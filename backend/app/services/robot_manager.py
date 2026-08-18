import asyncio
import logging
import os
import time
from typing import Optional

from app.models.schemas import RobotCommand, RobotStatusResponse
from app.websocket.manager import system_ws_manager

logger = logging.getLogger(__name__)


class RobotManager:
    """Manager for FAIRINO Robot Arm (Cobot) — TCP Socket Driver & Handshake Protocol.

    Architecture: Event-Driven Command / Response
    =============================================
    Firmware: Fairino V3.9.21 / FR3 V6.0
    Default Port: 8090 (Socket 1 on Fairino WebApp Controller)
    Default IP  : 192.168.57.2 (configurable via ROBOT_IP env var)

    LUA Script Commands Supported:
      - MOVE_HOME            : Returns "SUCCESS MOVE_HOME\n"
      - PICK <slot>          : Returns "SUCCESS PICK <slot>\n"
      - STORE <slot>         : Returns "SUCCESS STORE <slot>\n"
      - PICK_PRODUCT <slot>  : Returns "SUCCESS PICK <slot>\n"
      - PLACE_PRODUCT <slot> : Returns "SUCCESS STORE <slot>\n"
      - STATUS / GET_STATUS  : Returns "STATE:IDLE BUSY:FALSE POSITION:HOME\n"
      - STOP / ESTOP         : Returns "STOP SUCCESS STATE:IDLE\n"

    In simulator mode, mechanical delays are simulated with asyncio.sleep
    followed by state update and DONE signal.
    """

    _instance: Optional["RobotManager"] = None

    def __init__(self, simulator_mode: bool = False, robot_ip: str = "192.168.57.2", robot_port: int = 8090):
        self.simulator_mode = simulator_mode
        self.robot_ip = robot_ip
        self.robot_port = robot_port
        self.is_connected: bool = False
        self.state: str = "IDLE"             # "IDLE", "READY", "MOVING", "PICKING", "PLACING", "ERROR", "OFFLINE"
        self.current_slot: Optional[str] = None
        self.holding_product: Optional[str] = None
        self._reconnect_attempts: int = 0
        self._next_reconnect_time: float = 0.0
        self._socket_lock: asyncio.Lock = asyncio.Lock()
        self._is_busy_moving: bool = False

        # Handshake: asyncio.Event for command completion
        self._done_event: asyncio.Event = asyncio.Event()
        self._done_event.set()

    @classmethod
    def get_instance(cls) -> "RobotManager":
        if cls._instance is None:
            env_sim = os.getenv("ROBOT_SIMULATOR_MODE", "false").lower()
            sim_mode = env_sim in ("true", "1", "yes")
            robot_ip = os.getenv("ROBOT_IP", "192.168.57.2")
            robot_port = int(os.getenv("ROBOT_PORT", "8090"))
            cls._instance = RobotManager(simulator_mode=sim_mode, robot_ip=robot_ip, robot_port=robot_port)
        return cls._instance

    def update_config(self, robot_ip: Optional[str] = None, robot_port: Optional[int] = None, simulator_mode: Optional[bool] = None) -> None:
        if robot_ip is not None:
            self.robot_ip = robot_ip
        if robot_port is not None:
            self.robot_port = robot_port
        if simulator_mode is not None:
            self.simulator_mode = simulator_mode
        self._next_reconnect_time = 0.0
        logger.info("Updated RobotManager config: IP=%s, Port=%d, Simulator=%s", self.robot_ip, self.robot_port, self.simulator_mode)


    async def check_connection(self) -> bool:
        """Health check for FAIRINO Robot arm TCP Socket connection (Socket 1, Port 8090)."""
        if self.simulator_mode:
            self.is_connected = True
            return True

        # If robot is currently executing a motion command, it is active and online
        # Avoid opening a secondary socket connection while motion is in progress
        if self._is_busy_moving or self.state in ("MOVING", "PICKING", "PLACING"):
            self.is_connected = True
            return True

        # If another operation currently holds the socket lock, avoid collision
        if self._socket_lock.locked():
            return self.is_connected

        now = time.time()
        if now < self._next_reconnect_time:
            return self.is_connected

        try:
            async with self._socket_lock:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.robot_ip, self.robot_port),
                    timeout=3.0
                )
                # Send quick status ping
                writer.write(b"STATUS\r\n")
                await writer.drain()

                response_bytes = await asyncio.wait_for(reader.readline(), timeout=3.0)
                response_str = response_bytes.decode("utf-8", errors="ignore").strip()

                writer.close()
                await writer.wait_closed()

                if not self.is_connected:
                    logger.info("✅ FAIRINO Robot TCP Socket connected successfully (%s:%d) [Resp: %s]",
                                self.robot_ip, self.robot_port, response_str)

                self.is_connected = True
                self._reconnect_attempts = 0
                self._next_reconnect_time = 0.0
                return True

        except Exception as err:
            self._reconnect_attempts += 1
            backoff_delay = min(2 ** self._reconnect_attempts, 16)
            self._next_reconnect_time = now + backoff_delay
            if self.is_connected:
                logger.warning("❌ FAIRINO Robot TCP connection lost (%s:%d): %s. Retrying in %ds...",
                               self.robot_ip, self.robot_port, err, backoff_delay)
            self.is_connected = False
            return False

    def get_status(self) -> RobotStatusResponse:
        is_online = self.is_connected or self.simulator_mode
        current_state = self.state if is_online else "OFFLINE"
        return RobotStatusResponse(
            state=current_state,
            current_slot=self.current_slot,
            holding_product=self.holding_product,
            connected=is_online,
            simulator_mode=self.simulator_mode,
        )

    def signal_done(self) -> None:
        """Called externally or on response parser completion."""
        self._done_event.set()
        if self.state in ("MOVING", "PICKING", "PLACING"):
            self.state = "READY"
        logger.info("FAIRINO Robot: DONE signal received (State set to READY)")

    def emergency_stop(self) -> RobotStatusResponse:
        """Triggers Emergency Stop for FAIRINO Robot Arm (Sends ESTOP / STOP over TCP)."""
        self.state = "ERROR"
        self._done_event.set()
        if not self.simulator_mode:
            asyncio.create_task(self._send_socket_command("ESTOP", timeout=5.0))
        logger.error("FAIRINO Robot: EMERGENCY STOP TRIGGERED!")
        return self.get_status()

    async def _send_socket_command(self, payload: str, timeout: float = 30.0) -> bool:
        """Sends TCP string command to FAIRINO Robot LUA Server (Port 8090) and parses response line.

        Protocol Specifications:
        - Payload ending: '\r\n'
        - Lua response format:
            'SUCCESS MOVE_HOME\n'
            'SUCCESS PICK A1\n'
            'SUCCESS STORE B2\n'
            'BUSY STATE:MOVING POSITION:A1\n'
            'FAILED INVALID_SLOT Z9\n'
        """
        if self.simulator_mode:
            logger.info("FAIRINO Robot [SIMULATOR]: Sent payload '%s' over Socket TCP", payload)
            self.signal_done()
            return True

        msg = f"{payload.strip().upper()}\r\n"
        logger.info("FAIRINO Robot: Connecting to %s:%d to send '%s'...", self.robot_ip, self.robot_port, payload)

        self._is_busy_moving = True
        self.is_connected = True
        try:
            async with self._socket_lock:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.robot_ip, self.robot_port),
                    timeout=5.0
                )
                self.is_connected = True
                writer.write(msg.encode("utf-8"))
                await writer.drain()
                logger.info("FAIRINO Robot: Payload '%s' sent. Awaiting response (timeout %.1fs)...", payload, timeout)

                response_bytes = await asyncio.wait_for(reader.readline(), timeout=timeout)
                response_str = response_bytes.decode("utf-8", errors="ignore").strip()
                logger.info("FAIRINO Robot: Response received: '%s'", response_str)

                writer.close()
                await writer.wait_closed()

                resp_upper = response_str.upper()
                if "SUCCESS" in resp_upper or "OK" in resp_upper or "DONE" in resp_upper:
                    self.signal_done()
                    return True
                elif "BUSY" in resp_upper:
                    logger.warning("FAIRINO Robot reports BUSY: %s", response_str)
                    self.state = "ERROR"
                    return False
                elif "FAILED" in resp_upper or "ERROR" in resp_upper:
                    logger.error("FAIRINO Robot command FAILED: %s", response_str)
                    self.state = "ERROR"
                    return False

                self.signal_done()
                return True

        except (asyncio.TimeoutError, ConnectionRefusedError, OSError, Exception) as err:
            logger.error("❌ FAIRINO Robot Socket connection failed for '%s': %s.", payload, err)
            self.is_connected = False
            self.state = "ERROR"
            return False
        finally:
            self._is_busy_moving = False

    async def _wait_for_done(self, timeout: float = 30.0) -> bool:
        """Wait for robot DONE signal."""
        if self.simulator_mode:
            return True

        self._done_event.clear()
        try:
            await asyncio.wait_for(self._done_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.warning("FAIRINO Robot: DONE signal timeout (%.1fs)", timeout)
            return False

    async def execute_command(self, cmd: RobotCommand, slot: Optional[str] = None) -> RobotStatusResponse:
        """Execute a robot command over Fairino TCP Socket protocol and wait for completion."""
        # Normalize slot target: DOCK, PAD, PAD_N1 map to N1 in Lua script
        target = slot or "N1"
        if target.upper() in ("DOCK", "PAD", "PAD_N1"):
            target = "N1"
        else:
            target = target.upper().strip()

        logger.info("Executing FAIRINO Robot command: %s (slot: %s -> target: %s, simulator: %s)", cmd.value, slot, target, self.simulator_mode)

        if cmd in (RobotCommand.MOVE_HOME, RobotCommand.REQUEST_Z_DOWN):
            self.state = "MOVING"
            payload = "MOVE_HOME" if cmd == RobotCommand.MOVE_HOME else "REQUEST_Z_DOWN"
            if self.simulator_mode:
                await asyncio.sleep(0.4)
                success = True
            else:
                success = await self._send_socket_command(payload, timeout=15.0)
            if not success:
                raise RuntimeError(f"FAIRINO Robot MOVE_HOME execution failed")
            self.state = "READY"
            self.current_slot = None
            logger.info("FAIRINO Robot: Returned to HOME position (DONE)")

        elif cmd == RobotCommand.STANDBY:
            self.state = "MOVING"
            if self.simulator_mode:
                await asyncio.sleep(0.4)
                success = True
            else:
                success = await self._send_socket_command("MOVE_HOME", timeout=15.0)
            if not success:
                raise RuntimeError(f"FAIRINO Robot STANDBY execution failed")
            self.state = "READY"
            logger.info("FAIRINO Robot: Moved to STANDBY position (DONE)")

        elif cmd == RobotCommand.REQUEST_Z_UP:
            self.state = "READY"
            if not self.simulator_mode:
                await self._send_socket_command("REQUEST_Z_UP", timeout=10.0)
            logger.info("FAIRINO Robot: Ready for Z_UP operation (DONE)")

        elif cmd in (RobotCommand.PICK_PRODUCT, RobotCommand.PICK):
            self.state = "PICKING"
            self.current_slot = target
            payload = f"PICK {target}"
            if self.simulator_mode:
                await asyncio.sleep(0.6)
                success = True
            else:
                success = await self._send_socket_command(payload, timeout=30.0)
            if not success:
                raise RuntimeError(f"FAIRINO Robot PICK {target} execution failed")
            self.holding_product = f"PROD_{target}" if target else "SP001"
            self.state = "READY"
            logger.info("FAIRINO Robot: Successfully picked product from %s (DONE)", target)

        elif cmd in (RobotCommand.PLACE_PRODUCT, RobotCommand.STORE):
            self.state = "PLACING"
            self.current_slot = target
            payload = f"STORE {target}"
            if self.simulator_mode:
                await asyncio.sleep(0.6)
                success = True
            else:
                success = await self._send_socket_command(payload, timeout=30.0)
            if not success:
                raise RuntimeError(f"FAIRINO Robot STORE {target} execution failed")
            self.holding_product = None
            self.state = "READY"
            logger.info("FAIRINO Robot: Successfully placed product into %s (DONE)", target)

        elif cmd == RobotCommand.PICK_UAV:
            self.state = "PICKING"
            self.current_slot = "N1"
            if self.simulator_mode:
                await asyncio.sleep(0.6)
                success = True
            else:
                success = await self._send_socket_command("PICK N1", timeout=30.0)
            if not success:
                raise RuntimeError(f"FAIRINO Robot PICK N1 (UAV) execution failed")
            self.holding_product = "SP_FROM_UAV"
            self.state = "READY"
            logger.info("FAIRINO Robot: Successfully picked cargo from UAV Pad N1 (DONE)")

        elif cmd == RobotCommand.PLACE_UAV:
            self.state = "PLACING"
            self.current_slot = "N1"
            if self.simulator_mode:
                await asyncio.sleep(0.6)
                success = True
            else:
                success = await self._send_socket_command("STORE N1", timeout=30.0)
            if not success:
                raise RuntimeError(f"FAIRINO Robot STORE N1 (UAV) execution failed")
            self.holding_product = None
            self.state = "READY"
            logger.info("FAIRINO Robot: Successfully loaded cargo onto UAV Pad N1 (DONE)")

        elif cmd == RobotCommand.SCAN_QR_POS:
            self.state = "MOVING"
            if self.simulator_mode:
                await asyncio.sleep(0.5)
                success = True
            else:
                success = await self._send_socket_command("MOVE_HOME", timeout=20.0)
            if not success:
                raise RuntimeError(f"FAIRINO Robot SCAN_QR_POS execution failed")
            self.state = "READY"
            logger.info("FAIRINO Robot: Positioned at QR Vision Scanner Station (DONE)")

        elif cmd == RobotCommand.OPEN_GRIPPER:
            if self.simulator_mode:
                await asyncio.sleep(0.2)
            else:
                await self._send_socket_command("GRIPPER_OPEN", timeout=10.0)
            logger.info("FAIRINO Robot: Gripper OPENED (DONE)")

        elif cmd == RobotCommand.CLOSE_GRIPPER:
            if self.simulator_mode:
                await asyncio.sleep(0.2)
            else:
                await self._send_socket_command("GRIPPER_CLOSE", timeout=10.0)
            logger.info("FAIRINO Robot: Gripper CLOSED (DONE)")

        status_res = self.get_status()
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(system_ws_manager.broadcast("ROBOT_STATUS", status_res.model_dump()))
        except RuntimeError:
            pass

        return status_res

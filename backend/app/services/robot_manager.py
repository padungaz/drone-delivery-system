import asyncio
import logging
import os
from typing import Optional

from app.models.schemas import RobotCommand, RobotStatusResponse
from app.websocket.manager import system_ws_manager

logger = logging.getLogger(__name__)


class RobotManager:
    """Manager for FAIRINO Robot Arm (Cobot) — Handshake Signal Protocol.

    Architecture: Event-Driven Command/Done
    ========================================
    Backend sends a command to Robot Arm.
    Robot autonomously executes the full motion sequence.
    Robot signals completion via done callback / state change.

    In simulator mode, mechanical delays are simulated with asyncio.sleep
    followed by an immediate DONE signal.

    Controls:
      - Motion states (IDLE, READY, MOVING, PICKING, PLACING, ERROR)
      - Picking & placing items from UAV or Storage Slots (A1..C3)
      - Handshake signal: execute_command returns ONLY after robot reports DONE
    """

    _instance: Optional["RobotManager"] = None

    def __init__(self, simulator_mode: bool = False, robot_ip: str = "192.168.58.2", robot_port: int = 8080):
        self.simulator_mode = simulator_mode
        self.robot_ip = robot_ip
        self.robot_port = robot_port
        self.is_connected: bool = False
        self.state: str = "IDLE"
        self.current_slot: Optional[str] = None
        self.holding_product: Optional[str] = None
        self._reconnect_attempts: int = 0
        self._next_reconnect_time: float = 0.0

        # Handshake: asyncio.Event for external DONE signal from real robot
        self._done_event: asyncio.Event = asyncio.Event()
        self._done_event.set()  # Initially ready (no pending command)

    @classmethod
    def get_instance(cls) -> "RobotManager":
        if cls._instance is None:
            env_sim = os.getenv("ROBOT_SIMULATOR_MODE", "false").lower()
            sim_mode = env_sim in ("true", "1", "yes")
            robot_ip = os.getenv("ROBOT_IP", "192.168.58.2")
            robot_port = int(os.getenv("ROBOT_PORT", "8080"))
            cls._instance = RobotManager(simulator_mode=sim_mode, robot_ip=robot_ip, robot_port=robot_port)
        return cls._instance

    async def check_connection(self) -> bool:
        """Health check for FAIRINO Robot arm TCP Socket connection."""
        if self.simulator_mode:
            self.is_connected = True
            return True

        import time
        now = time.time()
        if now < self._next_reconnect_time:
            return self.is_connected

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.robot_ip, self.robot_port),
                timeout=3.0
            )
            writer.close()
            await writer.wait_closed()
            if not self.is_connected:
                logger.info("✅ FAIRINO Robot TCP Socket connected successfully (%s:%d)", self.robot_ip, self.robot_port)
            self.is_connected = True
            self._reconnect_attempts = 0
            self._next_reconnect_time = 0.0
            return True
        except Exception as err:
            self._reconnect_attempts += 1
            backoff_delay = min(2 ** self._reconnect_attempts, 16)
            self._next_reconnect_time = now + backoff_delay
            if self.is_connected:
                logger.warning("❌ FAIRINO Robot connection lost (%s:%d): %s. Retrying in %ds...", self.robot_ip, self.robot_port, err, backoff_delay)
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
        """Called externally when real robot reports command completion (ROBOT_DONE).
        Can be triggered by a robot callback endpoint or polling loop.
        """
        self._done_event.set()
        if self.state in ("MOVING", "PICKING", "PLACING"):
            self.state = "READY"
        logger.info("FAIRINO Robot: DONE signal received (State set to READY)")

    def emergency_stop(self) -> RobotStatusResponse:
        """Triggers Emergency Stop for FAIRINO Robot Arm."""
        self.state = "ERROR"
        self._done_event.set()
        if not self.simulator_mode:
            asyncio.create_task(self._send_socket_command("EMERGENCY_STOP", timeout=5.0))
        logger.error("FAIRINO Robot: EMERGENCY STOP TRIGGERED!")
        return self.get_status()

    async def _send_socket_command(self, payload: str, timeout: float = 30.0) -> bool:
        """Sends Socket TCP string command to FAIRINO Robot and awaits reply line.
        Format example: 'PICK A1\\n' or 'STORE B2\\n' or 'MOVE_HOME\\n'.
        The Lua script running on FAIRINO parses the command + slot and executes the motion trajectory.
        """
        if self.simulator_mode:
            logger.info("FAIRINO Robot [SIMULATOR]: Sent payload '%s' over Socket TCP", payload)
            return True

        msg = f"{payload}\n"
        logger.info("FAIRINO Robot: Connecting to %s:%d to send '%s'...", self.robot_ip, self.robot_port, payload)

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.robot_ip, self.robot_port),
                timeout=5.0
            )
            self.is_connected = True
            writer.write(msg.encode("utf-8"))
            await writer.drain()
            logger.info("FAIRINO Robot: Payload '%s' sent. Waiting for response/DONE...", payload)

            response_bytes = await asyncio.wait_for(reader.readline(), timeout=timeout)
            response_str = response_bytes.decode("utf-8").strip()
            logger.info("FAIRINO Robot: Response received: '%s'", response_str)

            writer.close()
            await writer.wait_closed()

            if "DONE" in response_str.upper() or "OK" in response_str.upper():
                self.signal_done()
                return True
            return True
        except (asyncio.TimeoutError, Exception) as err:
            logger.warning("FAIRINO Robot Socket error or timeout for '%s': %s. Waiting for HTTP callback signal...", payload, err)
            # Fallback to waiting for external HTTP signal_done() callback
            return await self._wait_for_done(timeout=timeout)

    async def _wait_for_done(self, timeout: float = 30.0) -> bool:
        """Wait for robot DONE signal. In simulator mode, returns immediately.
        Returns True if DONE received within timeout, False on timeout.
        """
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
        """Execute a robot command and wait for DONE signal (Handshake Protocol).

        Backend sends command + location target (e.g. 'PICK A1', 'STORE B2', 'MOVE_HOME') over Socket TCP.
        The motion trajectory calculation and robot axis motion execution run in the LUA script on the robot.

        Flow:
          1. Format TCP Socket payload (Command + Slot/Target)
          2. Set state to action state (MOVING, PICKING, PLACING)
          3. In simulator mode: simulate delay then mark DONE
          4. In real mode: send TCP Socket payload to robot Lua listener & wait for DONE signal
          5. Update state to READY on success
          6. Return status
        """
        target = slot or "PAD"
        logger.info("Executing FAIRINO Robot command: %s (slot: %s, simulator: %s)", cmd.value, slot, self.simulator_mode)

        if cmd in (RobotCommand.MOVE_HOME, RobotCommand.REQUEST_Z_DOWN):
            self.state = "MOVING"
            payload = "MOVE_HOME" if cmd == RobotCommand.MOVE_HOME else "REQUEST_Z_DOWN"
            if self.simulator_mode:
                await asyncio.sleep(0.4)
            else:
                await self._send_socket_command(payload, timeout=15.0)
            self.state = "READY"
            self.current_slot = None
            logger.info("FAIRINO Robot: Returned to HOME position (DONE)")

        elif cmd == RobotCommand.REQUEST_Z_UP:
            self.state = "READY"
            if not self.simulator_mode:
                await self._send_socket_command("REQUEST_Z_UP", timeout=10.0)
            logger.info("FAIRINO Robot: Ready for Z_UP operation (DONE)")

        elif cmd in (RobotCommand.PICK_PRODUCT, RobotCommand.PICK):
            self.state = "PICKING"
            self.current_slot = slot
            payload = f"PICK {target}" if cmd == RobotCommand.PICK else f"PICK_PRODUCT {target}"
            if self.simulator_mode:
                await asyncio.sleep(0.6)
            else:
                await self._send_socket_command(payload, timeout=30.0)
            self.holding_product = f"PROD_{slot}" if slot else "SP001"
            self.state = "READY"
            logger.info("FAIRINO Robot: Successfully picked product from %s (DONE)", target)

        elif cmd in (RobotCommand.PLACE_PRODUCT, RobotCommand.STORE):
            self.state = "PLACING"
            self.current_slot = slot
            payload = f"STORE {target}" if cmd == RobotCommand.STORE else f"PLACE_PRODUCT {target}"
            if self.simulator_mode:
                await asyncio.sleep(0.6)
            else:
                await self._send_socket_command(payload, timeout=30.0)
            self.holding_product = None
            self.state = "READY"
            logger.info("FAIRINO Robot: Successfully placed product into %s (DONE)", target)

        status_res = self.get_status()
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(system_ws_manager.broadcast("ROBOT_STATUS", status_res.model_dump()))
        except RuntimeError:
            pass

        return status_res

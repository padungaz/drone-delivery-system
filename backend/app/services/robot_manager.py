import asyncio
import logging
import os
import time
from typing import Optional

from app.database.repository import async_session
from app.models.schemas import RobotCommand, RobotStatusResponse, StorageSlotStatus
from app.services.inventory_manager import InventoryManager
from app.websocket.manager import system_ws_manager

logger = logging.getLogger(__name__)


class RobotManager:
    """Manager for FAIRINO Robot Arm (Cobot) — TCP Socket Driver & Handshake Protocol.

    Architecture: Persistent TCP Connection + Event-Driven Request Listener
    ========================================================================
    Firmware: Fairino V3.9.21 / FR3 V6.0
    Default Port: 8090 (Socket 1 on Fairino WebApp Controller)
    Default IP  : 192.168.57.2 (configurable via ROBOT_IP env var)

    Two-way Communication:
    1. Backend -> Robot (Commands):
       - MOVE_HOME            : Returns "SUCCESS MOVE_HOME\n"
       - PICK <slot>          : Returns "SUCCESS PICK <slot>\n"
       - STORE <slot>         : Returns "SUCCESS STORE <slot>\n"
       - OUTBOUND_CYCLE <slot>: Returns "SUCCESS OUTBOUND <slot>\n"
       - INBOUND_CYCLE <slot> : Returns "SUCCESS INBOUND <slot>\n"
       - STATUS / GET_STATUS  : Returns "STATE:IDLE BUSY:FALSE POSITION:HOME\n"
       - STOP / ESTOP         : Returns "STOP SUCCESS STATE:IDLE\n"

    2. Robot -> Backend (Autonomous Requests from DI1 / DI2 triggers):
       - REQUEST_PICK_SLOT    : Robot asks which slot to pick -> Backend replies "PICK <slot>\n"
       - REQUEST_STORE_SLOT   : Robot asks which slot to store -> Backend replies "STORE <slot>\n"
       - DONE_PICK <slot>     : Robot completed picking from slot -> Backend updates DB
       - DONE_STORE <slot>    : Robot completed storing into slot -> Backend updates DB
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

        # Persistent connection handles
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._listener_task: Optional[asyncio.Task] = None
        self._pending_response_future: Optional[asyncio.Future] = None

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
        changed = False
        if robot_ip is not None and robot_ip != self.robot_ip:
            self.robot_ip = robot_ip
            changed = True
        if robot_port is not None and robot_port != self.robot_port:
            self.robot_port = robot_port
            changed = True
        if simulator_mode is not None and simulator_mode != self.simulator_mode:
            self.simulator_mode = simulator_mode
            changed = True
        self._next_reconnect_time = 0.0
        if changed and not self.simulator_mode:
            asyncio.create_task(self._disconnect_socket())
        logger.info("Updated RobotManager config: IP=%s, Port=%d, Simulator=%s", self.robot_ip, self.robot_port, self.simulator_mode)

    async def _ensure_connection(self) -> bool:
        """Establish or maintain persistent TCP socket connection with Robot controller."""
        if self.simulator_mode:
            self.is_connected = True
            return True

        if self._writer is not None and not self._writer.is_closing():
            return True

        now = time.time()
        if now < self._next_reconnect_time:
            return False

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.robot_ip, self.robot_port),
                timeout=3.0
            )
            self._reader = reader
            self._writer = writer
            self.is_connected = True
            self._reconnect_attempts = 0
            self._next_reconnect_time = 0.0

            if self._listener_task is None or self._listener_task.done():
                self._listener_task = asyncio.create_task(self._socket_listener_loop(), name="robot_listener")

            logger.info("✅ FAIRINO Robot Persistent TCP Socket connected (%s:%d)", self.robot_ip, self.robot_port)
            return True
        except Exception as err:
            self._reconnect_attempts += 1
            backoff_delay = min(2 ** self._reconnect_attempts, 16)
            self._next_reconnect_time = now + backoff_delay
            self.is_connected = False
            logger.warning("❌ FAIRINO Robot TCP connection failed (%s:%d): %s. Retrying in %ds...",
                           self.robot_ip, self.robot_port, err, backoff_delay)
            return False

    async def _socket_listener_loop(self) -> None:
        """Background coroutine continuously reading from persistent Robot socket."""
        logger.info("FAIRINO Robot: Socket listener loop started")
        while not self.simulator_mode:
            try:
                if self._reader is None:
                    break
                line_bytes = await self._reader.readline()
                if not line_bytes:
                    logger.warning("FAIRINO Robot: Socket closed by peer (EOF)")
                    break
                line = line_bytes.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                logger.info("FAIRINO Robot [RX]: '%s'", line)
                line_upper = line.upper()

                # 1. Handle Autonomous DI1 Trigger: Robot reports ready via DI1
                if line_upper.startswith("ROBOT_READY") or line_upper.startswith("REQUEST_PICK_SLOT"):
                    await self._handle_robot_pick_request()

                # 2. Handle Autonomous DI2 Trigger: Robot reports item detected at O1 via DI2
                elif line_upper.startswith("ROBOT_INBOUND_READY") or line_upper.startswith("REQUEST_STORE_SLOT"):
                    await self._handle_robot_store_request()

                # 3. Handle Robot Pick Complete notification
                elif line_upper.startswith("DONE_PICK") or line_upper.startswith("SUCCESS PICK"):
                    parts = line.split()
                    slot = parts[1] if len(parts) > 1 and parts[1] != "PICK" else (parts[2] if len(parts) > 2 else "")
                    await self._handle_robot_pick_done(slot)
                    if self._pending_response_future and not self._pending_response_future.done():
                        self._pending_response_future.set_result(line)

                # 4. Handle Robot Store Complete notification
                elif line_upper.startswith("DONE_STORE") or line_upper.startswith("SUCCESS STORE"):
                    parts = line.split()
                    slot = parts[1] if len(parts) > 1 and parts[1] != "STORE" else (parts[2] if len(parts) > 2 else "")
                    await self._handle_robot_store_done(slot)
                    if self._pending_response_future and not self._pending_response_future.done():
                        self._pending_response_future.set_result(line)

                # 5. Handle Responses for command callers
                elif self._pending_response_future and not self._pending_response_future.done():
                    self._pending_response_future.set_result(line)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in FAIRINO Robot socket listener: %s", e)
                break

        await self._disconnect_socket()

    async def _handle_robot_pick_request(self) -> None:
        """Robot triggered via DI1 -> needs next slot with product to pick to conveyor."""
        try:
            # Check if StaffOperationManager is actively running an OUTBOUND queue!
            from app.services.staff_operation_manager import staff_operation_manager
            if staff_operation_manager.status == "RUNNING" and staff_operation_manager.active_type == "OUTBOUND":
                logger.info("FAIRINO Robot [DI1 Event]: ROBOT_READY signal received for Staff Outbound queue.")
                staff_operation_manager.notify_robot_ready()
                return

            async with async_session() as session:
                inv_mgr = InventoryManager(session)
                occupied = await inv_mgr.get_occupied_slots()
                if occupied:
                    target_slot = occupied[0].slot_name
                    logger.info("FAIRINO Robot: Auto-assigning PICK slot '%s'", target_slot)
                    await self._send_raw_socket_reply(f"PICK {target_slot}\n")
                else:
                    logger.warning("FAIRINO Robot requested PICK slot, but warehouse is empty.")
                    await self._send_raw_socket_reply("NONE\n")
        except Exception as err:
            logger.error("Failed to handle REQUEST_PICK_SLOT: %s", err)
            await self._send_raw_socket_reply("NONE\n")

    async def _handle_robot_store_request(self) -> None:
        """Robot triggered via DI2 -> needs next empty slot to store from conveyor."""
        try:
            # Check if StaffOperationManager is actively running an INBOUND cycle!
            from app.services.staff_operation_manager import staff_operation_manager
            if staff_operation_manager.status == "RUNNING" and staff_operation_manager.active_type == "INBOUND":
                logger.info("FAIRINO Robot [DI2 Event]: ROBOT_INBOUND_READY signal received for Staff Inbound.")
                staff_operation_manager.notify_inbound_ready()
                return

            async with async_session() as session:
                inv_mgr = InventoryManager(session)
                free_slot = await inv_mgr.find_available_slot()
                if free_slot:
                    target_slot = free_slot.slot_name
                    logger.info("FAIRINO Robot: Auto-assigning STORE slot '%s'", target_slot)
                    await self._send_raw_socket_reply(f"STORE {target_slot}\n")
                else:
                    logger.warning("FAIRINO Robot requested STORE slot, but warehouse is FULL.")
                    await self._send_raw_socket_reply("FULL\n")
        except Exception as err:
            logger.error("Failed to handle REQUEST_STORE_SLOT / ROBOT_INBOUND_READY: %s", err)
            await self._send_raw_socket_reply("FULL\n")

    async def _handle_robot_pick_done(self, slot: str) -> None:
        logger.info("FAIRINO Robot reports DONE_PICK for slot '%s'", slot)
        if slot:
            try:
                async with async_session() as session:
                    inv_mgr = InventoryManager(session)
                    await inv_mgr.update_slot(slot_name=slot, status=StorageSlotStatus.EMPTY, product_id=None, qr_code=None)
                    all_slots = await inv_mgr.get_all_slots()
                    slots_data = [
                        {
                            "id": s.id,
                            "slot_name": s.slot_name,
                            "status": s.status,
                            "product_id": s.product_id,
                            "qr_code": s.qr_code,
                            "is_empty": s.status == StorageSlotStatus.EMPTY.value or not s.product_id,
                        }
                        for s in all_slots
                    ]
                    await system_ws_manager.broadcast("STORAGE_UPDATE", {"slots": slots_data})
            except Exception as err:
                logger.error("Error updating slot after DONE_PICK: %s", err)

    async def _handle_robot_store_done(self, slot: str) -> None:
        logger.info("FAIRINO Robot reports DONE_STORE for slot '%s'", slot)
        if slot:
            try:
                async with async_session() as session:
                    inv_mgr = InventoryManager(session)
                    await inv_mgr.update_slot(slot_name=slot, status=StorageSlotStatus.OCCUPIED, product_id=f"PROD_{slot}")
                    all_slots = await inv_mgr.get_all_slots()
                    slots_data = [
                        {
                            "id": s.id,
                            "slot_name": s.slot_name,
                            "status": s.status,
                            "product_id": s.product_id,
                            "qr_code": s.qr_code,
                            "is_empty": s.status == StorageSlotStatus.EMPTY.value or not s.product_id,
                        }
                        for s in all_slots
                    ]
                    await system_ws_manager.broadcast("STORAGE_UPDATE", {"slots": slots_data})
            except Exception as err:
                logger.error("Error updating slot after DONE_STORE: %s", err)

    async def _send_raw_socket_reply(self, text: str) -> None:
        if self._writer and not self._writer.is_closing():
            self._writer.write(text.encode("utf-8"))
            await self._writer.drain()

    async def _disconnect_socket(self) -> None:
        self.is_connected = False
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
        self._reader = None
        if self._listener_task is not None and not self._listener_task.done():
            self._listener_task.cancel()
        self._listener_task = None

    async def check_connection(self) -> bool:
        """Health check for FAIRINO Robot arm TCP Socket connection (Socket 1, Port 8090)."""
        if self.simulator_mode:
            self.is_connected = True
            return True

        if self._is_busy_moving or self.state in ("MOVING", "PICKING", "PLACING"):
            self.is_connected = True
            return True

        if self._writer is not None and not self._writer.is_closing():
            self.is_connected = True
            return True

        return await self._ensure_connection()

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

    async def _send_socket_command(self, payload: str, timeout: Optional[float] = None) -> bool:
        """Sends TCP string command to FAIRINO Robot LUA Server (Port 8090) over persistent connection."""
        if self.simulator_mode:
            logger.info("FAIRINO Robot [SIMULATOR]: Sent payload '%s' over Socket TCP", payload)
            self.signal_done()
            return True

        msg = f"{payload.strip().upper()}\r\n"
        self._is_busy_moving = True
        try:
            async with self._socket_lock:
                connected = await self._ensure_connection()
                if not connected or self._writer is None:
                    raise ConnectionError(f"Could not connect to FAIRINO Robot at {self.robot_ip}:{self.robot_port}")

                loop = asyncio.get_running_loop()
                self._pending_response_future = loop.create_future()

                self._writer.write(msg.encode("utf-8"))
                await self._writer.drain()
                
                if timeout is not None and timeout > 0:
                    logger.info("FAIRINO Robot: Payload '%s' sent. Awaiting response (timeout %.1fs)...", payload, timeout)
                    response_str = await asyncio.wait_for(self._pending_response_future, timeout=timeout)
                else:
                    logger.info("FAIRINO Robot: Payload '%s' sent. Awaiting response (không giới hạn thời gian chờ)...", payload)
                    response_str = await self._pending_response_future
                
                logger.info("FAIRINO Robot: Response received: '%s'", response_str)

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

        except asyncio.TimeoutError:
            logger.warning("FAIRINO Robot command timeout for '%s'", payload)
            self.state = "ERROR"
            return False
        except (ConnectionRefusedError, OSError, Exception) as err:
            logger.error("❌ FAIRINO Robot Socket command failed for '%s': %s.", payload, err)
            self.is_connected = False
            self.state = "ERROR"
            await self._disconnect_socket()
            return False
        finally:
            self._pending_response_future = None
            self._is_busy_moving = False

    async def _wait_for_done(self, timeout: Optional[float] = None) -> bool:
        """Wait for robot DONE signal."""
        if self.simulator_mode:
            return True

        self._done_event.clear()
        try:
            if timeout is not None and timeout > 0:
                await asyncio.wait_for(self._done_event.wait(), timeout=timeout)
            else:
                await self._done_event.wait()
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

        if cmd == RobotCommand.MOVE_HOME:
            self.state = "MOVING"
            payload = "MOVE_HOME"
            if self.simulator_mode:
                await asyncio.sleep(0.4)
                success = True
            else:
                success = await self._send_socket_command(payload, timeout=None)
            if not success:
                raise RuntimeError("FAIRINO Robot MOVE_HOME execution failed")
            self.state = "READY"
            self.current_slot = None
            logger.info("FAIRINO Robot: Returned to HOME position (DONE)")

        elif cmd == RobotCommand.STANDBY:
            self.state = "MOVING"
            if self.simulator_mode:
                await asyncio.sleep(0.4)
                success = True
            else:
                success = await self._send_socket_command("MOVE_HOME", timeout=None)
            if not success:
                raise RuntimeError("FAIRINO Robot STANDBY execution failed")
            self.state = "READY"
            self.current_slot = None
            logger.info("FAIRINO Robot: Entered STANDBY position (DONE)")

        elif cmd in (RobotCommand.PICK, RobotCommand.PICK_PRODUCT):
            self.state = "PICKING"
            self.current_slot = target
            payload = f"PICK {target}"
            if self.simulator_mode:
                await asyncio.sleep(0.6)
                success = True
            else:
                success = await self._send_socket_command(payload, timeout=None)
            if not success:
                raise RuntimeError(f"FAIRINO Robot PICK {target} execution failed")
            self.holding_product = f"PRD-{target}"
            self.state = "READY"
            logger.info("FAIRINO Robot: Successfully picked product from %s (DONE)", target)

        elif cmd in (RobotCommand.STORE, RobotCommand.PLACE_PRODUCT):
            self.state = "PLACING"
            self.current_slot = target
            payload = f"STORE {target}"
            if self.simulator_mode:
                await asyncio.sleep(0.6)
                success = True
            else:
                success = await self._send_socket_command(payload, timeout=None)
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
                success = await self._send_socket_command("PICK N1", timeout=None)
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
                success = await self._send_socket_command("STORE N1", timeout=None)
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
                success = await self._send_socket_command("MOVE_HOME", timeout=None)
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

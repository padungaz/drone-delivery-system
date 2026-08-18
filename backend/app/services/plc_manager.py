import asyncio
import logging
import os
from typing import Optional

from app.models.schemas import PLCCommand, PLCStatusResponse
from app.websocket.manager import system_ws_manager

logger = logging.getLogger(__name__)

# Attempt to import snap7 safely
try:
    # pyrefly: ignore [missing-import]
    import snap7
    # pyrefly: ignore [missing-import]
    from snap7.util import get_bool, set_bool
    SNAP7_AVAILABLE = True
except (ImportError, Exception) as snap7_err:
    SNAP7_AVAILABLE = False
    snap7 = None
    logger.warning(
        "python-snap7 module not available or native library missing. Real PLC mode will fallback to simulator mode. Error: %s",
        snap7_err,
    )

# PLC Connection Defaults (Siemens S7-1200)
DEFAULT_PLC_IP = "192.168.58.10"
DEFAULT_RACK = 0
DEFAULT_SLOT = 1
DEFAULT_DB_NUMBER = 15

# ========================================================================================
# DB15 Handshake Protocol Mapping (Siemens S7-1200 Docking Station)
# ========================================================================================
#
# Byte 0: Backend -> PLC (Command bits, written by Backend)
#   0.0: cmd_lock_drone       - Yêu cầu PLC kích hoạt cơ cấu khóa cố định Drone
#   0.1: cmd_unlock_drone     - Yêu cầu PLC mở khóa, giải phóng Drone
#   0.2: cmd_z_up             - Yêu cầu PLC điều khiển trục Z nâng lên
#   0.3: cmd_z_down           - Yêu cầu PLC điều khiển trục Z hạ xuống
#   0.4: cmd_stop_plc         - Yêu cầu PLC dừng chu trình hoạt động
#   0.5: cmd_start_plc        - Yêu cầu PLC khởi động / cho phép hệ thống hoạt động
#   0.6: cmd_reset_plc        - Yêu cầu PLC reset lỗi và đưa hệ thống về trạng thái sẵn sàng
#   0.7: (reserved)
#
# Byte 2: PLC -> Backend (Status bits, read-only by Backend)
#   2.0: drone_detected       - PLC phát hiện Drone đã hạ cánh đúng vị trí Dock
#   2.1: plc_locked_state     - Trạng thái cơ cấu khóa Drone đã hoàn thành
#   2.2: plc_z_is_up          - Trạng thái trục Z đã nâng đến vị trí trên
#   2.3: plc_z_is_down        - Trạng thái trục Z đã hạ về vị trí ban đầu
#   2.4: plc_on               - PLC đang hoạt động và sẵn sàng nhận lệnh
#   2.5: plc_error            - PLC phát hiện lỗi trong quá trình vận hành
#   2.6: emergency_stop       - Trạng thái nút dừng khẩn cấp được kích hoạt
#   2.7: (reserved)
#
# ========================================================================================

# Byte 0: Backend -> PLC (Command bits)
OFFSET_CMD_LOCK          = (0, 0)  # cmd_lock_drone: Bool 0.0
OFFSET_CMD_UNLOCK        = (0, 1)  # cmd_unlock_drone: Bool 0.1
OFFSET_CMD_Z_UP          = (0, 2)  # cmd_z_up: Bool 0.2
OFFSET_CMD_Z_DOWN        = (0, 3)  # cmd_z_down: Bool 0.3
OFFSET_CMD_STOP          = (0, 4)  # cmd_stop_plc: Bool 0.4
OFFSET_CMD_START         = (0, 5)  # cmd_start_plc: Bool 0.5
OFFSET_CMD_RESET         = (0, 6)  # cmd_reset_plc: Bool 0.6

# Byte 2: PLC -> Backend (Status bits)
OFFSET_DRONE_DETECTED    = (2, 0)  # drone_detected: Bool 2.0
OFFSET_PLC_LOCKED_STATE  = (2, 1)  # plc_locked_state: Bool 2.1 (1 = Locked)
OFFSET_PLC_Z_IS_UP       = (2, 2)  # plc_z_is_up: Bool 2.2 (1 = Z at Top)
OFFSET_PLC_Z_IS_DOWN     = (2, 3)  # plc_z_is_down: Bool 2.3 (1 = Z at Bottom)
OFFSET_PLC_ON            = (2, 4)  # plc_on: Bool 2.4 (1 = Active/Ready)
OFFSET_PLC_ERROR         = (2, 5)  # plc_error: Bool 2.5 (1 = Error)
OFFSET_E_STOP            = (2, 6)  # emergency_stop: Bool 2.6 (1 = E-Stop Active)

# Handshake timing defaults
DEFAULT_HANDSHAKE_TIMEOUT = 25.0   # Seconds to wait for target status signal
DEFAULT_POLL_INTERVAL     = 0.15   # Seconds between DB reads during wait


class PLCManager:
    """Manager for PLC Siemens S7-1200 Docking Station (DB15 Protocol Mapping).

    Architecture: Event-Driven Signal Protocol
    ==========================================
    Backend (Master Orchestrator) sends command bits to PLC via DB15 Byte 0.
    PLC autonomously executes the physical sequence and updates status bits in DB15 Byte 2.
    """

    _instance: Optional["PLCManager"] = None

    def __init__(
        self,
        simulator_mode: bool = True,
        plc_ip: str = DEFAULT_PLC_IP,
        rack: int = DEFAULT_RACK,
        slot: int = DEFAULT_SLOT,
        db_number: int = DEFAULT_DB_NUMBER,
    ):
        self.simulator_mode = simulator_mode
        self.plc_ip = plc_ip
        self.rack = rack
        self.slot = slot
        self.db_number = db_number

        self.client = None
        self.is_connected = False
        self._lock: Optional[asyncio.Lock] = None

        # Cached states (updated from PLC DB15 Byte 2 status bits or simulator)
        self.drone_detected: bool = False
        self.plc_locked_state: bool = False
        self.drone_locked: bool = False       # Alias for plc_locked_state
        self.plc_z_is_up: bool = False
        self.plc_z_is_down: bool = True       # Default DOWN at home
        self.plc_on: bool = True              # Active & ready by default
        self.plc_error: bool = False
        self.emergency_stop: bool = False
        self.z_axis: str = "DOWN"             # "UP", "DOWN", "MOVING", "HOME"
        self.plc_busy: bool = False
        self._reconnect_attempts: int = 0
        self._next_reconnect_time: float = 0.0

        if not self.simulator_mode and SNAP7_AVAILABLE:
            self._connect_plc()

    @classmethod
    def get_instance(cls) -> "PLCManager":
        if cls._instance is None:
            # Check environment variables (default simulator_mode is True unless PLC_SIMULATOR_MODE=false)
            env_sim = os.getenv("PLC_SIMULATOR_MODE", "false").lower()
            sim_mode = env_sim not in ("false", "0", "no")
            plc_ip = os.getenv("PLC_IP", DEFAULT_PLC_IP)
            cls._instance = PLCManager(simulator_mode=sim_mode, plc_ip=plc_ip)
        return cls._instance

    def update_config(
        self,
        plc_ip: Optional[str] = None,
        rack: Optional[int] = None,
        slot: Optional[int] = None,
        db_number: Optional[int] = None,
        simulator_mode: Optional[bool] = None,
    ) -> None:
        if plc_ip is not None:
            self.plc_ip = plc_ip
        if rack is not None:
            self.rack = rack
        if slot is not None:
            self.slot = slot
        if db_number is not None:
            self.db_number = db_number
        if simulator_mode is not None:
            self.simulator_mode = simulator_mode
        self._next_reconnect_time = 0.0
        if self.client:
            try:
                self.client.disconnect()
            except Exception:
                pass
            self.client = None
        self.is_connected = False
        logger.info(
            "Updated PLCManager config: IP=%s, Rack=%d, Slot=%d, DB=%d, Simulator=%s",
            self.plc_ip, self.rack, self.slot, self.db_number, self.simulator_mode
        )


    def _connect_plc(self) -> bool:
        """Establishes connection to Siemens S7-1200 PLC with exponential backoff on failure."""
        if not SNAP7_AVAILABLE:
            logger.warning("Snap7 library unavailable; remaining in simulator mode.")
            self.is_connected = False
            return False

        import time
        now = time.time()
        if now < self._next_reconnect_time:
            return False  # Exponential backoff cool-down in effect

        try:
            if self.client is None:
                self.client = snap7.client.Client()
                try:
                    self.client.set_connection_params(self.plc_ip, self.rack, self.slot)
                except Exception:
                    pass

            if not self.client.get_connected():
                logger.info(
                    "Connecting/Reconnecting to Siemens S7-1200 PLC at %s (Rack: %d, Slot: %d, DB: %d, Attempt: %d)...",
                    self.plc_ip,
                    self.rack,
                    self.slot,
                    self.db_number,
                    self._reconnect_attempts + 1,
                )
                try:
                    self.client.disconnect()
                except Exception:
                    pass
                self.client.connect(self.plc_ip, self.rack, self.slot)

            self.is_connected = self.client.get_connected()
            if self.is_connected:
                logger.info("✅ PLC S7-1200 connected successfully (%s, DB%d)", self.plc_ip, self.db_number)
                self._reconnect_attempts = 0
                self._next_reconnect_time = 0.0
            else:
                self._reconnect_attempts += 1
                backoff_delay = min(2 ** self._reconnect_attempts, 16)
                self._next_reconnect_time = now + backoff_delay
                logger.error("❌ Failed to connect to PLC S7-1200 (%s). Retrying in %ds...", self.plc_ip, backoff_delay)
        except Exception as e:
            self._reconnect_attempts += 1
            backoff_delay = min(2 ** self._reconnect_attempts, 16)
            self._next_reconnect_time = now + backoff_delay
            logger.error("❌ Exception during PLC Snap7 connection: %s. Retrying in %ds...", str(e), backoff_delay)
            self.is_connected = False

        return self.is_connected

    # ----------------------------------------------------------------
    # DB15 Read/Write helpers (wrapped in asyncio.to_thread + lock for safety)
    # ----------------------------------------------------------------

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _sync_db_read(self, start: int, size: int) -> bytes:
        """Synchronous DB read — runs in thread pool via asyncio.to_thread."""
        return self.client.db_read(self.db_number, start, size)

    def _sync_db_write(self, start: int, data: bytearray) -> None:
        """Synchronous DB write — runs in thread pool via asyncio.to_thread."""
        self.client.db_write(self.db_number, start, data)

    async def _async_db_read(self, start: int, size: int) -> bytes:
        """Non-blocking DB read using thread pool with async lock to prevent concurrent socket access."""
        async with self._get_lock():
            return await asyncio.to_thread(self._sync_db_read, start, size)

    async def _async_db_write(self, start: int, data: bytearray) -> None:
        """Non-blocking DB write using thread pool with async lock to prevent concurrent socket access."""
        async with self._get_lock():
            await asyncio.to_thread(self._sync_db_write, start, data)

    # ----------------------------------------------------------------
    # Read PLC status bits (Byte 1 only — no raw sensor reading)
    # ----------------------------------------------------------------
    # Read PLC status bits (Byte 2: DB15.DBX2.x)
    # ----------------------------------------------------------------

    async def read_plc_status(self) -> None:
        """Reads DB15 Byte 2 status bits from PLC (non-blocking).
        Backend reads PLC's high-level status & limit switch signals.
        """
        if self.simulator_mode or not self.is_connected or self.client is None:
            return

        try:
            # Read 3 bytes from DB15: Byte 0 (cmd), Byte 1 (unused), Byte 2 (status)
            data = await self._async_db_read(0, 3)

            self.drone_detected = get_bool(data, OFFSET_DRONE_DETECTED[0], OFFSET_DRONE_DETECTED[1])
            self.plc_locked_state = get_bool(data, OFFSET_PLC_LOCKED_STATE[0], OFFSET_PLC_LOCKED_STATE[1])
            self.drone_locked = self.plc_locked_state
            self.plc_z_is_up = get_bool(data, OFFSET_PLC_Z_IS_UP[0], OFFSET_PLC_Z_IS_UP[1])
            self.plc_z_is_down = get_bool(data, OFFSET_PLC_Z_IS_DOWN[0], OFFSET_PLC_Z_IS_DOWN[1])
            self.plc_on = get_bool(data, OFFSET_PLC_ON[0], OFFSET_PLC_ON[1])
            self.plc_error = get_bool(data, OFFSET_PLC_ERROR[0], OFFSET_PLC_ERROR[1])
            self.emergency_stop = get_bool(data, OFFSET_E_STOP[0], OFFSET_E_STOP[1])

            if self.plc_z_is_up:
                self.z_axis = "UP"
                self.plc_busy = False
            elif self.plc_z_is_down:
                self.z_axis = "DOWN"
                self.plc_busy = False
            else:
                if self.plc_busy:
                    self.z_axis = "MOVING"
                else:
                    self.z_axis = "DOWN"
                    self.plc_busy = False

        except Exception as e:
            logger.error("Error reading PLC DB%d status: %s", self.db_number, str(e))
            self.is_connected = False
            if self.client:
                try:
                    self.client.disconnect()
                except Exception:
                    pass

    # ----------------------------------------------------------------
    # Handshake: Send command (Byte 0) + poll status (Byte 2)
    # ----------------------------------------------------------------

    async def _send_command_and_wait(
        self,
        cmd: PLCCommand,
        timeout: float = DEFAULT_HANDSHAKE_TIMEOUT,
    ) -> bool:
        """Core execution: write command bit to Byte 0, then poll Byte 2 for target state flag.

        Target State Criteria:
          - LOCK_DRONE   -> plc_locked_state == True (DB15.DBX2.1)
          - UNLOCK_DRONE -> plc_locked_state == False (DB15.DBX2.1)
          - Z_UP         -> plc_z_is_up == True (DB15.DBX2.2)
          - Z_DOWN       -> plc_z_is_down == True (DB15.DBX2.3)
          - START_PLC    -> plc_on == True (DB15.DBX2.4)
          - STOP_PLC     -> plc_on == False (DB15.DBX2.4)
          - RESET_PLC    -> plc_error == False (DB15.DBX2.5)

        Returns True if target state reached within timeout, False on timeout.
        """
        if not self.is_connected or self.client is None:
            return False

        try:
            # Step 1: Read Byte 0 and set the target command bit
            write_data = bytearray(await self._async_db_read(0, 1))

            # Clear all command bits first (Byte 0: DB15.DBX0.0..6)
            set_bool(write_data, 0, OFFSET_CMD_LOCK[1], False)
            set_bool(write_data, 0, OFFSET_CMD_UNLOCK[1], False)
            set_bool(write_data, 0, OFFSET_CMD_Z_UP[1], False)
            set_bool(write_data, 0, OFFSET_CMD_Z_DOWN[1], False)
            set_bool(write_data, 0, OFFSET_CMD_STOP[1], False)
            set_bool(write_data, 0, OFFSET_CMD_START[1], False)
            set_bool(write_data, 0, OFFSET_CMD_RESET[1], False)

            # Set requested command bit
            if cmd == PLCCommand.LOCK_DRONE:
                set_bool(write_data, 0, OFFSET_CMD_LOCK[1], True)
            elif cmd == PLCCommand.UNLOCK_DRONE:
                set_bool(write_data, 0, OFFSET_CMD_UNLOCK[1], True)
            elif cmd == PLCCommand.Z_UP:
                set_bool(write_data, 0, OFFSET_CMD_Z_UP[1], True)
            elif cmd == PLCCommand.Z_DOWN:
                set_bool(write_data, 0, OFFSET_CMD_Z_DOWN[1], True)
            elif cmd == PLCCommand.STOP_PLC:
                set_bool(write_data, 0, OFFSET_CMD_STOP[1], True)
            elif cmd == PLCCommand.START_PLC:
                set_bool(write_data, 0, OFFSET_CMD_START[1], True)
            elif cmd == PLCCommand.RESET_PLC:
                set_bool(write_data, 0, OFFSET_CMD_RESET[1], True)

            # Step 2: Write command to PLC DB15 Byte 0
            await self._async_db_write(0, write_data)
            logger.info("PLC Command: Sent %s to DB15 Byte 0", cmd.value)

            # Step 3: Poll DB15 Byte 2 for target status flag
            elapsed = 0.0
            while elapsed < timeout:
                await asyncio.sleep(DEFAULT_POLL_INTERVAL)
                elapsed += DEFAULT_POLL_INTERVAL

                status_data = await self._async_db_read(0, 3)

                plc_locked = get_bool(status_data, OFFSET_PLC_LOCKED_STATE[0], OFFSET_PLC_LOCKED_STATE[1])
                plc_z_up = get_bool(status_data, OFFSET_PLC_Z_IS_UP[0], OFFSET_PLC_Z_IS_UP[1])
                plc_z_down = get_bool(status_data, OFFSET_PLC_Z_IS_DOWN[0], OFFSET_PLC_Z_IS_DOWN[1])
                plc_on = get_bool(status_data, OFFSET_PLC_ON[0], OFFSET_PLC_ON[1])
                plc_err = get_bool(status_data, OFFSET_PLC_ERROR[0], OFFSET_PLC_ERROR[1])
                is_estop = get_bool(status_data, OFFSET_E_STOP[0], OFFSET_E_STOP[1])

                if is_estop:
                    logger.error("PLC Command: EMERGENCY STOP triggered during %s", cmd.value)
                    break

                # Target state verification
                is_target_reached = (
                    (cmd == PLCCommand.LOCK_DRONE and plc_locked) or
                    (cmd == PLCCommand.UNLOCK_DRONE and not plc_locked) or
                    (cmd == PLCCommand.Z_UP and plc_z_up) or
                    (cmd == PLCCommand.Z_DOWN and plc_z_down) or
                    (cmd == PLCCommand.START_PLC and plc_on) or
                    (cmd == PLCCommand.STOP_PLC and not plc_on) or
                    (cmd == PLCCommand.RESET_PLC and not plc_err)
                )

                if is_target_reached:
                    logger.info("PLC Command %s COMPLETED (Status verified in %.1fs)", cmd.value, elapsed)

                    # Step 4: Clear command bits in Byte 0
                    reset_data = bytearray(await self._async_db_read(0, 1))
                    set_bool(reset_data, 0, OFFSET_CMD_LOCK[1], False)
                    set_bool(reset_data, 0, OFFSET_CMD_UNLOCK[1], False)
                    set_bool(reset_data, 0, OFFSET_CMD_Z_UP[1], False)
                    set_bool(reset_data, 0, OFFSET_CMD_Z_DOWN[1], False)
                    set_bool(reset_data, 0, OFFSET_CMD_STOP[1], False)
                    set_bool(reset_data, 0, OFFSET_CMD_START[1], False)
                    set_bool(reset_data, 0, OFFSET_CMD_RESET[1], False)
                    await self._async_db_write(0, reset_data)
                    return True

            # Timeout — clear command bit anyway
            logger.warning("PLC Command: Timeout (%.1fs) waiting for status flag on %s", timeout, cmd.value)
            reset_data = bytearray(await self._async_db_read(0, 1))
            set_bool(reset_data, 0, OFFSET_CMD_LOCK[1], False)
            set_bool(reset_data, 0, OFFSET_CMD_UNLOCK[1], False)
            set_bool(reset_data, 0, OFFSET_CMD_Z_UP[1], False)
            set_bool(reset_data, 0, OFFSET_CMD_Z_DOWN[1], False)
            set_bool(reset_data, 0, OFFSET_CMD_STOP[1], False)
            set_bool(reset_data, 0, OFFSET_CMD_START[1], False)
            set_bool(reset_data, 0, OFFSET_CMD_RESET[1], False)
            await self._async_db_write(0, reset_data)
            return False

        except Exception as e:
            logger.error("PLC Handshake: Exception during %s: %s", cmd.value, str(e))
            self.is_connected = False
            if self.client:
                try:
                    self.client.disconnect()
                except Exception:
                    pass
            return False

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    async def check_connection(self) -> bool:
        """Health check: try to read 1 byte from PLC to verify TCP connection is alive.
        If disconnected, attempts to auto-reconnect via thread pool.
        Updates is_connected accordingly. Called periodically from heartbeat task.
        """
        if self.simulator_mode:
            return True

        if not SNAP7_AVAILABLE:
            self.is_connected = False
            return False

        # If currently marked disconnected or client lost connection, attempt reconnect
        if not self.is_connected or self.client is None or not self.client.get_connected():
            was_connected = self.is_connected
            connected = await asyncio.to_thread(self._connect_plc)
            if not connected:
                self.is_connected = False
                return False
            if not was_connected:
                logger.info("✅ PLC S7-1200 auto-reconnected successfully (%s)", self.plc_ip)

        try:
            # Test connection & refresh cached status from DB15
            await self.read_plc_status()
            self.is_connected = True
            return True
        except Exception as e:
            if self.is_connected:
                logger.warning("❌ PLC S7-1200 connection lost (%s): %s", self.plc_ip, str(e))
            self.is_connected = False
            if self.client:
                try:
                    self.client.disconnect()
                except Exception:
                    pass
            return False

    def get_status(self) -> PLCStatusResponse:
        return PLCStatusResponse(
            drone_detected=self.drone_detected,
            plc_locked_state=self.plc_locked_state or self.drone_locked,
            drone_locked=self.drone_locked or self.plc_locked_state,
            plc_z_is_up=self.plc_z_is_up or (self.z_axis == "UP"),
            plc_z_is_down=self.plc_z_is_down or (self.z_axis == "DOWN"),
            plc_on=self.plc_on,
            plc_error=self.plc_error,
            emergency_stop=self.emergency_stop,
            z_axis=self.z_axis,
            connected=self.is_connected if not self.simulator_mode else True,
            simulator_mode=self.simulator_mode,
            plc_busy=self.plc_busy,
        )

    async def execute_command(self, cmd: PLCCommand) -> PLCStatusResponse:
        """Execute a PLC command using Handshake Signal Protocol.

        Flow:
          1. Send command bit (Byte 0)
          2. Wait for PLC status bit update (Byte 2)
          3. Update cached state
          4. Return status
        """
        logger.info("Executing PLC command: %s (DB%d, Simulator Mode: %s)", cmd.value, self.db_number, self.simulator_mode)

        if self.simulator_mode or not SNAP7_AVAILABLE:
            return await self._execute_simulator_command(cmd)

        # Real PLC execution via handshake
        if not self.is_connected:
            self._connect_plc()
            if not self.is_connected:
                logger.warning("PLC connection failed. Falling back to simulator mode for command %s", cmd.value)
                return await self._execute_simulator_command(cmd)

        # Update intermediate state
        if cmd in (PLCCommand.LOCK_DRONE, PLCCommand.START_PLC, PLCCommand.STOP_PLC, PLCCommand.RESET_PLC):
            self.plc_busy = True
        elif cmd == PLCCommand.Z_UP or cmd == PLCCommand.Z_DOWN:
            self.z_axis = "MOVING"
            self.plc_z_is_up = False
            self.plc_z_is_down = False
            self.plc_busy = True

        # Execute handshake
        success = await self._send_command_and_wait(cmd)

        if success:
            # Update cached state based on completed command
            if cmd == PLCCommand.START_PLC:
                self.plc_on = True
                self.plc_error = False
                logger.info("PLC Real (DB15): System started / enabled via DB15.DBX0.5")
            elif cmd == PLCCommand.STOP_PLC:
                self.plc_on = False
                logger.info("PLC Real (DB15): System stopped via DB15.DBX0.4")
            elif cmd == PLCCommand.RESET_PLC:
                self.plc_error = False
                self.emergency_stop = False
                self.plc_on = True
                logger.info("PLC Real (DB15): Error reset via DB15.DBX0.6")
            elif cmd == PLCCommand.LOCK_DRONE:
                self.plc_locked_state = True
                self.drone_locked = True
                logger.info("PLC Real (DB15): Drone locked successfully via DB15.DBX0.0")
            elif cmd == PLCCommand.UNLOCK_DRONE:
                self.plc_locked_state = False
                self.drone_locked = False
                # Note: drone_detected remains TRUE because drone is still sitting on dock until takeoff/departure event
                logger.info("PLC Real (DB15): Drone unlocked via DB15.DBX0.1 (drone_detected maintained until departure)")
            elif cmd == PLCCommand.Z_UP:
                self.z_axis = "UP"
                self.plc_z_is_up = True
                self.plc_z_is_down = False
                logger.info("PLC Real (DB15): Lift Z-axis moved to UP position via DB15.DBX0.2")
            elif cmd == PLCCommand.Z_DOWN:
                self.z_axis = "DOWN"
                self.plc_z_is_up = False
                self.plc_z_is_down = True
                logger.info("PLC Real (DB15): Lift Z-axis moved to DOWN position via DB15.DBX0.3")
            self.plc_busy = False
            self.plc_error = False
        else:
            # Handshake failed (timeout or error) — keep actual DB15 state & set error flag
            logger.warning("PLC Handshake failed for %s — status target not reached or timeout", cmd.value)
            self.plc_busy = False
            self.plc_error = True
            # Refresh actual status from PLC DB15
            await self.read_plc_status()

        status_res = self.get_status()
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(system_ws_manager.broadcast("PLC_STATUS", status_res.model_dump()))
        except RuntimeError:
            pass

        return status_res

    async def _execute_simulator_command(self, cmd: PLCCommand) -> PLCStatusResponse:
        """Fallback / simulator command execution logic."""
        if cmd == PLCCommand.START_PLC:
            self.plc_on = True
            self.plc_error = False
            logger.info("PLC [Sim]: System started / enabled (plc_on = True)")

        elif cmd == PLCCommand.STOP_PLC:
            self.plc_on = False
            self.plc_busy = False
            logger.info("PLC [Sim]: System stopped (plc_on = False)")

        elif cmd == PLCCommand.RESET_PLC:
            self.plc_error = False
            self.emergency_stop = False
            self.plc_on = True
            logger.info("PLC [Sim]: Error reset completed")

        elif cmd == PLCCommand.LOCK_DRONE:
            self.plc_busy = True
            await asyncio.sleep(0.5)  # Simulate mechanical clamp movement
            self.plc_locked_state = True
            self.drone_locked = True
            self.plc_busy = False
            logger.info("PLC [Sim]: Drone locked successfully")

        elif cmd == PLCCommand.UNLOCK_DRONE:
            self.plc_locked_state = False
            self.drone_locked = False
            # Note: drone_detected remains TRUE until UAV departure event
            logger.info("PLC [Sim]: Drone unlocked and clamps released")

        elif cmd == PLCCommand.Z_UP:
            self.z_axis = "MOVING"
            self.plc_z_is_up = False
            self.plc_z_is_down = False
            self.plc_busy = True
            await asyncio.sleep(0.3)
            self.z_axis = "UP"
            self.plc_z_is_up = True
            self.plc_z_is_down = False
            self.plc_busy = False
            logger.info("PLC [Sim]: Lift Z-axis moved to UP position")

        elif cmd == PLCCommand.Z_DOWN:
            self.z_axis = "MOVING"
            self.plc_z_is_up = False
            self.plc_z_is_down = False
            self.plc_busy = True
            await asyncio.sleep(0.3)
            self.z_axis = "DOWN"
            self.plc_z_is_up = False
            self.plc_z_is_down = True
            self.plc_busy = False
            logger.info("PLC [Sim]: Lift Z-axis moved to DOWN position")

        status_res = self.get_status()
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(system_ws_manager.broadcast("PLC_STATUS", status_res.model_dump()))
        except RuntimeError:
            pass

        return status_res

    async def wait_for_status(
        self,
        status_key: str,
        target_value: bool,
        timeout_sec: float = 5.0,
        poll_interval: float = 0.15,
    ) -> None:
        """Wait for a PLC status attribute to reach the target value.

        Used by StationService for the 11-step FSM handshake protocol:
            Command → Execute → Feedback → Next Step

        In simulator mode, the execute_command method already sets the
        target status synchronously, so this will return almost immediately.
        In real hardware mode, it polls the cached PLC state (updated by
        read_plc_status) until the target value is reached or timeout occurs.

        Args:
            status_key: Name of the cached boolean attribute
                        (e.g. 'drone_detected', 'plc_locked_state',
                         'plc_z_is_up', 'plc_z_is_down').
            target_value: The boolean value to wait for.
            timeout_sec: Maximum wait time in seconds before raising TimeoutError.
            poll_interval: Seconds between polling attempts.

        Raises:
            TimeoutError: If target value is not reached within timeout_sec.
            AttributeError: If status_key is not a valid PLC attribute.
        """
        if not hasattr(self, status_key):
            raise AttributeError(
                f"PLCManager has no status attribute '{status_key}'. "
                f"Valid keys: drone_detected, plc_locked_state, plc_z_is_up, "
                f"plc_z_is_down, plc_on, plc_error, emergency_stop"
            )

        elapsed = 0.0
        while elapsed < timeout_sec:
            current_value = getattr(self, status_key)
            if current_value == target_value:
                logger.debug(
                    "PLC wait_for_status('%s'=%s) satisfied after %.2fs",
                    status_key, target_value, elapsed,
                )
                return
            # In real hardware mode, refresh status from PLC DB15
            if not self.simulator_mode and self.is_connected:
                try:
                    await self.read_plc_status()
                except Exception as e:
                    logger.warning("Error reading PLC status during wait: %s", e)
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        # Timeout reached — raise error for StationService to handle
        current_value = getattr(self, status_key)
        raise TimeoutError(
            f"PLC wait_for_status('{status_key}'={target_value}) timed out after {timeout_sec}s. "
            f"Current value: {current_value}"
        )

    def set_drone_detected(self, detected: bool) -> None:
        self.drone_detected = detected
        logger.info("PLC Sensor: Drone detection set to %s", detected)


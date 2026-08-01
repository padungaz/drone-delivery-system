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
#   0.0: cmd_lock_drone       - Lệnh khóa kẹp Drone
#   0.1: cmd_unlock_drone     - Lệnh mở khóa kẹp Drone
#   0.2: cmd_z_up             - Lệnh nâng trục Z lên
#   0.3: cmd_z_down           - Lệnh hạ trục Z xuống
#   0.4: backend_heartbeat    - Tín hiệu sống Backend (toggle)
#   0.5: cmd_req_strobe       - Xung kích hoạt lệnh mới (set=1 khi gửi lệnh, reset=0 sau khi nhận DONE)
#   0.6: (reserved)
#   0.7: (reserved)
#
# Byte 1: PLC -> Backend (Status & Done bits, read-only by Backend)
#   1.0: plc_busy             - PLC đang thực thi lệnh
#   1.1: plc_done             - PLC hoàn thành lệnh hiện tại
#   1.2: plc_error            - PLC gặp lỗi khi thực thi
#   1.3: emergency_stop       - Nút dừng khẩn cấp được nhấn
#   1.4: plc_locked_state     - Trạng thái: Drone đang bị khóa
#   1.5: plc_z_is_up          - Trạng thái: Trục Z đang ở vị trí trên
#   1.6: plc_z_is_down        - Trạng thái: Trục Z đang ở vị trí dưới
#   1.7: plc_heartbeat        - Tín hiệu sống PLC (toggle)
#
# ========================================================================================

# Byte 0: Backend -> PLC (Command bits & Drone Detection Sensor)
OFFSET_CMD_LOCK          = (0, 0)  # cmd_lock_drone: Bool 0.0
OFFSET_CMD_UNLOCK        = (0, 1)  # cmd_unlock_drone: Bool 0.1
OFFSET_CMD_Z_UP          = (0, 2)  # cmd_z_up: Bool 0.2
OFFSET_CMD_Z_DOWN        = (0, 3)  # cmd_z_down: Bool 0.3
OFFSET_BACKEND_HEARTBEAT = (0, 4)  # backend_heartbeat: Bool 0.4
OFFSET_DRONE_DETECTED    = (0, 5)  # drone_detected: Bool 0.5 sensor

# Byte 1: PLC -> Backend (Status & Limit Switch State bits)
OFFSET_PLC_LOCKED_STATE  = (1, 0)  # plc_locked_state: Bool 1.0 (1 = Locked)
OFFSET_PLC_Z_IS_UP       = (1, 1)  # plc_z_is_up: Bool 1.1 (1 = Z at Top)
OFFSET_PLC_Z_IS_DOWN     = (1, 2)  # plc_z_is_down: Bool 1.2 (1 = Z at Bottom)
OFFSET_E_STOP            = (1, 3)  # emergency_stop: Bool 1.3
OFFSET_PLC_HEARTBEAT     = (1, 4)  # plc_heartbeat: Bool 1.4

# Handshake timing defaults
DEFAULT_HANDSHAKE_TIMEOUT = 25.0   # Seconds to wait for PLC DONE / Limit Flag signal (allows mechanical stroke time)
DEFAULT_POLL_INTERVAL     = 0.15   # Seconds between DB reads during wait


class PLCManager:
    """Manager for PLC Siemens S7-1200 Docking Station (DB15 Handshake Protocol).

    Architecture: Event-Driven Handshake Signal Protocol
    ====================================================
    Backend (Master Orchestrator) sends command bits to PLC via DB15 Byte 0.
    PLC autonomously executes the full mechanical sequence (clamps, Z-axis, sensors)
    and signals completion via plc_done bit in DB15 Byte 1.

    Backend does NOT read raw sensors (limit switches, clamp states).
    PLC owns the closed-loop mechanical control.

    Handshake Sequence:
      1. Backend sets command bit(s) + cmd_req_strobe = True -> writes to DB15 Byte 0
      2. PLC reads strobe, begins execution, sets plc_busy = True, plc_done = False
      3. PLC completes mechanical action, sets plc_done = True, plc_busy = False
      4. Backend detects plc_done = True, resets cmd_req_strobe = False + command bits
      5. Cycle complete. Ready for next command.
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

        # Cached states (updated from PLC status bits or simulator)
        self.drone_detected: bool = False
        self.drone_locked: bool = False
        self.z_axis: str = "HOME"       # "HOME", "UP", "DOWN", "MOVING"
        self.emergency_stop: bool = False
        self.plc_heartbeat: bool = False
        self.plc_busy: bool = False
        self.plc_error: bool = False

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

    def _connect_plc(self) -> bool:
        """Establishes connection to Siemens S7-1200 PLC."""
        if not SNAP7_AVAILABLE:
            logger.warning("Snap7 library unavailable; remaining in simulator mode.")
            self.is_connected = False
            return False

        try:
            if self.client is None:
                self.client = snap7.client.Client()
                # Try to set longer TCP timeouts (may not be available in all snap7 versions)
                try:
                    self.client.set_connection_params(self.plc_ip, self.rack, self.slot)
                except Exception:
                    pass  # Pure Python snap7 may not support this

            if not self.client.get_connected():
                logger.info(
                    "Connecting/Reconnecting to Siemens S7-1200 PLC at %s (Rack: %d, Slot: %d, DB: %d)...",
                    self.plc_ip,
                    self.rack,
                    self.slot,
                    self.db_number,
                )
                try:
                    self.client.disconnect()
                except Exception:
                    pass
                self.client.connect(self.plc_ip, self.rack, self.slot)

            self.is_connected = self.client.get_connected()
            if self.is_connected:
                logger.info("✅ PLC S7-1200 connected successfully (%s, DB%d)", self.plc_ip, self.db_number)
            else:
                logger.error("❌ Failed to connect to PLC S7-1200 (%s)", self.plc_ip)
        except Exception as e:
            logger.error("❌ Exception during PLC Snap7 connection: %s", str(e))
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

    async def read_plc_status(self) -> None:
        """Reads DB15 Byte 1 status bits from PLC (non-blocking).
        Backend reads PLC's high-level status & limit switch signals.
        """
        if self.simulator_mode or not self.is_connected or self.client is None:
            return

        try:
            data = await self._async_db_read(0, 2)

            self.drone_detected = get_bool(data, OFFSET_DRONE_DETECTED[0], OFFSET_DRONE_DETECTED[1])
            self.emergency_stop = get_bool(data, OFFSET_E_STOP[0], OFFSET_E_STOP[1])
            self.plc_heartbeat = get_bool(data, OFFSET_PLC_HEARTBEAT[0], OFFSET_PLC_HEARTBEAT[1])

            # State indicators (limit switch flags)
            plc_locked = get_bool(data, OFFSET_PLC_LOCKED_STATE[0], OFFSET_PLC_LOCKED_STATE[1])
            plc_z_up = get_bool(data, OFFSET_PLC_Z_IS_UP[0], OFFSET_PLC_Z_IS_UP[1])
            plc_z_down = get_bool(data, OFFSET_PLC_Z_IS_DOWN[0], OFFSET_PLC_Z_IS_DOWN[1])

            self.drone_locked = plc_locked
            if plc_z_up:
                self.z_axis = "UP"
                self.plc_busy = False
            elif plc_z_down:
                self.z_axis = "DOWN"
                self.plc_busy = False
            else:
                # Neither limit switch is active: mark MOVING only if a command is currently active
                if self.plc_busy:
                    self.z_axis = "MOVING"
                else:
                    self.z_axis = "DOWN"
                    self.plc_busy = False

            self.plc_error = False

        except Exception as e:
            logger.error("Error reading PLC DB%d status: %s", self.db_number, str(e))
            self.is_connected = False
            if self.client:
                try:
                    self.client.disconnect()
                except Exception:
                    pass

    # ----------------------------------------------------------------
    # Streamlined Handshake: Send command + wait for Target Limit Flag
    # ----------------------------------------------------------------

    async def _send_command_and_wait(
        self,
        cmd: PLCCommand,
        timeout: float = DEFAULT_HANDSHAKE_TIMEOUT,
    ) -> bool:
        """Core execution: write command bit to Byte 0, then poll Byte 1 for target state flag.

        Target State Criteria:
          - LOCK_DRONE   -> plc_locked_state == True
          - UNLOCK_DRONE -> plc_locked_state == False
          - Z_UP         -> plc_z_is_up == True
          - Z_DOWN       -> plc_z_is_down == True

        Returns True if target state reached within timeout, False on timeout.
        """
        if not self.is_connected or self.client is None:
            return False

        try:
            # Step 1: Read Byte 0 and set the target command bit
            write_data = bytearray(await self._async_db_read(0, 1))

            # Clear all command bits first
            set_bool(write_data, 0, OFFSET_CMD_LOCK[1], False)
            set_bool(write_data, 0, OFFSET_CMD_UNLOCK[1], False)
            set_bool(write_data, 0, OFFSET_CMD_Z_UP[1], False)
            set_bool(write_data, 0, OFFSET_CMD_Z_DOWN[1], False)

            # Set requested command bit
            if cmd == PLCCommand.LOCK_DRONE:
                set_bool(write_data, 0, OFFSET_CMD_LOCK[1], True)
            elif cmd == PLCCommand.UNLOCK_DRONE:
                set_bool(write_data, 0, OFFSET_CMD_UNLOCK[1], True)
            elif cmd == PLCCommand.Z_UP:
                set_bool(write_data, 0, OFFSET_CMD_Z_UP[1], True)
            elif cmd == PLCCommand.Z_DOWN:
                set_bool(write_data, 0, OFFSET_CMD_Z_DOWN[1], True)

            # Step 2: Write command to PLC
            await self._async_db_write(0, write_data)
            logger.info("PLC Command: Sent %s to DB15 Byte 0", cmd.value)

            # Step 3: Poll Byte 1 for target limit switch flag
            elapsed = 0.0
            while elapsed < timeout:
                await asyncio.sleep(DEFAULT_POLL_INTERVAL)
                elapsed += DEFAULT_POLL_INTERVAL

                status_data = await self._async_db_read(0, 2)

                plc_locked = get_bool(status_data, OFFSET_PLC_LOCKED_STATE[0], OFFSET_PLC_LOCKED_STATE[1])
                plc_z_up = get_bool(status_data, OFFSET_PLC_Z_IS_UP[0], OFFSET_PLC_Z_IS_UP[1])
                plc_z_down = get_bool(status_data, OFFSET_PLC_Z_IS_DOWN[0], OFFSET_PLC_Z_IS_DOWN[1])
                is_estop = get_bool(status_data, OFFSET_E_STOP[0], OFFSET_E_STOP[1])

                if is_estop:
                    logger.error("PLC Command: EMERGENCY STOP triggered during %s", cmd.value)
                    break

                # Target state verification
                is_target_reached = (
                    (cmd == PLCCommand.LOCK_DRONE and plc_locked) or
                    (cmd == PLCCommand.UNLOCK_DRONE and not plc_locked) or
                    (cmd == PLCCommand.Z_UP and plc_z_up) or
                    (cmd == PLCCommand.Z_DOWN and plc_z_down)
                )

                if is_target_reached:
                    logger.info("PLC Command %s COMPLETED (Limit flag verified in %.1fs)", cmd.value, elapsed)

                    # Step 4: Clear command bits in Byte 0
                    reset_data = bytearray(await self._async_db_read(0, 1))
                    set_bool(reset_data, 0, OFFSET_CMD_LOCK[1], False)
                    set_bool(reset_data, 0, OFFSET_CMD_UNLOCK[1], False)
                    set_bool(reset_data, 0, OFFSET_CMD_Z_UP[1], False)
                    set_bool(reset_data, 0, OFFSET_CMD_Z_DOWN[1], False)
                    await self._async_db_write(0, reset_data)
                    return True

            # Timeout — clear command bit anyway
            logger.warning("PLC Command: Timeout (%.1fs) waiting for limit flag on %s", timeout, cmd.value)
            reset_data = bytearray(await self._async_db_read(0, 1))
            set_bool(reset_data, 0, OFFSET_CMD_LOCK[1], False)
            set_bool(reset_data, 0, OFFSET_CMD_UNLOCK[1], False)
            set_bool(reset_data, 0, OFFSET_CMD_Z_UP[1], False)
            set_bool(reset_data, 0, OFFSET_CMD_Z_DOWN[1], False)
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
            drone_locked=self.drone_locked,
            z_axis=self.z_axis,
            emergency_stop=self.emergency_stop,
            connected=self.is_connected if not self.simulator_mode else True,
            simulator_mode=self.simulator_mode,
            plc_busy=self.plc_busy,
            plc_error=self.plc_error,
        )

    async def execute_command(self, cmd: PLCCommand) -> PLCStatusResponse:
        """Execute a PLC command using Handshake Signal Protocol.

        Flow:
          1. Send command bits + strobe to PLC
          2. Wait for PLC to report DONE (plc_done bit or target state bit)
          3. Update cached state
          4. Return status

        In simulator mode, mechanical delays are simulated.
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
        if cmd == PLCCommand.LOCK_DRONE:
            self.plc_busy = True
        elif cmd == PLCCommand.Z_UP or cmd == PLCCommand.Z_DOWN:
            self.z_axis = "MOVING"
            self.plc_busy = True

        # Execute handshake
        success = await self._send_command_and_wait(cmd)

        if success:
            # Update cached state based on completed command
            if cmd == PLCCommand.LOCK_DRONE:
                self.drone_locked = True
                logger.info("PLC Real (DB15): Drone locked successfully via handshake")
            elif cmd == PLCCommand.UNLOCK_DRONE:
                self.drone_locked = False
                self.drone_detected = False
                logger.info("PLC Real (DB15): Drone unlocked and clamps released via handshake")
            elif cmd == PLCCommand.Z_UP:
                self.z_axis = "UP"
                logger.info("PLC Real (DB15): Lift Z-axis moved to UP position via handshake")
            elif cmd == PLCCommand.Z_DOWN:
                self.z_axis = "DOWN"
                logger.info("PLC Real (DB15): Lift Z-axis moved to DOWN position via handshake")
            self.plc_busy = False
            self.plc_error = False
        else:
            # Handshake failed (timeout or error) — keep actual DB15 state & set error flag
            logger.warning("PLC Handshake failed for %s — limit switch target not reached or timeout", cmd.value)
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
        if cmd == PLCCommand.LOCK_DRONE:
            self.plc_busy = True
            await asyncio.sleep(0.5)  # Simulate mechanical clamp movement
            self.drone_locked = True
            self.plc_busy = False
            logger.info("PLC [Sim]: Drone locked successfully")

        elif cmd == PLCCommand.UNLOCK_DRONE:
            self.drone_locked = False
            self.drone_detected = False
            logger.info("PLC [Sim]: Drone unlocked and clamps released")

        elif cmd == PLCCommand.Z_UP:
            self.z_axis = "MOVING"
            self.plc_busy = True
            await asyncio.sleep(0.3)
            self.z_axis = "UP"
            self.plc_busy = False
            logger.info("PLC [Sim]: Lift Z-axis moved to UP position")

        elif cmd == PLCCommand.Z_DOWN:
            self.z_axis = "MOVING"
            self.plc_busy = True
            await asyncio.sleep(0.3)
            self.z_axis = "DOWN"
            self.plc_busy = False
            logger.info("PLC [Sim]: Lift Z-axis moved to DOWN position")

        status_res = self.get_status()
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(system_ws_manager.broadcast("PLC_STATUS", status_res.model_dump()))
        except RuntimeError:
            pass

        return status_res

    def set_drone_detected(self, detected: bool) -> None:
        self.drone_detected = detected
        logger.info("PLC Sensor: Drone detection set to %s", detected)

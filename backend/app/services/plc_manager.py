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

# PLC Connection Defaults (Siemens S7-1200 - Snap7 DB15 Protocol)
DEFAULT_PLC_IP = "192.168.58.10"
DEFAULT_RACK = 0
DEFAULT_SLOT = 1
DEFAULT_DB_NUMBER = 15

# ========================================================================================
# DB15 Handshake Protocol Mapping (Siemens S7-1200 Docking Station & Smart Warehouse)
# ========================================================================================
#
# Byte 0: Backend -> PLC (Station Command bits, written by Backend)
#   0.0: cmd_lock_drone           - Yêu cầu PLC kích hoạt cơ cấu khóa cố định Drone
#   0.1: cmd_unlock_drone         - Yêu cầu PLC mở khóa, giải phóng Drone
#   0.2: cmd_z_up                 - Yêu cầu PLC điều khiển trục Z nâng lên
#   0.3: cmd_z_down               - Yêu cầu PLC điều khiển trục Z hạ xuống
#   0.4: cmd_stop_plc             - Yêu cầu PLC dừng chu trình hoạt động
#   0.5: cmd_start_plc            - Yêu cầu PLC khởi động / cho phép hệ thống hoạt động
#   0.6: cmd_reset_plc            - Yêu cầu PLC reset lỗi và đưa hệ thống về trạng thái sẵn sàng
#   0.7: watchdog_heartbeat       - Watchdog toggle từ Backend (1s)
#
# Byte 1: Backend -> PLC (Staff Mode & Conveyor Commands, written by Backend)
#   1.0: cmd_staff_mode_enable    - Kích hoạt Chế độ Nhân viên (1 = Staff Mode, 0 = Station Auto)
#   1.1: cmd_staff_outbound_start - Bắt đầu chu trình Lấy hàng ra Băng tải
#   1.2: cmd_staff_outbound_cancel- Hủy chu trình Lấy hàng ra Băng tải
#   1.3: cmd_staff_inbound_start  - Bắt đầu chu trình Thêm hàng từ O1 vào Kho
#   1.4: cmd_staff_inbound_stop   - Dừng chu trình Thêm hàng
#   1.5: cmd_conveyor_run         - Điều khiển Băng tải chạy thủ công
#   1.6: cmd_conveyor_stop        - Điều khiển Băng tải dừng thủ công
#   1.7: (reserved)
#
# Byte 2: PLC -> Backend (Station Status bits, read-only by Backend)
#   2.0: drone_detected           - PLC phát hiện Drone đã hạ cánh đúng vị trí Dock
#   2.1: plc_locked_state         - Trạng thái cơ cấu khóa Drone đã hoàn thành
#   2.2: plc_z_is_up              - Trạng thái trục Z đã nâng đến vị trí trên
#   2.3: plc_z_is_down            - Trạng thái trục Z đã hạ về vị trí ban đầu
#   2.4: plc_on                   - PLC đang hoạt động và sẵn sàng nhận lệnh
#   2.5: plc_error                - PLC phát hiện lỗi trong quá trình vận hành
#   2.6: emergency_stop           - Trạng thái nút dừng khẩn cấp được kích hoạt
#   2.7: (reserved)
#
# Byte 3: PLC -> Backend (Staff Mode & Conveyor Status bits, read-only by Backend)
#   3.0: sensor_conveyor_head     - Cảm biến 1: Đầu băng tải (Vị trí Robot & Điểm O1) có hàng
#   3.1: sensor_conveyor_end      - Cảm biến 2: Cuối băng tải (Vị trí Nhân viên) có hàng
#   3.2: conveyor_running         - Trạng thái Động cơ Băng tải đang RUN
#   3.3: staff_outbound_busy      - PLC đang trong chu trình xuất hàng ra băng tải
#   3.4: staff_outbound_done      - PLC đã xuất xong toàn bộ danh sách hàng ra băng tải
#   3.5: staff_inbound_busy       - PLC đang trong chu trình thêm hàng
#   3.6: staff_inbound_done       - PLC đã kết thúc thêm hàng
#   3.7: staff_mode_active        - PLC xác nhận đang ở Chế độ Nhân viên (Staff Mode)
#
# ========================================================================================

# Byte 0: Backend -> PLC (Station Commands)
OFFSET_CMD_LOCK               = (0, 0)  # cmd_lock_drone: Bool 0.0
OFFSET_CMD_UNLOCK             = (0, 1)  # cmd_unlock_drone: Bool 0.1
OFFSET_CMD_Z_UP               = (0, 2)  # cmd_z_up: Bool 0.2
OFFSET_CMD_Z_DOWN             = (0, 3)  # cmd_z_down: Bool 0.3
OFFSET_CMD_STOP               = (0, 4)  # cmd_stop_plc: Bool 0.4
OFFSET_CMD_START              = (0, 5)  # cmd_start_plc: Bool 0.5
OFFSET_CMD_RESET              = (0, 6)  # cmd_reset_plc: Bool 0.6
OFFSET_CMD_WATCHDOG           = (0, 7)  # watchdog_heartbeat: Bool 0.7

# Byte 1: Backend -> PLC (Staff Mode & Conveyor Commands)
OFFSET_CMD_STAFF_ENABLE       = (1, 0)  # cmd_staff_mode_enable: Bool 1.0
OFFSET_CMD_STAFF_OUT_START    = (1, 1)  # cmd_staff_outbound_start: Bool 1.1
OFFSET_CMD_STAFF_OUT_CANCEL   = (1, 2)  # cmd_staff_outbound_cancel: Bool 1.2
OFFSET_CMD_STAFF_IN_START     = (1, 3)  # cmd_staff_inbound_start: Bool 1.3
OFFSET_CMD_STAFF_IN_STOP      = (1, 4)  # cmd_staff_inbound_stop: Bool 1.4
OFFSET_CMD_CONVEYOR_RUN       = (1, 5)  # cmd_conveyor_run: Bool 1.5
OFFSET_CMD_CONVEYOR_STOP      = (1, 6)  # cmd_conveyor_stop: Bool 1.6

# Byte 2: PLC -> Backend (Station Status bits)
OFFSET_DRONE_DETECTED         = (2, 0)  # drone_detected: Bool 2.0
OFFSET_PLC_LOCKED_STATE       = (2, 1)  # plc_locked_state: Bool 2.1
OFFSET_PLC_Z_IS_UP            = (2, 2)  # plc_z_is_up: Bool 2.2
OFFSET_PLC_Z_IS_DOWN          = (2, 3)  # plc_z_is_down: Bool 2.3
OFFSET_PLC_ON                 = (2, 4)  # plc_on: Bool 2.4
OFFSET_PLC_ERROR              = (2, 5)  # plc_error: Bool 2.5
OFFSET_E_STOP                 = (2, 6)  # emergency_stop: Bool 2.6

# Byte 3: PLC -> Backend (Staff Mode & Conveyor Status bits)
OFFSET_SENSOR_CONVEYOR_HEAD   = (3, 0)  # sensor_conveyor_head: Bool 3.0 (Cảm biến đầu / O1)
OFFSET_SENSOR_CONVEYOR_END    = (3, 1)  # sensor_conveyor_end: Bool 3.1 (Cảm biến cuối)
OFFSET_CONVEYOR_RUNNING       = (3, 2)  # conveyor_running: Bool 3.2
OFFSET_STAFF_OUTBOUND_BUSY    = (3, 3)  # staff_outbound_busy: Bool 3.3
OFFSET_STAFF_OUTBOUND_DONE    = (3, 4)  # staff_outbound_done: Bool 3.4
OFFSET_STAFF_INBOUND_BUSY     = (3, 5)  # staff_inbound_busy: Bool 3.5
OFFSET_STAFF_INBOUND_DONE     = (3, 6)  # staff_inbound_done: Bool 3.6
OFFSET_STAFF_MODE_ACTIVE      = (3, 7)  # staff_mode_active: Bool 3.7

# DB15 Words (Int16) for Staff Quantity Handshake
OFFSET_STAFF_TARGET_COUNT     = 4       # DB15.DBW4 (Int16 - Số lượng Backend yêu cầu PLC)
OFFSET_STAFF_CURRENT_COUNT    = 6       # DB15.DBW6 (Int16 - Số lượng PLC đã đếm được)

# Handshake timing defaults
DEFAULT_HANDSHAKE_TIMEOUT = 25.0   # Seconds to wait for target status signal
DEFAULT_POLL_INTERVAL     = 0.15   # Seconds between DB reads during wait

# Watchdog configuration
WATCHDOG_INTERVAL_SEC     = 1.0    # Toggle DB15.DBX0.7 every 1 second
# Note: Set env PLC_WATCHDOG_ENABLED=true only after PLC S7-1200 program has
# a matching TON watchdog timer on bit DB15.DBX0.7 (recommended 3s timeout).


class PLCManager:
    """Manager for PLC Siemens S7-1200 Docking Station (DB15 Protocol Mapping).

    Architecture: Event-Driven Signal Protocol
    ==========================================
    Backend (Master Orchestrator) sends command bits to PLC via DB15 Byte 0 & Byte 1.
    PLC autonomously executes the physical sequence and updates status bits in DB15 Byte 2 & Byte 3.
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

        # Cached states (updated from PLC DB15 Byte 2 & Byte 3 status bits or simulator)
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

        # Staff Mode & Conveyor cached states (DB15 Byte 3 & Words 4, 6)
        self.sensor_conveyor_head: bool = False  # DB15.DBX3.0
        self.sensor_conveyor_end: bool = False   # DB15.DBX3.1
        self.conveyor_running: bool = False      # DB15.DBX3.2
        self.staff_outbound_busy: bool = False   # DB15.DBX3.3
        self.staff_outbound_done: bool = False   # DB15.DBX3.4
        self.staff_inbound_busy: bool = False    # DB15.DBX3.5
        self.staff_inbound_done: bool = False    # DB15.DBX3.6
        self.staff_mode_active: bool = False     # DB15.DBX3.7
        self.staff_target_count: int = 0         # DB15.DBW4
        self.staff_current_count: int = 0        # DB15.DBW6

        # Watchdog state
        self._watchdog_bit: bool = False       # Current toggle state of bit 0.7
        self._watchdog_task: Optional[asyncio.Task] = None
        self.watchdog_active: bool = False     # True while watchdog task is running

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
    # Read PLC status bits (Byte 2: Station Status & Byte 3: Staff/Conveyor Status)
    # ----------------------------------------------------------------

    async def read_plc_status(self) -> None:
        """Reads DB15 Byte 2 & Byte 3 status bits and Words 4, 6 from PLC (non-blocking)."""
        if self.simulator_mode or not self.is_connected or self.client is None:
            return

        try:
            # Read 8 bytes from DB15: Bytes 0-3 (flags), Words 4-5 (target count), Words 6-7 (current count)
            data = await self._async_db_read(0, 8)

            # Byte 2: Station status
            self.drone_detected = get_bool(data, OFFSET_DRONE_DETECTED[0], OFFSET_DRONE_DETECTED[1])
            self.plc_locked_state = get_bool(data, OFFSET_PLC_LOCKED_STATE[0], OFFSET_PLC_LOCKED_STATE[1])
            self.drone_locked = self.plc_locked_state
            self.plc_z_is_up = get_bool(data, OFFSET_PLC_Z_IS_UP[0], OFFSET_PLC_Z_IS_UP[1])
            self.plc_z_is_down = get_bool(data, OFFSET_PLC_Z_IS_DOWN[0], OFFSET_PLC_Z_IS_DOWN[1])
            self.plc_on = get_bool(data, OFFSET_PLC_ON[0], OFFSET_PLC_ON[1])
            self.plc_error = get_bool(data, OFFSET_PLC_ERROR[0], OFFSET_PLC_ERROR[1])
            self.emergency_stop = get_bool(data, OFFSET_E_STOP[0], OFFSET_E_STOP[1])

            # Byte 3: Staff & Conveyor status
            self.sensor_conveyor_head = get_bool(data, OFFSET_SENSOR_CONVEYOR_HEAD[0], OFFSET_SENSOR_CONVEYOR_HEAD[1])
            self.sensor_conveyor_end = get_bool(data, OFFSET_SENSOR_CONVEYOR_END[0], OFFSET_SENSOR_CONVEYOR_END[1])
            self.conveyor_running = get_bool(data, OFFSET_CONVEYOR_RUNNING[0], OFFSET_CONVEYOR_RUNNING[1])
            self.staff_outbound_busy = get_bool(data, OFFSET_STAFF_OUTBOUND_BUSY[0], OFFSET_STAFF_OUTBOUND_BUSY[1])
            self.staff_outbound_done = get_bool(data, OFFSET_STAFF_OUTBOUND_DONE[0], OFFSET_STAFF_OUTBOUND_DONE[1])
            self.staff_inbound_busy = get_bool(data, OFFSET_STAFF_INBOUND_BUSY[0], OFFSET_STAFF_INBOUND_BUSY[1])
            self.staff_inbound_done = get_bool(data, OFFSET_STAFF_INBOUND_DONE[0], OFFSET_STAFF_INBOUND_DONE[1])
            self.staff_mode_active = get_bool(data, OFFSET_STAFF_MODE_ACTIVE[0], OFFSET_STAFF_MODE_ACTIVE[1])

            if len(data) >= 8:
                import struct
                self.staff_target_count = struct.unpack(">h", data[4:6])[0]
                self.staff_current_count = struct.unpack(">h", data[6:8])[0]

            if self.plc_z_is_up:
                self.z_axis = "UP"
                self.plc_busy = False
            elif self.plc_z_is_down:
                self.z_axis = "DOWN"
                self.plc_busy = False
            else:
                self.z_axis = "MOVING"

        except Exception as e:
            logger.error("Error reading PLC DB%d status: %s", self.db_number, str(e))
            self.is_connected = False
            if self.client:
                try:
                    self.client.disconnect()
                except Exception:
                    pass

    async def set_staff_target_count(self, count: int) -> None:
        """Writes target item count to PLC DB15.DBW4 (Int16) for autonomous PLC counting."""
        self.staff_target_count = max(0, count)
        self.staff_current_count = 0
        logger.info("PLC Staff Quantity: Target count set to %d (current reset to 0)", self.staff_target_count)

        if not self.simulator_mode and self.is_connected and self.client:
            try:
                import struct
                packed_val = struct.pack(">h", self.staff_target_count)
                await self._async_db_write(OFFSET_STAFF_TARGET_COUNT, bytearray(packed_val))
                logger.info("PLC DB15.DBW4: Written target count %d to PLC", self.staff_target_count)
            except Exception as err:
                logger.error("Failed to write target count to PLC DB15.DBW4: %s", err)

    async def increment_staff_count(self) -> int:
        """Increments current count in PLC/simulator and checks if target is reached."""
        self.staff_current_count += 1
        logger.info("PLC Staff Quantity: Count incremented -> %d / %d", self.staff_current_count, self.staff_target_count)

        if not self.simulator_mode and self.is_connected and self.client:
            try:
                import struct
                packed_val = struct.pack(">h", self.staff_current_count)
                await self._async_db_write(OFFSET_STAFF_CURRENT_COUNT, bytearray(packed_val))
            except Exception as err:
                logger.error("Failed to write current count to PLC DB15.DBW6: %s", err)

        if self.staff_target_count > 0 and self.staff_current_count >= self.staff_target_count:
            if self.staff_outbound_busy:
                self.staff_outbound_busy = False
                self.staff_outbound_done = True
                logger.info("🎉 PLC Staff Outbound completed target quantity (%d items)!", self.staff_target_count)
            elif self.staff_inbound_busy:
                self.staff_inbound_busy = False
                self.staff_inbound_done = True
                logger.info("🎉 PLC Staff Inbound completed target quantity (%d items)!", self.staff_target_count)

        return self.staff_current_count

    # ----------------------------------------------------------------
    # Handshake: Send command (Byte 0 & 1) + poll status (Byte 2 & 3)
    # ----------------------------------------------------------------

    async def _send_command_and_wait(
        self,
        cmd: PLCCommand,
        timeout: float = DEFAULT_HANDSHAKE_TIMEOUT,
    ) -> bool:
        """Core execution: write command bit to Byte 0 or Byte 1, then poll Byte 2 / Byte 3 for target state flag."""
        if not self.is_connected or self.client is None:
            return False

        try:
            # Step 1: Read Byte 0 & Byte 1
            cmd_data = bytearray(await self._async_db_read(0, 2))

            # Determine whether this is a Byte 0 (Station) or Byte 1 (Staff) command
            is_staff_cmd = cmd in (
                PLCCommand.STAFF_MODE_ENABLE,
                PLCCommand.STAFF_MODE_DISABLE,
                PLCCommand.STAFF_OUTBOUND_START,
                PLCCommand.STAFF_OUTBOUND_CANCEL,
                PLCCommand.STAFF_INBOUND_START,
                PLCCommand.STAFF_INBOUND_STOP,
                PLCCommand.CONVEYOR_RUN,
                PLCCommand.CONVEYOR_STOP,
            )

            if not is_staff_cmd:
                # Clear Station command bits (Byte 0)
                set_bool(cmd_data, 0, OFFSET_CMD_LOCK[1], False)
                set_bool(cmd_data, 0, OFFSET_CMD_UNLOCK[1], False)
                set_bool(cmd_data, 0, OFFSET_CMD_Z_UP[1], False)
                set_bool(cmd_data, 0, OFFSET_CMD_Z_DOWN[1], False)
                set_bool(cmd_data, 0, OFFSET_CMD_STOP[1], False)
                set_bool(cmd_data, 0, OFFSET_CMD_START[1], False)
                set_bool(cmd_data, 0, OFFSET_CMD_RESET[1], False)

                # Set requested Station command bit
                if cmd == PLCCommand.LOCK_DRONE:
                    set_bool(cmd_data, 0, OFFSET_CMD_LOCK[1], True)
                elif cmd == PLCCommand.UNLOCK_DRONE:
                    set_bool(cmd_data, 0, OFFSET_CMD_UNLOCK[1], True)
                elif cmd == PLCCommand.Z_UP:
                    set_bool(cmd_data, 0, OFFSET_CMD_Z_UP[1], True)
                elif cmd == PLCCommand.Z_DOWN:
                    set_bool(cmd_data, 0, OFFSET_CMD_Z_DOWN[1], True)
                elif cmd == PLCCommand.STOP_PLC:
                    set_bool(cmd_data, 0, OFFSET_CMD_STOP[1], True)
                elif cmd == PLCCommand.START_PLC:
                    set_bool(cmd_data, 0, OFFSET_CMD_START[1], True)
                elif cmd == PLCCommand.RESET_PLC:
                    set_bool(cmd_data, 0, OFFSET_CMD_RESET[1], True)
            else:
                # Clear Staff command bits (Byte 1)
                set_bool(cmd_data, 1, OFFSET_CMD_STAFF_ENABLE[1], False)
                set_bool(cmd_data, 1, OFFSET_CMD_STAFF_OUT_START[1], False)
                set_bool(cmd_data, 1, OFFSET_CMD_STAFF_OUT_CANCEL[1], False)
                set_bool(cmd_data, 1, OFFSET_CMD_STAFF_IN_START[1], False)
                set_bool(cmd_data, 1, OFFSET_CMD_STAFF_IN_STOP[1], False)
                set_bool(cmd_data, 1, OFFSET_CMD_CONVEYOR_RUN[1], False)
                set_bool(cmd_data, 1, OFFSET_CMD_CONVEYOR_STOP[1], False)

                # Set requested Staff command bit
                if cmd == PLCCommand.STAFF_MODE_ENABLE:
                    set_bool(cmd_data, 1, OFFSET_CMD_STAFF_ENABLE[1], True)
                elif cmd == PLCCommand.STAFF_MODE_DISABLE:
                    set_bool(cmd_data, 1, OFFSET_CMD_STAFF_ENABLE[1], False)
                elif cmd == PLCCommand.STAFF_OUTBOUND_START:
                    set_bool(cmd_data, 1, OFFSET_CMD_STAFF_OUT_START[1], True)
                elif cmd == PLCCommand.STAFF_OUTBOUND_CANCEL:
                    set_bool(cmd_data, 1, OFFSET_CMD_STAFF_OUT_CANCEL[1], True)
                elif cmd == PLCCommand.STAFF_INBOUND_START:
                    set_bool(cmd_data, 1, OFFSET_CMD_STAFF_IN_START[1], True)
                elif cmd == PLCCommand.STAFF_INBOUND_STOP:
                    set_bool(cmd_data, 1, OFFSET_CMD_STAFF_IN_STOP[1], True)
                elif cmd == PLCCommand.CONVEYOR_RUN:
                    set_bool(cmd_data, 1, OFFSET_CMD_CONVEYOR_RUN[1], True)
                elif cmd == PLCCommand.CONVEYOR_STOP:
                    set_bool(cmd_data, 1, OFFSET_CMD_CONVEYOR_STOP[1], True)

            # Step 2: Write command bytes to PLC DB15
            await self._async_db_write(0, cmd_data)
            logger.info("PLC Command: Sent %s to DB15 (Byte %d)", cmd.value, 1 if is_staff_cmd else 0)

            # Step 3: Poll DB15 Byte 2 & Byte 3 for target status flag
            elapsed = 0.0
            while elapsed < timeout:
                await asyncio.sleep(DEFAULT_POLL_INTERVAL)
                elapsed += DEFAULT_POLL_INTERVAL

                status_data = await self._async_db_read(0, 4)

                plc_locked = get_bool(status_data, OFFSET_PLC_LOCKED_STATE[0], OFFSET_PLC_LOCKED_STATE[1])
                plc_z_up = get_bool(status_data, OFFSET_PLC_Z_IS_UP[0], OFFSET_PLC_Z_IS_UP[1])
                plc_z_down = get_bool(status_data, OFFSET_PLC_Z_IS_DOWN[0], OFFSET_PLC_Z_IS_DOWN[1])
                plc_on = get_bool(status_data, OFFSET_PLC_ON[0], OFFSET_PLC_ON[1])
                plc_err = get_bool(status_data, OFFSET_PLC_ERROR[0], OFFSET_PLC_ERROR[1])
                is_estop = get_bool(status_data, OFFSET_E_STOP[0], OFFSET_E_STOP[1])

                staff_active = get_bool(status_data, OFFSET_STAFF_MODE_ACTIVE[0], OFFSET_STAFF_MODE_ACTIVE[1])
                conveyor_run = get_bool(status_data, OFFSET_CONVEYOR_RUNNING[0], OFFSET_CONVEYOR_RUNNING[1])
                out_busy = get_bool(status_data, OFFSET_STAFF_OUTBOUND_BUSY[0], OFFSET_STAFF_OUTBOUND_BUSY[1])
                in_busy = get_bool(status_data, OFFSET_STAFF_INBOUND_BUSY[0], OFFSET_STAFF_INBOUND_BUSY[1])

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
                    (cmd == PLCCommand.RESET_PLC and not plc_err) or
                    (cmd == PLCCommand.STAFF_MODE_ENABLE and staff_active) or
                    (cmd == PLCCommand.STAFF_MODE_DISABLE and not staff_active) or
                    (cmd == PLCCommand.CONVEYOR_RUN and conveyor_run) or
                    (cmd == PLCCommand.CONVEYOR_STOP and not conveyor_run) or
                    (cmd == PLCCommand.STAFF_OUTBOUND_START and out_busy) or
                    (cmd == PLCCommand.STAFF_OUTBOUND_CANCEL and not out_busy) or
                    (cmd == PLCCommand.STAFF_INBOUND_START and in_busy) or
                    (cmd == PLCCommand.STAFF_INBOUND_STOP and not in_busy)
                )

                if is_target_reached:
                    logger.info("PLC Command %s COMPLETED (Status verified in %.1fs)", cmd.value, elapsed)

                    # Step 4: Clear pulse command bits in Byte 0 / Byte 1
                    reset_data = bytearray(await self._async_db_read(0, 2))
                    if not is_staff_cmd:
                        set_bool(reset_data, 0, OFFSET_CMD_LOCK[1], False)
                        set_bool(reset_data, 0, OFFSET_CMD_UNLOCK[1], False)
                        set_bool(reset_data, 0, OFFSET_CMD_Z_UP[1], False)
                        set_bool(reset_data, 0, OFFSET_CMD_Z_DOWN[1], False)
                        set_bool(reset_data, 0, OFFSET_CMD_STOP[1], False)
                        set_bool(reset_data, 0, OFFSET_CMD_START[1], False)
                        set_bool(reset_data, 0, OFFSET_CMD_RESET[1], False)
                    else:
                        set_bool(reset_data, 1, OFFSET_CMD_STAFF_OUT_START[1], False)
                        set_bool(reset_data, 1, OFFSET_CMD_STAFF_OUT_CANCEL[1], False)
                        set_bool(reset_data, 1, OFFSET_CMD_STAFF_IN_START[1], False)
                        set_bool(reset_data, 1, OFFSET_CMD_STAFF_IN_STOP[1], False)
                        set_bool(reset_data, 1, OFFSET_CMD_CONVEYOR_RUN[1], False)
                        set_bool(reset_data, 1, OFFSET_CMD_CONVEYOR_STOP[1], False)

                    await self._async_db_write(0, reset_data)
                    return True

            # Timeout — clear pulse command bits anyway
            logger.warning("PLC Command: Timeout (%.1fs) waiting for status flag on %s", timeout, cmd.value)
            reset_data = bytearray(await self._async_db_read(0, 2))
            set_bool(reset_data, 0, OFFSET_CMD_LOCK[1], False)
            set_bool(reset_data, 0, OFFSET_CMD_UNLOCK[1], False)
            set_bool(reset_data, 0, OFFSET_CMD_Z_UP[1], False)
            set_bool(reset_data, 0, OFFSET_CMD_Z_DOWN[1], False)
            set_bool(reset_data, 0, OFFSET_CMD_STOP[1], False)
            set_bool(reset_data, 0, OFFSET_CMD_START[1], False)
            set_bool(reset_data, 0, OFFSET_CMD_RESET[1], False)
            set_bool(reset_data, 1, OFFSET_CMD_STAFF_OUT_START[1], False)
            set_bool(reset_data, 1, OFFSET_CMD_STAFF_OUT_CANCEL[1], False)
            set_bool(reset_data, 1, OFFSET_CMD_STAFF_IN_START[1], False)
            set_bool(reset_data, 1, OFFSET_CMD_STAFF_IN_STOP[1], False)
            set_bool(reset_data, 1, OFFSET_CMD_CONVEYOR_RUN[1], False)
            set_bool(reset_data, 1, OFFSET_CMD_CONVEYOR_STOP[1], False)
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
        """Health check: try to read 1 byte from PLC to verify TCP connection is alive."""
        if self.simulator_mode:
            return True

        if not SNAP7_AVAILABLE:
            self.is_connected = False
            return False

        if not self.is_connected or self.client is None or not self.client.get_connected():
            was_connected = self.is_connected
            connected = await asyncio.to_thread(self._connect_plc)
            if not connected:
                self.is_connected = False
                return False
            if not was_connected:
                logger.info("✅ PLC S7-1200 auto-reconnected successfully (%s)", self.plc_ip)

        try:
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
            watchdog_active=self.watchdog_active,
            sensor_conveyor_head=self.sensor_conveyor_head,
            sensor_conveyor_end=self.sensor_conveyor_end,
            conveyor_running=self.conveyor_running,
            staff_outbound_busy=self.staff_outbound_busy,
            staff_outbound_done=self.staff_outbound_done,
            staff_inbound_busy=self.staff_inbound_busy,
            staff_inbound_done=self.staff_inbound_done,
            staff_mode_active=self.staff_mode_active,
            staff_target_count=self.staff_target_count,
            staff_current_count=self.staff_current_count,
        )

    async def execute_command(self, cmd: PLCCommand) -> PLCStatusResponse:
        """Execute a PLC command using Handshake Signal Protocol."""
        logger.info("Executing PLC command: %s (DB%d, Simulator Mode: %s)", cmd.value, self.db_number, self.simulator_mode)

        if self.simulator_mode or not SNAP7_AVAILABLE:
            return await self._execute_simulator_command(cmd)

        if not self.is_connected:
            self._connect_plc()
            if not self.is_connected:
                logger.error("❌ PLC S7-1200 connection failed at %s. Cannot execute %s in Real Hardware Mode.", self.plc_ip, cmd.value)
                raise ConnectionError(f"PLC Siemens S7-1200 ({self.plc_ip}) chưa được kết nối! Vui lòng kiểm tra cáp mạng LAN hoặc chuyển sang Simulator Mode.")

        # Update intermediate state
        if cmd in (PLCCommand.LOCK_DRONE, PLCCommand.START_PLC, PLCCommand.STOP_PLC, PLCCommand.RESET_PLC):
            self.plc_busy = True
        elif cmd in (PLCCommand.Z_UP, PLCCommand.Z_DOWN):
            self.z_axis = "MOVING"
            self.plc_z_is_up = False
            self.plc_z_is_down = False
            self.plc_busy = True
        elif cmd in (PLCCommand.STAFF_OUTBOUND_START, PLCCommand.STAFF_INBOUND_START):
            self.plc_busy = True

        # Execute handshake
        success = await self._send_command_and_wait(cmd)

        if success:
            if cmd == PLCCommand.START_PLC:
                self.plc_on = True
                self.plc_error = False
            elif cmd == PLCCommand.STOP_PLC:
                self.plc_on = False
            elif cmd == PLCCommand.RESET_PLC:
                self.plc_error = False
                self.emergency_stop = False
                self.plc_on = True
            elif cmd == PLCCommand.LOCK_DRONE:
                self.plc_locked_state = True
                self.drone_locked = True
            elif cmd == PLCCommand.UNLOCK_DRONE:
                self.plc_locked_state = False
                self.drone_locked = False
            elif cmd == PLCCommand.Z_UP:
                self.z_axis = "UP"
                self.plc_z_is_up = True
                self.plc_z_is_down = False
            elif cmd == PLCCommand.Z_DOWN:
                self.z_axis = "DOWN"
                self.plc_z_is_up = False
                self.plc_z_is_down = True
            elif cmd == PLCCommand.STAFF_MODE_ENABLE:
                self.staff_mode_active = True
            elif cmd == PLCCommand.STAFF_MODE_DISABLE:
                self.staff_mode_active = False
            elif cmd == PLCCommand.CONVEYOR_RUN:
                self.conveyor_running = True
            elif cmd == PLCCommand.CONVEYOR_STOP:
                self.conveyor_running = False
            elif cmd == PLCCommand.STAFF_OUTBOUND_START:
                self.staff_outbound_busy = True
                self.staff_outbound_done = False
            elif cmd == PLCCommand.STAFF_OUTBOUND_CANCEL:
                self.staff_outbound_busy = False
            elif cmd == PLCCommand.STAFF_INBOUND_START:
                self.staff_inbound_busy = True
                self.staff_inbound_done = False
            elif cmd == PLCCommand.STAFF_INBOUND_STOP:
                self.staff_inbound_busy = False
                self.staff_inbound_done = True
            self.plc_busy = False
            self.plc_error = False
        else:
            logger.warning("PLC Handshake failed for %s — status target not reached or timeout", cmd.value)
            self.plc_busy = False
            self.plc_error = True
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
            await asyncio.sleep(0.5)
            self.plc_locked_state = True
            self.drone_locked = True
            self.plc_busy = False
            logger.info("PLC [Sim]: Drone locked successfully")

        elif cmd == PLCCommand.UNLOCK_DRONE:
            self.plc_locked_state = False
            self.drone_locked = False
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

        # Staff Mode & Conveyor Commands in Simulator
        elif cmd == PLCCommand.STAFF_MODE_ENABLE:
            self.staff_mode_active = True
            logger.info("PLC [Sim]: Staff Mode Enabled (staff_mode_active = True)")

        elif cmd == PLCCommand.STAFF_MODE_DISABLE:
            self.staff_mode_active = False
            logger.info("PLC [Sim]: Staff Mode Disabled (staff_mode_active = False)")

        elif cmd == PLCCommand.CONVEYOR_RUN:
            self.conveyor_running = True
            logger.info("PLC [Sim]: Conveyor motor RUNNING (conveyor_running = True)")

        elif cmd == PLCCommand.CONVEYOR_STOP:
            self.conveyor_running = False
            logger.info("PLC [Sim]: Conveyor motor STOPPED (conveyor_running = False)")

        elif cmd == PLCCommand.STAFF_OUTBOUND_START:
            self.staff_outbound_busy = True
            self.staff_outbound_done = False
            logger.info("PLC [Sim]: Staff Outbound cycle started (staff_outbound_busy = True)")

        elif cmd == PLCCommand.STAFF_OUTBOUND_CANCEL:
            self.staff_outbound_busy = False
            logger.info("PLC [Sim]: Staff Outbound cycle cancelled")

        elif cmd == PLCCommand.STAFF_INBOUND_START:
            self.staff_inbound_busy = True
            self.staff_inbound_done = False
            logger.info("PLC [Sim]: Staff Inbound cycle started (staff_inbound_busy = True)")

        elif cmd == PLCCommand.STAFF_INBOUND_STOP:
            self.staff_inbound_busy = False
            self.staff_inbound_done = True
            logger.info("PLC [Sim]: Staff Inbound cycle stopped (staff_inbound_done = True)")

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

    # ----------------------------------------------------------------
    # Watchdog Heartbeat (DB15.DBX0.7)
    # ----------------------------------------------------------------

    async def _watchdog_loop(self) -> None:
        """Background coroutine: toggle DB15.DBX0.7 every WATCHDOG_INTERVAL_SEC.

        The PLC S7-1200 should have a TON timer monitoring this bit.
        If the bit stops toggling for >3s, the PLC should trigger a safe stop.
        NOTE: Enable only after the PLC program has matching Watchdog logic.
        """
        logger.info("PLC Watchdog: Heartbeat task started (interval=%.1fs, bit=DB15.DBX0.7)", WATCHDOG_INTERVAL_SEC)
        try:
            while True:
                await asyncio.sleep(WATCHDOG_INTERVAL_SEC)
                if not self.is_connected or self.client is None or self.simulator_mode:
                    continue
                try:
                    self._watchdog_bit = not self._watchdog_bit
                    async with self._get_lock():
                        write_data = bytearray(await asyncio.to_thread(self._sync_db_read, 0, 1))
                        set_bool(write_data, 0, OFFSET_CMD_WATCHDOG[1], self._watchdog_bit)
                        await asyncio.to_thread(self._sync_db_write, 0, write_data)
                except Exception as e:
                    logger.debug("PLC Watchdog: Write failed (connection may be down): %s", e)
        except asyncio.CancelledError:
            # Clean up: clear watchdog bit on exit
            if self.is_connected and self.client is not None and not self.simulator_mode:
                try:
                    async with self._get_lock():
                        write_data = bytearray(await asyncio.to_thread(self._sync_db_read, 0, 1))
                        set_bool(write_data, 0, OFFSET_CMD_WATCHDOG[1], False)
                        await asyncio.to_thread(self._sync_db_write, 0, write_data)
                except Exception:
                    pass
            logger.info("PLC Watchdog: Heartbeat task stopped")
            self.watchdog_active = False

    async def start_watchdog(self) -> None:
        """Start the Watchdog heartbeat background task.

        Called from FastAPI lifespan when PLC_WATCHDOG_ENABLED=true.
        Safe to call multiple times — skips if already running.
        """
        if self._watchdog_task is not None and not self._watchdog_task.done():
            logger.debug("PLC Watchdog: Already running, skipping start.")
            return
        self._watchdog_task = asyncio.create_task(self._watchdog_loop(), name="plc_watchdog")
        self.watchdog_active = True
        logger.info("PLC Watchdog: Task created (DB15.DBX0.7).")

    async def stop_watchdog(self) -> None:
        """Stop the Watchdog heartbeat background task gracefully.

        Called from FastAPI lifespan shutdown. Clears the watchdog bit in PLC.
        """
        if self._watchdog_task is not None and not self._watchdog_task.done():
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
        self._watchdog_task = None
        self.watchdog_active = False

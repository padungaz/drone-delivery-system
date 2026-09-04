import asyncio
import logging
import os
import threading
import time
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
#   0.2: (Reserved - Thay thế bằng DB15.DBW8 target_z_level)
#   0.3: (Reserved - Thay thế bằng DB15.DBW8 target_z_level)
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
#   1.5: (reserved - PLC tự quản lý động cơ băng tải)
#   1.6: (reserved - PLC tự quản lý động cơ băng tải)
#   1.7: (reserved)
#
# Byte 2: PLC -> Backend (Station Status bits, read-only by Backend)
#   2.0: drone_detected           - PLC phát hiện Drone đã hạ cánh đúng vị trí Dock
#   2.1: plc_locked_state         - Trạng thái cơ cấu khóa Drone đã hoàn thành
#   2.2: (Reserved - Thay thế bằng DB15.DBX2.7 plc_z_in_position)
#   2.3: (Reserved - Thay thế bằng DB15.DBX2.7 plc_z_in_position)
#   2.4: plc_on                   - PLC đang hoạt động và sẵn sàng nhận lệnh
#   2.5: plc_error                - PLC phát hiện lỗi trong quá trình vận hành
#   2.6: emergency_stop           - Trạng thái nút dừng khẩn cấp được kích hoạt
#   2.7: plc_z_in_position       - PLC báo trục Z đã đến đúng tầng mục tiêu và đứng yên sẵn sàng
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
OFFSET_CMD_TARGET_Z           = (0, 2)  # cmd_target_z: Bool 0.2 (Kích hoạt chạy trục Z đến tầng DBW8)
# Bit 0.3: Reserved
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
# (DB15.DBX1.5 & 1.6: Reserved - PLC tự điều khiển động cơ băng tải nội bộ)

# Byte 2: PLC -> Backend (Station Status bits)
OFFSET_DRONE_DETECTED         = (2, 0)  # drone_detected: Bool 2.0
OFFSET_PLC_LOCKED_STATE       = (2, 1)  # plc_locked_state: Bool 2.1
# Bits 2.2 & 2.3: Reserved (Thay thế bằng DB15.DBX2.7 plc_z_in_position)
OFFSET_PLC_ON                 = (2, 4)  # plc_on: Bool 2.4
OFFSET_PLC_ERROR              = (2, 5)  # plc_error: Bool 2.5
OFFSET_E_STOP                 = (2, 6)  # emergency_stop: Bool 2.6
OFFSET_PLC_Z_IN_POSITION      = (2, 7)  # plc_z_in_position: Bool 2.7 (Z đã đến tầng mục tiêu)

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

# DB15 Word (Int16) for Z-Axis Multi-Level Control
OFFSET_CMD_TARGET_Z_LEVEL     = 8       # DB15.DBW8 (Int16 - Backend ghi mã tầng Z mục tiêu)

# Z Level Integer Mapping
Z_LEVEL_HOME      = 0   # Vị trí gốc / nghỉ
Z_LEVEL_ROW_A     = 1   # Tầng A (ô A1, A2, A3)
Z_LEVEL_ROW_B     = 2   # Tầng B (ô B1, B2, B3)
Z_LEVEL_DOCK_N    = 3   # Bãi đáp Drone (N1)
Z_LEVEL_CONVEYOR  = 4   # Đầu băng tải (O1)

Z_LEVEL_LABELS = {
    Z_LEVEL_HOME: "HOME",
    Z_LEVEL_ROW_A: "HÀNG A",
    Z_LEVEL_ROW_B: "HÀNG B",
    Z_LEVEL_DOCK_N: "DRONE N1",
    Z_LEVEL_CONVEYOR: "BĂNG TẢI O1",
}


def slot_to_z_level(slot: Optional[str]) -> int:
    """Convert a slot name (A1, B2, N1, O1, etc.) to the corresponding Z level integer code."""
    if not slot:
        return Z_LEVEL_HOME
    s = slot.upper().strip()
    if s.startswith("A"):
        return Z_LEVEL_ROW_A
    elif s.startswith("B"):
        return Z_LEVEL_ROW_B
    elif s in ("N1", "DOCK", "PAD", "PAD_N1"):
        return Z_LEVEL_DOCK_N
    elif s in ("O1", "CONVEYOR"):
        return Z_LEVEL_CONVEYOR
    return Z_LEVEL_HOME

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
        self._conn_lock = threading.Lock()

        # Cached states (updated from PLC DB15 Byte 2 & Byte 3 status bits or simulator)
        self.drone_detected: bool = False
        self.plc_locked_state: bool = False
        self.drone_locked: bool = False       # Alias for plc_locked_state
        self.plc_on: bool = True              # Active & ready by default
        self.plc_error: bool = False
        self.emergency_stop: bool = False
        self.z_axis: str = "HOME"             # "HOME", "HÀNG A", "HÀNG B", "DRONE N1", "BĂNG TẢI O1", "MOVING"
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
        self.cmd_staff_outbound_cancel: bool = False  # DB15.DBX1.2 (Cờ lệnh Hủy xuất hàng)
        self.cmd_staff_inbound_stop: bool = False     # DB15.DBX1.4 (Cờ lệnh Dừng nạp hàng)

        # Z-Axis Multi-Level Control (DB15.DBW8 + DB15.DBX2.7 + DB15.DBX0.2)
        self.cmd_target_z: bool = False          # DB15.DBX0.2 - Lệnh kích hoạt chạy trục Z
        self.plc_z_in_position: bool = True      # DB15.DBX2.7 - Z đã sẵn sàng tại tầng mục tiêu
        self.target_z_level: int = 0              # Mã tầng Z Backend yêu cầu (ghi vào DB15.DBW8)
        self.current_z_level: int = 0             # Mã tầng Z hiện tại PLC phản hồi

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

        with self._conn_lock:
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
        """Reads DB15 Bytes 0-9 status bits, Words 4/6/8 from PLC (non-blocking)."""
        if self.simulator_mode or not self.is_connected or self.client is None:
            return

        try:
            # Read 10 bytes from DB15: Bytes 0-3 (flags), Words 4-5 (target count), Words 6-7 (current count), Words 8-9 (Z level)
            data = await self._async_db_read(0, 10)

            # Byte 0: Command flags
            self.cmd_target_z = get_bool(data, OFFSET_CMD_TARGET_Z[0], OFFSET_CMD_TARGET_Z[1])

            # Byte 2: Station status
            self.drone_detected = get_bool(data, OFFSET_DRONE_DETECTED[0], OFFSET_DRONE_DETECTED[1])
            self.plc_locked_state = get_bool(data, OFFSET_PLC_LOCKED_STATE[0], OFFSET_PLC_LOCKED_STATE[1])
            self.drone_locked = self.plc_locked_state
            self.plc_on = get_bool(data, OFFSET_PLC_ON[0], OFFSET_PLC_ON[1])
            self.plc_error = get_bool(data, OFFSET_PLC_ERROR[0], OFFSET_PLC_ERROR[1])
            self.emergency_stop = get_bool(data, OFFSET_E_STOP[0], OFFSET_E_STOP[1])
            self.plc_z_in_position = get_bool(data, OFFSET_PLC_Z_IN_POSITION[0], OFFSET_PLC_Z_IN_POSITION[1])

            # Byte 3: Staff & Conveyor status
            self.sensor_conveyor_head = get_bool(data, OFFSET_SENSOR_CONVEYOR_HEAD[0], OFFSET_SENSOR_CONVEYOR_HEAD[1])
            self.sensor_conveyor_end = get_bool(data, OFFSET_SENSOR_CONVEYOR_END[0], OFFSET_SENSOR_CONVEYOR_END[1])
            self.conveyor_running = get_bool(data, OFFSET_CONVEYOR_RUNNING[0], OFFSET_CONVEYOR_RUNNING[1])
            self.staff_outbound_busy = get_bool(data, OFFSET_STAFF_OUTBOUND_BUSY[0], OFFSET_STAFF_OUTBOUND_BUSY[1])
            self.staff_outbound_done = get_bool(data, OFFSET_STAFF_OUTBOUND_DONE[0], OFFSET_STAFF_OUTBOUND_DONE[1])
            self.staff_inbound_busy = get_bool(data, OFFSET_STAFF_INBOUND_BUSY[0], OFFSET_STAFF_INBOUND_BUSY[1])
            self.staff_inbound_done = get_bool(data, OFFSET_STAFF_INBOUND_DONE[0], OFFSET_STAFF_INBOUND_DONE[1])
            self.staff_mode_active = get_bool(data, OFFSET_STAFF_MODE_ACTIVE[0], OFFSET_STAFF_MODE_ACTIVE[1])

            # Handshake: Nếu đã gửi Cancel/Stop (=1) mà PLC báo staff_mode_active == 0 -> Tự động reset cancel/stop về 0
            if (self.cmd_staff_outbound_cancel or self.cmd_staff_inbound_stop) and not self.staff_mode_active:
                logger.info("PLC Handshake: staff_mode_active = 0 sau khi gửi Cancel/Stop -> Reset cmd_staff_outbound_cancel và cmd_staff_inbound_stop về 0")
                await self.clear_staff_cancel_bits()

            import struct
            if len(data) >= 8:
                self.staff_target_count = struct.unpack(">h", data[4:6])[0]
                self.staff_current_count = struct.unpack(">h", data[6:8])[0]
            if len(data) >= 10:
                self.current_z_level = struct.unpack(">h", data[8:10])[0]

            if self.plc_z_in_position:
                self.z_axis = Z_LEVEL_LABELS.get(self.current_z_level, "HOME")
                self.plc_busy = False
            else:
                self.z_axis = "MOVING"
                self.plc_busy = True

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
    # Z-Axis Multi-Level Control: Write DB15.DBW8 + DB15.DBX0.2 (cmd_target_z) -> Poll DB15.DBX2.7
    # ----------------------------------------------------------------

    async def move_z_to_level(self, level: int, timeout_sec: Optional[float] = None) -> bool:
        """Request PLC to move Z-axis to target level and wait for confirmation.

        Protocol (Strobe / Handshake):
          1. Backend writes target level (Int16) to DB15.DBW8.
          2. Backend turns ON DB15.DBX0.2 (cmd_target_z = True) to notify PLC to start moving Z.
          3. PLC reads DB15.DBW8, drives Z-axis motor, keeping DB15.DBX2.7 (plc_z_in_position) = False.
          4. When Z arrives at target level, PLC sets DB15.DBX2.7 (plc_z_in_position) = True.
          5. Backend detects DB15.DBX2.7 == True, then turns OFF DB15.DBX0.2 (cmd_target_z = False).

        Safety & Error Handling:
          - No timeout_sec limit by default: Z-axis can take as long as mechanical movement needs.
          - If PLC encounters an error (DB15.DBX2.5 plc_error) or Emergency Stop (DB15.DBX2.6 emergency_stop),
            Backend aborts immediately, turns off cmd_target_z, and returns False.
        """
        level_label = Z_LEVEL_LABELS.get(level, f"UNKNOWN({level})")

        # Skip if already at the requested level and confirmed in position
        if self.current_z_level == level and self.plc_z_in_position:
            logger.info("PLC Z-Axis: Already at %s (level %d). Skipping move.", level_label, level)
            return True

        self.target_z_level = level
        self.plc_z_in_position = False
        self.cmd_target_z = True
        logger.info("PLC Z-Axis: Requesting move to %s (level %d -> DB15.DBW8, cmd_target_z DB0.2 = TRUE)...", level_label, level)

        if self.simulator_mode or not SNAP7_AVAILABLE:
            await asyncio.sleep(0.3)
            self.current_z_level = level
            self.plc_z_in_position = True
            self.cmd_target_z = False  # Khi plc_z_in_position trả về thì tắt cmd_target_z
            logger.info("PLC Z-Axis [Sim]: Arrived at %s (level %d). DB15.DBX2.7 = True -> cmd_target_z (DB0.2) = False", level_label, level)
            return True

        # Real PLC: Connect if needed
        if not self.is_connected or self.client is None:
            if not self._connect_plc():
                logger.error("PLC Z-Axis: Cannot connect to PLC to write Z level.")
                self.cmd_target_z = False
                return False

        try:
            # 1. Ghi mã tầng DBW8
            import struct
            packed = struct.pack(">h", level)
            await self._async_db_write(OFFSET_CMD_TARGET_Z_LEVEL, bytearray(packed))
            logger.info("PLC Z-Axis: Written level %d to DB15.DBW8", level)

            # 2. Bật cờ cmd_target_z (DB15.DBX0.2 = True) để PLC biết kích hoạt động cơ trục Z
            async with self._get_lock():
                cmd_data = bytearray(await asyncio.to_thread(self._sync_db_read, 0, 1))
                set_bool(cmd_data, 0, OFFSET_CMD_TARGET_Z[1], True)
                await asyncio.to_thread(self._sync_db_write, 0, cmd_data)
            logger.info("PLC Z-Axis: Turned ON cmd_target_z (DB15.DBX0.2 = True)")
        except Exception as err:
            logger.error("PLC Z-Axis: Failed to initiate Z movement: %s", err)
            self.cmd_target_z = False
            return False

        # 3. Giai đoạn A: Chờ PLC xác nhận rời tầng cũ (DB15.DBX2.7 chuyển về False)
        # Giúp tránh lỗi bắt nhầm cờ True còn sót lại từ tầng trước đó
        logger.info("PLC Z-Axis: Chờ PLC xác nhận rời vị trí cũ (DB15.DBX2.7 -> False)...")
        wait_depart_start = time.time()
        departed = False
        while (time.time() - wait_depart_start) < 2.0:  # Chờ tối đa 2.0s
            await asyncio.sleep(0.08)
            try:
                data = await self._async_db_read(2, 1)
                z_in_pos = get_bool(data, 0, 7)
                plc_err = get_bool(data, 0, 5)
                is_estop = get_bool(data, 0, 6)
                if is_estop or plc_err:
                    break
                if not z_in_pos:
                    departed = True
                    logger.info("PLC Z-Axis: Đã xác nhận Z bắt đầu di chuyển (DB15.DBX2.7 = False sau %.2fs)",
                                time.time() - wait_depart_start)
                    break
            except Exception as e:
                logger.warning("PLC Z-Axis: Lỗi đọc trạng thái rời tầng cũ: %s", e)

        if not departed:
            logger.warning("PLC Z-Axis: Cảnh báo - Sau 2.0s chưa thấy DB15.DBX2.7 về False, tiếp tục chờ tầng đích...")

        # 4. Giai đoạn B: Poll DB15.DBX2.7 cho đến khi True (Trục Z đã đến tầng mới mục tiêu)
        start_time = time.time()
        last_log_time = 0.0
        while timeout_sec is None or (time.time() - start_time) < timeout_sec:
            await asyncio.sleep(DEFAULT_POLL_INTERVAL)
            elapsed = time.time() - start_time
            try:
                data = await self._async_db_read(2, 1)
                z_in_pos = get_bool(data, 0, 7)  # Bit 2.7: plc_z_in_position
                plc_err = get_bool(data, 0, 5)   # Bit 2.5: plc_error
                is_estop = get_bool(data, 0, 6)  # Bit 2.6: emergency_stop
                raw_byte2 = data[0] if data else 0

                # Diagnostic log mỗi 2 giây để quan sát trạng thái di chuyển
                if elapsed - last_log_time >= 2.0:
                    last_log_time = elapsed
                    logger.info("PLC Z-Axis Polling [%.1fs]: Byte 2 = 0x%02X (Bit 2.7 = %s, Error = %s, E-Stop = %s)",
                                elapsed, raw_byte2, z_in_pos, plc_err, is_estop)

                # Nếu PLC báo E-Stop khẩn cấp -> ngắt ngay lập tức
                if is_estop:
                    logger.error("PLC Z-Axis: EMERGENCY STOP detected while moving to level %d! Aborting...", level)
                    self.emergency_stop = True
                    break

                # Nếu PLC báo lỗi hệ thống/động cơ trục Z -> ngắt ngay lập tức
                if plc_err:
                    logger.error("PLC Z-Axis: PLC ERROR detected (DB15.DBX2.5 = 1) while moving to level %d! Aborting...", level)
                    self.plc_error = True
                    break

                # Trục Z đã đến vị trí mục tiêu an toàn
                if z_in_pos:
                    self.plc_z_in_position = True
                    self.current_z_level = level
                    logger.info("PLC Z-Axis: Confirmed at %s (level %d). DB15.DBX2.7 = True (%.1fs)",
                                level_label, level, elapsed)

                    # 5. Khi plc_z_in_position trả về thì TẮT cmd_target_z (DB15.DBX0.2 = False)
                    try:
                        async with self._get_lock():
                            reset_data = bytearray(await asyncio.to_thread(self._sync_db_read, 0, 1))
                            set_bool(reset_data, 0, OFFSET_CMD_TARGET_Z[1], False)
                            await asyncio.to_thread(self._sync_db_write, 0, reset_data)
                        self.cmd_target_z = False
                        logger.info("PLC Z-Axis: Turned OFF cmd_target_z (DB15.DBX0.2 = False)")
                    except Exception as clear_err:
                        logger.warning("PLC Z-Axis: Failed to clear cmd_target_z: %s", clear_err)

                    return True
            except Exception as poll_err:
                logger.warning("PLC Z-Axis: Poll error: %s", poll_err)

        # Di chuyển thất bại do PLC Error hoặc E-Stop: Tắt cờ cmd_target_z để an toàn
        logger.error("PLC Z-Axis: Movement aborted for level %d (%s) due to PLC Error / E-Stop!", level, level_label)
        try:
            async with self._get_lock():
                reset_data = bytearray(await asyncio.to_thread(self._sync_db_read, 0, 1))
                set_bool(reset_data, 0, OFFSET_CMD_TARGET_Z[1], False)
                await asyncio.to_thread(self._sync_db_write, 0, reset_data)
        except Exception:
            pass
        self.cmd_target_z = False
        return False

    # ----------------------------------------------------------------
    # Handshake: Send command (Byte 0 & 1) + poll status (Byte 2 & 3)
    # ----------------------------------------------------------------

    async def _write_command_bits(self, cmd: PLCCommand, is_staff_cmd: bool) -> None:
        """Atomically read DB15 Bytes 0-1, set target command bit, and write back under async lock.
        Preserves Watchdog bit 0.7 without race conditions.
        """
        async with self._get_lock():
            cmd_data = bytearray(await asyncio.to_thread(self._sync_db_read, 0, 2))

            if not is_staff_cmd:
                # Clear Station command bits (Byte 0), keeping bit 0.7 (watchdog) untouched
                set_bool(cmd_data, 0, OFFSET_CMD_LOCK[1], False)
                set_bool(cmd_data, 0, OFFSET_CMD_UNLOCK[1], False)
                set_bool(cmd_data, 0, OFFSET_CMD_STOP[1], False)
                set_bool(cmd_data, 0, OFFSET_CMD_START[1], False)
                set_bool(cmd_data, 0, OFFSET_CMD_RESET[1], False)

                # Set requested Station command bit
                if cmd == PLCCommand.LOCK_DRONE:
                    set_bool(cmd_data, 0, OFFSET_CMD_LOCK[1], True)
                elif cmd == PLCCommand.UNLOCK_DRONE:
                    set_bool(cmd_data, 0, OFFSET_CMD_UNLOCK[1], True)
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

                # Set requested Staff command bit
                if cmd == PLCCommand.STAFF_MODE_ENABLE:
                    set_bool(cmd_data, 1, OFFSET_CMD_STAFF_ENABLE[1], True)
                elif cmd == PLCCommand.STAFF_MODE_DISABLE:
                    set_bool(cmd_data, 1, OFFSET_CMD_STAFF_ENABLE[1], False)
                elif cmd == PLCCommand.STAFF_OUTBOUND_START:
                    set_bool(cmd_data, 1, OFFSET_CMD_STAFF_OUT_START[1], True)
                elif cmd == PLCCommand.STAFF_OUTBOUND_CANCEL:
                    set_bool(cmd_data, 1, OFFSET_CMD_STAFF_OUT_CANCEL[1], True)
                    self.cmd_staff_outbound_cancel = True
                elif cmd == PLCCommand.STAFF_INBOUND_START:
                    set_bool(cmd_data, 1, OFFSET_CMD_STAFF_IN_START[1], True)
                elif cmd == PLCCommand.STAFF_INBOUND_STOP:
                    set_bool(cmd_data, 1, OFFSET_CMD_STAFF_IN_STOP[1], True)
                    self.cmd_staff_inbound_stop = True

            await asyncio.to_thread(self._sync_db_write, 0, cmd_data)

    async def _clear_pulse_bits(self, is_staff_cmd: bool) -> None:
        """Atomically clear pulse command bits in Byte 0 or Byte 1 while preserving Watchdog bit."""
        async with self._get_lock():
            reset_data = bytearray(await asyncio.to_thread(self._sync_db_read, 0, 2))
            if not is_staff_cmd:
                set_bool(reset_data, 0, OFFSET_CMD_LOCK[1], False)
                set_bool(reset_data, 0, OFFSET_CMD_UNLOCK[1], False)
                set_bool(reset_data, 0, OFFSET_CMD_STOP[1], False)
                set_bool(reset_data, 0, OFFSET_CMD_START[1], False)
                set_bool(reset_data, 0, OFFSET_CMD_RESET[1], False)
            else:
                set_bool(reset_data, 1, OFFSET_CMD_STAFF_OUT_START[1], False)
                set_bool(reset_data, 1, OFFSET_CMD_STAFF_OUT_CANCEL[1], False)
                set_bool(reset_data, 1, OFFSET_CMD_STAFF_IN_START[1], False)
                set_bool(reset_data, 1, OFFSET_CMD_STAFF_IN_STOP[1], False)
                self.cmd_staff_outbound_cancel = False
                self.cmd_staff_inbound_stop = False

            await asyncio.to_thread(self._sync_db_write, 0, reset_data)

    async def clear_staff_cancel_bits(self) -> None:
        """Atomically reset cmd_staff_outbound_cancel (DB15.DBX1.2) and cmd_staff_inbound_stop (DB15.DBX1.4) to False (0).
        Được gọi:
          1. Trước mỗi khi nhân viên bấm 📦 LẤY HÀNG (OUTBOUND) hoặc 📥 THÊM HÀNG (INBOUND).
          2. Khi PLC xác nhận đã thoát Staff Mode (staff_mode_active = 0) sau khi gửi lệnh Cancel/Stop.
        """
        self.cmd_staff_outbound_cancel = False
        self.cmd_staff_inbound_stop = False

        if not self.simulator_mode and self.is_connected and self.client is not None:
            try:
                async with self._get_lock():
                    reset_data = bytearray(await asyncio.to_thread(self._sync_db_read, 0, 2))
                    set_bool(reset_data, 1, OFFSET_CMD_STAFF_OUT_CANCEL[1], False)
                    set_bool(reset_data, 1, OFFSET_CMD_STAFF_IN_STOP[1], False)
                    await asyncio.to_thread(self._sync_db_write, 0, reset_data)
                logger.info("PLC Staff Bits: Đã reset cmd_staff_outbound_cancel và cmd_staff_inbound_stop về 0 (DB15.DBX1.2 = 0, DB15.DBX1.4 = 0)")
            except Exception as err:
                logger.error("Lỗi khi reset cờ cancel/stop trong DB15 Byte 1: %s", err)
        else:
            logger.debug("PLC [Sim]: Đã reset cmd_staff_outbound_cancel và cmd_staff_inbound_stop về False")

    async def _send_command_and_wait(
        self,
        cmd: PLCCommand,
        timeout_sec: Optional[float] = None,
    ) -> bool:
        """Send command bit via pulse handshake and wait for PLC status bit to confirm.

        Safety Rules:
          - If emergency_stop becomes True during wait: abort immediately.
          - If plc_error becomes True (and command is not RESET_PLC): abort immediately.
          - Command bits are pulsed: set True, wait confirmation (or min pulse time), then cleared.
          - If timeout_sec is None, waits without timeout until confirmed or E-Stop/PLC Error.
        """
        is_staff_cmd = cmd in (
            PLCCommand.STAFF_MODE_ENABLE,
            PLCCommand.STAFF_MODE_DISABLE,
            PLCCommand.STAFF_OUTBOUND_START,
            PLCCommand.STAFF_OUTBOUND_CANCEL,
            PLCCommand.STAFF_INBOUND_START,
            PLCCommand.STAFF_INBOUND_STOP,
        )

        try:
            # 1. Assert command bit under lock
            await self._write_command_bits(cmd, is_staff_cmd)
            logger.debug("PLC Handshake: Asserted bit for command %s", cmd.value)

            # 2. Poll for target status bit
            import time
            start_time = time.time()

            while timeout_sec is None or (time.time() - start_time) < timeout_sec:
                await asyncio.sleep(DEFAULT_POLL_INTERVAL)
                elapsed = time.time() - start_time

                status_data = await self._async_db_read(0, 4)

                plc_locked = get_bool(status_data, OFFSET_PLC_LOCKED_STATE[0], OFFSET_PLC_LOCKED_STATE[1])
                plc_on = get_bool(status_data, OFFSET_PLC_ON[0], OFFSET_PLC_ON[1])
                plc_err = get_bool(status_data, OFFSET_PLC_ERROR[0], OFFSET_PLC_ERROR[1])
                is_estop = get_bool(status_data, OFFSET_E_STOP[0], OFFSET_E_STOP[1])

                staff_active = get_bool(status_data, OFFSET_STAFF_MODE_ACTIVE[0], OFFSET_STAFF_MODE_ACTIVE[1])
                out_busy = get_bool(status_data, OFFSET_STAFF_OUTBOUND_BUSY[0], OFFSET_STAFF_OUTBOUND_BUSY[1])
                in_busy = get_bool(status_data, OFFSET_STAFF_INBOUND_BUSY[0], OFFSET_STAFF_INBOUND_BUSY[1])

                if is_estop:
                    logger.error("PLC Command: EMERGENCY STOP triggered during %s", cmd.value)
                    self.emergency_stop = True
                    break

                if plc_err and cmd != PLCCommand.RESET_PLC:
                    logger.error("PLC Command: PLC_ERROR detected during %s", cmd.value)
                    self.plc_error = True
                    break

                # Target state verification
                is_target_reached = (
                    (cmd == PLCCommand.LOCK_DRONE and plc_locked) or
                    (cmd == PLCCommand.UNLOCK_DRONE and not plc_locked) or
                    (cmd == PLCCommand.START_PLC and plc_on) or
                    (cmd == PLCCommand.STOP_PLC and not plc_on) or
                    (cmd == PLCCommand.RESET_PLC and not plc_err) or
                    (cmd == PLCCommand.STAFF_MODE_ENABLE and staff_active) or
                    (cmd == PLCCommand.STAFF_MODE_DISABLE and not staff_active) or
                    (cmd == PLCCommand.STAFF_OUTBOUND_START and out_busy) or
                    (cmd == PLCCommand.STAFF_OUTBOUND_CANCEL and (not out_busy or not staff_active)) or
                    (cmd == PLCCommand.STAFF_INBOUND_START and in_busy) or
                    (cmd == PLCCommand.STAFF_INBOUND_STOP and (not in_busy or not staff_active))
                )

                if is_target_reached:
                    logger.info("PLC Command %s COMPLETED (Status verified in %.1fs)", cmd.value, elapsed)
                    # Step 3: Clear pulse command bits in Byte 0 / Byte 1 atomically
                    await self._clear_pulse_bits(is_staff_cmd)
                    return True

            # Timeout or aborted — clear pulse command bits anyway
            logger.warning("PLC Command: Timeout or aborted waiting for status flag on %s", cmd.value)
            await self._clear_pulse_bits(is_staff_cmd)
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
            cmd_staff_outbound_cancel=self.cmd_staff_outbound_cancel,
            cmd_staff_inbound_stop=self.cmd_staff_inbound_stop,
            plc_z_in_position=self.plc_z_in_position,
            cmd_target_z=self.cmd_target_z,
            target_z_level=self.target_z_level,
            current_z_level=self.current_z_level,
        )

    async def execute_command(self, cmd: PLCCommand) -> PLCStatusResponse:
        """Execute a PLC command using Handshake Signal Protocol."""
        logger.info("Executing PLC command: %s (DB%d, Simulator Mode: %s)", cmd.value, self.db_number, self.simulator_mode)

        # Legacy Z commands: Redirect directly to multi-level control (DB15.DBW8)
        if cmd == PLCCommand.Z_UP:
            logger.info("PLC execute_command: Legacy Z_UP redirected to move_z_to_level(Z_LEVEL_DOCK_N)")
            await self.move_z_to_level(Z_LEVEL_DOCK_N)
            return self.get_status()
        elif cmd == PLCCommand.Z_DOWN:
            logger.info("PLC execute_command: Legacy Z_DOWN redirected to move_z_to_level(Z_LEVEL_HOME)")
            await self.move_z_to_level(Z_LEVEL_HOME)
            return self.get_status()

        # Safety Interlock: Block motion/station commands if PLC is in E-Stop or Error state.
        # STOP_PLC and RESET_PLC are always permitted as emergency/recovery actions.
        if cmd not in (PLCCommand.STOP_PLC, PLCCommand.RESET_PLC):
            if self.emergency_stop:
                logger.warning("Rejecting PLC command %s: Emergency Stop (E-Stop) is currently active!", cmd.value)
                raise RuntimeError(
                    f"Không thể thực thi lệnh {cmd.value}: Nút dừng khẩn cấp (Emergency Stop) của PLC đang được kích hoạt!"
                )
            if self.plc_error:
                logger.warning("Rejecting PLC command %s: PLC is in error state!", cmd.value)
                raise RuntimeError(
                    f"Không thể thực thi lệnh {cmd.value}: PLC đang báo lỗi (PLC_ERROR). Vui lòng Reset PLC trước khi tiếp tục!"
                )

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
            elif cmd == PLCCommand.STAFF_MODE_ENABLE:
                self.staff_mode_active = True
            elif cmd == PLCCommand.STAFF_MODE_DISABLE:
                self.staff_mode_active = False
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
            self.z_axis = "DOWN"
            self.plc_z_is_up = False
            self.plc_z_is_down = True
            logger.info("PLC [Sim]: System started / enabled (plc_on = True, Z-axis auto-homed to DOWN)")

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

        # Staff Mode & Conveyor Commands in Simulator
        elif cmd == PLCCommand.STAFF_MODE_ENABLE:
            self.staff_mode_active = True
            logger.info("PLC [Sim]: Staff Mode Enabled (staff_mode_active = True)")

        elif cmd == PLCCommand.STAFF_MODE_DISABLE:
            self.staff_mode_active = False
            logger.info("PLC [Sim]: Staff Mode Disabled (staff_mode_active = False)")

        elif cmd == PLCCommand.STAFF_OUTBOUND_START:
            self.staff_outbound_busy = True
            self.staff_outbound_done = False
            logger.info("PLC [Sim]: Staff Outbound cycle started (staff_outbound_busy = True)")

        elif cmd == PLCCommand.STAFF_OUTBOUND_CANCEL:
            self.staff_outbound_busy = False
            self.staff_mode_active = False
            self.cmd_staff_outbound_cancel = False
            logger.info("PLC [Sim]: Staff Outbound cycle cancelled (staff_mode_active = False, cmd_staff_outbound_cancel = False)")

        elif cmd == PLCCommand.STAFF_INBOUND_START:
            self.staff_inbound_busy = True
            self.staff_inbound_done = False
            logger.info("PLC [Sim]: Staff Inbound cycle started (staff_inbound_busy = True)")

        elif cmd == PLCCommand.STAFF_INBOUND_STOP:
            self.staff_inbound_busy = False
            self.staff_inbound_done = True
            self.staff_mode_active = False
            self.cmd_staff_inbound_stop = False
            logger.info("PLC [Sim]: Staff Inbound cycle stopped (staff_mode_active = False, cmd_staff_inbound_stop = False)")

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
        timeout_sec: Optional[float] = None,
        poll_interval: float = 0.15,
    ) -> None:
        """Wait for a PLC status attribute to reach the target value.

        Used by StationService for FSM handshake protocol:
            Command → Execute → Feedback → Next Step

        In simulator mode, the execute_command method already sets the
        target status synchronously, so this will return almost immediately.
        In real hardware mode, it polls the cached PLC state (updated by
        read_plc_status) until the target value is reached.

        Args:
            status_key: Name of the cached boolean attribute
                        (e.g. 'drone_detected', 'plc_locked_state',
                         'plc_z_in_position', 'plc_on', 'plc_error').
            target_value: The boolean value to wait for.
            timeout_sec: Maximum wait time in seconds before raising TimeoutError.
                         If None (default), waits indefinitely until satisfied or E-Stop.
            poll_interval: Seconds between polling attempts.

        Raises:
            TimeoutError: If timeout_sec is specified and target value is not reached within timeout_sec.
            RuntimeError: If emergency_stop or plc_error occurs during wait.
            AttributeError: If status_key is not a valid PLC attribute.
        """
        if not hasattr(self, status_key):
            raise AttributeError(
                f"PLCManager has no status attribute '{status_key}'. "
                f"Valid keys: drone_detected, plc_locked_state, plc_z_in_position, "
                f"plc_on, plc_error, emergency_stop"
            )

        elapsed = 0.0
        while timeout_sec is None or elapsed < timeout_sec:
            if self.emergency_stop:
                raise RuntimeError("EMERGENCY_STOP triggered while waiting for PLC status.")
            if self.plc_error and status_key != "plc_error":
                raise RuntimeError("PLC_ERROR detected while waiting for PLC status.")

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

        # Timeout reached (only if timeout_sec is not None)
        current_value = getattr(self, status_key)
        raise TimeoutError(
            f"PLC wait_for_status('{status_key}'={target_value}) timed out after {timeout_sec}s. "
            f"Current value: {current_value}"
        )

    def set_drone_detected(self, detected: bool) -> None:
        self.drone_detected = detected
        logger.info("PLC Sensor: Drone detection set to %s", detected)

    def set_emergency_stop(self, estop: bool) -> None:
        self.emergency_stop = estop
        if estop:
            self.plc_busy = False
        logger.warning("PLC State: Emergency Stop set to %s", estop)

    def set_plc_error(self, error: bool) -> None:
        self.plc_error = error
        if error:
            self.plc_busy = False
        logger.warning("PLC State: PLC Error state set to %s", error)

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

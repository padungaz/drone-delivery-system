import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import select

from app.database.repository import async_session
from app.models.database import ProductRecord, StorageSlotRecord
from app.models.schemas import RobotCommand, StorageSlotStatus, PLCCommand
from app.services.camera_manager import CameraManager
from app.services.device_lock_manager import device_lock_manager
from app.services.inventory_manager import InventoryManager
from app.services.plc_manager import PLCManager, slot_to_z_level, Z_LEVEL_LABELS
from app.services.robot_manager import RobotManager
from app.services.system_mode_manager import system_mode_manager
from app.websocket.manager import system_ws_manager

logger = logging.getLogger(__name__)


class StaffOperationManager:
    """Manages Staff Warehouse Operations (Outbound Picking to Conveyor & Inbound Storing from O1).
    
    Architecture & Logic:
    =====================
    1. OUTBOUND (Lấy hàng ra Băng tải):
       - User selects slots (e.g. ['A2', 'B1', 'C3'])
       - Loop for each slot:
         a. Check conveyor start sensor via PLC (simulated / real)
         b. Trigger Robot to pick from Slot and place at Conveyor (O1)
         c. Robot pulses DO1 -> PLC, Backend clears slot from DB
         d. PLC runs conveyor until head sensor cleared
       - Loop ends when queue is done.
       
    2. INBOUND (Thêm hàng từ O1 vào Kho):
       - Mode: 'QUANTITY' (stops at target_count), 'MANUAL' (runs until user stops), 'FULL_AUTO' (stops when 9 slots full)
       - Loop:
         a. Item arrives at O1 / Conveyor head
         b. Camera scans QR (or reads from scanner)
         c. Backend finds first empty slot (A1..C3)
         d. Robot picks from O1 and places in target slot
         e. Backend updates DB slot with product info
         f. Increment count & check termination condition
    """

    _instance: Optional["StaffOperationManager"] = None

    def __init__(self):
        self.plc_mgr = PLCManager.get_instance()
        self.robot_mgr = RobotManager.get_instance()
        self.cam_mgr = CameraManager.get_instance()

        self.active_type: Optional[str] = None  # None | "OUTBOUND" | "INBOUND"
        self.status: str = "IDLE"  # "IDLE" | "RUNNING" | "PAUSED" | "COMPLETED" | "CANCELLED" | "ERROR"
        self.message: str = "Hệ thống nhân viên sẵn sàng."

        # Outbound state
        self.outbound_queue: List[str] = []
        self.outbound_completed: List[str] = []
        self.outbound_current_slot: Optional[str] = None

        # Inbound state
        self.inbound_mode: str = "QUANTITY"  # "QUANTITY" | "MANUAL" | "FULL_AUTO"
        self.inbound_target_count: int = 1
        self.inbound_current_count: int = 0
        self.inbound_current_slot: Optional[str] = None
        self.last_scanned_qr: Optional[str] = None

        # Background runner task
        self._current_task: Optional[asyncio.Task] = None
        self._stop_requested: bool = False
        # [Issue #5] Queue chống mất/trôi xung tín hiệu qua từng chu kỳ
        self._robot_ready_queue: asyncio.Queue = asyncio.Queue(maxsize=10)
        self._inbound_ready_queue: asyncio.Queue = asyncio.Queue(maxsize=10)
        # [Issue #2 & #3] Theo dõi kiện hàng Robot đang kẹp trên tay
        self._holding_product_info: Optional[Dict[str, Any]] = None

    def notify_robot_ready(self) -> None:
        """Called when Robot reports ROBOT_READY (via hardware DI1 from PLC)."""
        logger.info("[StaffOperationManager] Robot ready signal received (DI1 triggered). Triggering next outbound slot!")
        try:
            self._robot_ready_queue.put_nowait(True)
        except asyncio.QueueFull:
            pass

    def notify_inbound_ready(self) -> None:
        """Called when Robot reports ROBOT_INBOUND_READY (via hardware DI2 from PLC when item is at O1)."""
        logger.info("[StaffOperationManager] Robot inbound ready signal received (DI2 triggered). Proceeding with storing!")
        try:
            self._inbound_ready_queue.put_nowait(True)
        except asyncio.QueueFull:
            pass

    async def _verify_z_in_position(self, target_z: int, slot_label: str) -> bool:
        """
        [Safety Interlock - Issue #1] Xác thực kép trục Z đã thực sự đến đúng tầng và đứng yên ổn định.
        Ngăn chặn mọi nguy cơ va chạm cơ khí gãy cánh tay Robot.
        """
        await asyncio.sleep(0.15)  # Thời gian ổn định cơ khí sau khi động cơ dừng
        if not self.plc_mgr.plc_z_in_position or self.plc_mgr.current_z_level != target_z:
            logger.error(
                "[Safety Interlock] Trục Z chưa ổn định ở tầng %s (Mục tiêu: %d, Hiện tại: %s, InPos: %s)! Ngăn chặn lệnh Robot.",
                slot_label,
                target_z,
                self.plc_mgr.current_z_level,
                self.plc_mgr.plc_z_in_position,
            )
            return False
        return True

    async def _execute_robot_command_safe(self, cmd: RobotCommand, slot: str, max_retries: int = 2) -> None:
        """
        [Issue #9] Thực thi lệnh Robot với cơ chế tự động thử lại nếu gặp lỗi kết nối/phản hồi thoáng qua.
        """
        last_err = None
        for attempt in range(1, max_retries + 1):
            try:
                await self.robot_mgr.execute_command(cmd, slot=slot)
                return
            except Exception as e:
                last_err = e
                logger.warning("Robot %s %s thử lại lần %d/%d thất bại: %s", cmd.value, slot, attempt, max_retries, e)
                if attempt < max_retries:
                    await asyncio.sleep(0.5)
        raise RuntimeError(f"Lỗi điều khiển Robot {cmd.value} {slot} sau {max_retries} lần thử: {last_err}")

    @classmethod
    def get_instance(cls) -> "StaffOperationManager":
        if cls._instance is None:
            cls._instance = StaffOperationManager()
        return cls._instance

    def get_status(self) -> Dict[str, Any]:
        return {
            "active_type": self.active_type,
            "status": self.status,
            "message": self.message,
            "outbound": {
                "queue": self.outbound_queue,
                "completed": self.outbound_completed,
                "current_slot": self.outbound_current_slot,
                "total": len(self.outbound_queue) + len(self.outbound_completed),
                "remaining": len(self.outbound_queue),
            },
            "inbound": {
                "mode": self.inbound_mode,
                "target_count": self.inbound_target_count,
                "current_count": self.inbound_current_count,
                "current_slot": self.inbound_current_slot,
                "last_scanned_qr": self.last_scanned_qr,
            },
            "robot_state": self.robot_mgr.state,
            "plc_state": {
                "connected": self.plc_mgr.is_connected or self.plc_mgr.simulator_mode,
                "busy": self.plc_mgr.plc_busy,
            },
        }

    async def broadcast_status(self) -> None:
        await system_ws_manager.broadcast("STAFF_OPERATION_UPDATE", self.get_status())

    async def log_event(self, text: str) -> None:
        self.message = text
        logger.info("[StaffOperationManager] %s", text)
        await self.broadcast_status()

    # =========================================================================
    # OUTBOUND PICKING FLOW
    # =========================================================================
    async def start_outbound(self, slots: Optional[List[str]] = None, quantity: Optional[int] = None) -> Dict[str, Any]:
        if self.status == "RUNNING":
            if self.active_type == "INBOUND":
                logger.info("📦 [Chế độ LẤY HÀNG]: Tự động TẮT / DỪNG tiến trình THÊM HÀNG (Inbound)...")
                await self.stop_inbound()
                await asyncio.sleep(0.4)
            elif self.active_type == "OUTBOUND":
                raise RuntimeError("Tiến trình lấy hàng đang chạy. Vui lòng dừng hoặc chờ hoàn tất.")
            else:
                raise RuntimeError("Đang có tiến trình khác đang chạy. Vui lòng dừng hoặc chờ hoàn tất.")

        # Resolve target slots from slots parameter or quantity count
        resolved_slots: List[str] = []
        if slots and len(slots) > 0:
            resolved_slots = [s.upper().strip() for s in slots]
        elif quantity and quantity > 0:
            async with async_session() as session:
                inv_mgr = InventoryManager(session)
                occupied = await inv_mgr.get_occupied_slots()
                if not occupied:
                    raise ValueError("Kho đang trống, không có hàng để xuất.")
                resolved_slots = [slot.slot_name for slot in occupied[:quantity]]
        else:
            raise ValueError("Vui lòng cung cấp danh sách ô hoặc số lượng hàng cần lấy.")

        if not resolved_slots:
            raise ValueError("Không tìm thấy ô phù hợp để lấy hàng.")

        target_count = len(resolved_slots)

        # Check safety interlock: ensure station is not busy with a Drone Mission
        if device_lock_manager.is_station_busy() and device_lock_manager._locks.get("STATION", {}).get("locked_by") != "STAFF_OPERATION":
            lock_mission = device_lock_manager.get_locking_mission_id("STATION")
            raise RuntimeError(f"Trạm Drone đang bận thực thi Nhiệm vụ #{lock_mission}. Vui lòng đợi hoàn tất trước khi lấy hàng!")

        # Acquire lock on hardware
        device_lock_manager.lock_device("STATION", locked_by="STAFF_OPERATION", reason="Nhân viên đang lấy hàng ra băng tải")
        device_lock_manager.lock_device("PLC01", locked_by="STAFF_OPERATION", reason="Nhân viên đang lấy hàng ra băng tải")
        device_lock_manager.lock_device("ROBOT01", locked_by="STAFF_OPERATION", reason="Nhân viên đang lấy hàng ra băng tải")

        # 1. Reset cờ cancel/stop (DB15.DBX1.2 & 1.4) về 0 trước khi bắt đầu lấy hàng
        await self.plc_mgr.clear_staff_cancel_bits()

        # 2. Ensure we switch system mode to STAFF_OPERATION
        await system_mode_manager.set_operation_mode("STAFF_OPERATION")

        # 3. Send Target Quantity & Outbound Start to PLC
        await self.plc_mgr.set_staff_target_count(target_count)
        await self.plc_mgr.execute_command(PLCCommand.STAFF_MODE_ENABLE)
        await self.plc_mgr.execute_command(PLCCommand.STAFF_OUTBOUND_START)

        self.active_type = "OUTBOUND"
        self.status = "RUNNING"
        self.outbound_queue = resolved_slots
        self.outbound_completed = []
        self.outbound_current_slot = None
        self._stop_requested = False
        # Xóa sạch token cũ trong queue
        while not self._robot_ready_queue.empty():
            try:
                self._robot_ready_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self._holding_product_info = None

        await self.log_event(f"🚀 Backend đã gửi xuống PLC: Chế độ Outbound Picking (Mục tiêu: {target_count} kiện: {', '.join(self.outbound_queue)})")

        # Launch worker task
        self._current_task = asyncio.create_task(self._run_outbound_loop())
        return self.get_status()

    async def cancel_outbound(self) -> Dict[str, Any]:
        if self.status != "RUNNING":
            return self.get_status()

        self._stop_requested = True
        try:
            self._robot_ready_queue.put_nowait(False)
        except asyncio.QueueFull:
            pass

        # [Issue #2] Xử lý an toàn khi Robot đang kẹp hàng trên tay:
        # Cho phép chu trình hoàn tất nốt bước hạ Z và đặt hàng xuống O1 trước khi dừng hẳn
        if self._holding_product_info:
            held_slot = self._holding_product_info.get("source_slot")
            await self.log_event(
                f"⚠️ Nhân viên yêu cầu Hủy khi Robot đang kẹp kiện hàng từ {held_slot}! "
                f"Hệ thống cho phép chu trình hoàn tất đặt kiện hàng xuống O1 an toàn trước khi dừng..."
            )
            if self._current_task and not self._current_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(self._current_task), timeout=30.0)
                except Exception as e:
                    logger.warning("Chờ hoàn thành đặt hàng khi hủy Outbound: %s", e)

        if self._current_task and not self._current_task.done():
            self._current_task.cancel()

        # Gửi lệnh HỦY sang PLC (bật DB15.DBX1.2 = 1)
        await self.plc_mgr.execute_command(PLCCommand.STAFF_OUTBOUND_CANCEL)

        # Gửi lệnh CANCEL xuống Robot để xóa cờ WAITING_SLOT và đưa Robot về IDLE an toàn
        try:
            await self.robot_mgr.execute_command(RobotCommand.CANCEL)
        except Exception as e:
            logger.warning("Không thể gửi CANCEL xuống Robot: %s", e)

        self._holding_product_info = None
        device_lock_manager.unlock_station()
        self.status = "CANCELLED"
        await self.log_event("🛑 Tiến trình lấy hàng đã bị hủy bởi nhân viên.")
        return self.get_status()

    async def _run_outbound_loop(self) -> None:
        """
        Chu trình lấy hàng 9 bước phối hợp PLC - Robot - Backend:
        1. Backend ghi DB15.DBW4 = target_count, khởi động xuất hàng.
        2. PLC sẵn sàng -> kích DI1 sang Robot.
        3. Robot nhận DI1 = 1 -> gửi ROBOT_READY lên Backend.
        4. Backend xác định ô cần lấy -> yêu cầu PLC đưa Z lên tầng ô kho.
        5. Trục Z đến tầng ô kho (Xác thực an toàn DBX2.7) -> Backend yêu cầu Robot gắp (PICK slot).
        6. Robot gắp xong -> Đánh dấu đang giữ hàng.
        7. Backend yêu cầu PLC đưa Z xuống tầng Băng tải O1.
        8. Z đến O1 (Xác thực an toàn DBX2.7) -> Robot thả tại O1 -> Cập nhật CSDL kho chính xác (EMPTY).
        9. Robot kích xung DO1 sang PLC -> PLC tăng DBW6 + 1.
        """
        try:
            total_items = len(self.outbound_queue)
            while self.outbound_queue and not self._stop_requested:
                current_item_idx = len(self.outbound_completed) + 1

                # -------------------------------------------------------------
                # Bước 2 & 3: Chờ PLC kích DI1 và Robot gửi ROBOT_READY
                # [Issue #5]: Sử dụng Queue để đảm bảo tiêu thụ tuần tự, chống trôi xung
                # -------------------------------------------------------------
                if self.robot_mgr.simulator_mode or self.plc_mgr.simulator_mode:
                    await asyncio.sleep(1.0)
                    self.notify_robot_ready()

                await self.log_event(
                    f"⏳ [Bước 2-3] Chờ PLC kích DI1 sang Robot báo sẵn sàng lấy kiện {current_item_idx}/{total_items}..."
                )

                ready_received = False
                step_start_time = time.time()
                while not ready_received and not self._stop_requested:
                    try:
                        token = await asyncio.wait_for(self._robot_ready_queue.get(), timeout=1.0)
                        if token is True:
                            ready_received = True
                            break
                    except asyncio.TimeoutError:
                        # [Issue #7]: Giám sát Timeout 180s
                        if time.time() - step_start_time > 180.0:
                            await self.log_event(
                                f"⚠️ [Bước 2-3] Quá 180s chưa có tín hiệu DI1 từ PLC cho kiện {current_item_idx}/{total_items}. Vui lòng kiểm tra băng tải/cảm biến."
                            )
                            step_start_time = time.time()

                if self._stop_requested:
                    return

                # -------------------------------------------------------------
                # Bước 4: Backend xác định ô cần lấy & Yêu cầu PLC đưa Z lên tầng
                # -------------------------------------------------------------
                target_slot = self.outbound_queue[0]
                self.outbound_current_slot = target_slot
                z_slot = slot_to_z_level(target_slot)
                z_slot_label = Z_LEVEL_LABELS.get(z_slot, str(z_slot))

                await self.log_event(
                    f"📦 [Bước 4] Robot đã sẵn sàng! Backend xác định lấy ô {target_slot} ({current_item_idx}/{total_items}). "
                    f"Yêu cầu PLC nâng Z lên tầng {z_slot_label} (DB15.DBW8={z_slot})..."
                )

                if not await self.plc_mgr.move_z_to_level(z_slot, timeout_sec=60.0):
                    self.status = "ERROR"
                    await self.log_event(f"❌ PLC trục Z không thể đến tầng {z_slot_label}! Dừng chu trình xuất.")
                    return

                # [Issue #1]: Xác thực kép Trục Z in-position trước khi Robot di chuyển gắp hàng
                if not await self._verify_z_in_position(z_slot, z_slot_label):
                    self.status = "ERROR"
                    await self.log_event(f"❌ Trục Z chưa ổn định ở tầng {z_slot_label}! Dừng chu trình để bảo vệ cánh tay Robot.")
                    return

                # -------------------------------------------------------------
                # Bước 5 & 6: Trục Z đến tầng -> Backend yêu cầu Robot gắp hàng (PICK slot)
                # -------------------------------------------------------------
                await self.log_event(f"🤖 [Bước 5] Trục Z đã đến tầng {z_slot_label}. Yêu cầu Robot gắp hàng ô {target_slot}...")
                try:
                    await self._execute_robot_command_safe(RobotCommand.PICK, slot=target_slot)
                    await self.log_event(f"✅ [Bước 6] Robot đã gắp ô {target_slot} thành công và rút về vị trí an toàn.")
                except Exception as e:
                    logger.error("Lỗi điều khiển Robot khi gắp ô %s: %s", target_slot, e)
                    self.status = "ERROR"
                    await self.log_event(f"❌ Lỗi Robot khi gắp ô {target_slot}: {str(e)}")
                    return

                # [Issue #2 & #3]: Đánh dấu Robot đang giữ hàng, CHƯA cập nhật kho thành EMPTY vội!
                item_prod_id = None
                async with async_session() as session:
                    stmt_slot = select(StorageSlotRecord).where(StorageSlotRecord.slot_name == target_slot)
                    res_slot = await session.execute(stmt_slot)
                    slot_item = res_slot.scalar_one_or_none()
                    if slot_item:
                        item_prod_id = slot_item.product_id

                self._holding_product_info = {
                    "source_slot": target_slot,
                    "product_id": item_prod_id,
                    "operation": "OUTBOUND",
                }

                # -------------------------------------------------------------
                # Bước 7: Backend yêu cầu PLC đưa Z xuống tầng Băng tải O1
                # -------------------------------------------------------------
                z_o1 = slot_to_z_level("O1")
                z_o1_label = Z_LEVEL_LABELS.get(z_o1, str(z_o1))
                await self.log_event(
                    f"⬇️ [Bước 7] Robot gắp xong. Backend yêu cầu PLC hạ Z xuống tầng Băng tải O1 ({z_o1_label}, DB15.DBW8={z_o1})..."
                )
                if not await self.plc_mgr.move_z_to_level(z_o1, timeout_sec=60.0):
                    self.status = "ERROR"
                    await self.log_event(f"❌ PLC trục Z không thể hạ xuống tầng Băng tải {z_o1_label}! Dừng chu trình xuất.")
                    return

                # [Issue #1]: Xác thực kép Trục Z in-position trước khi Robot thả xuống O1
                if not await self._verify_z_in_position(z_o1, z_o1_label):
                    self.status = "ERROR"
                    await self.log_event(f"❌ Trục Z chưa ổn định ở tầng Băng tải O1! Dừng chu trình để bảo vệ Robot.")
                    return

                # -------------------------------------------------------------
                # Bước 8: Z đến O1 -> Backend yêu cầu Robot thả hàng tại O1
                # (Robot thả hàng tại O1 -> Robot tự bật xung DO1 sang PLC)
                # -------------------------------------------------------------
                await self.log_event("📦 [Bước 8] Z đã đến O1. Yêu cầu Robot thả kiện hàng xuống Băng tải O1...")
                try:
                    await self._execute_robot_command_safe(RobotCommand.STORE, slot="O1")
                except Exception as e:
                    logger.error("Lỗi điều khiển Robot khi đặt hàng xuống O1: %s", e)
                    self.status = "ERROR"
                    await self.log_event(f"❌ Lỗi Robot khi đặt hàng xuống O1: {str(e)}")
                    return

                # [Issue #3]: Robot đã thả an toàn xuống O1 -> Xóa cờ holding và cập nhật kho chính xác
                self._holding_product_info = None

                async with async_session() as session:
                    inv_mgr = InventoryManager(session)
                    await inv_mgr.update_slot(
                        slot_name=target_slot,
                        status=StorageSlotStatus.EMPTY,
                        product_id=None,
                        qr_code=None,
                        auto_broadcast=True,
                    )

                    if item_prod_id:
                        stmt_p = select(ProductRecord).where(ProductRecord.product_id == item_prod_id)
                        res_p = await session.execute(stmt_p)
                        prod_rec = res_p.scalar_one_or_none()
                        if prod_rec:
                            prod_rec.status = "EXPORTED"
                            prod_rec.updated_at = datetime.utcnow()
                            await session.commit()

                await self.log_event(
                    f"📦 [Cập nhật kho] Đã xuất kiện hàng từ ô {target_slot} ra O1 thành công -> Ô {target_slot} đã TRỐNG (EMPTY)!"
                )

                self.outbound_completed.append(target_slot)
                self.outbound_queue.pop(0)
                self.outbound_current_slot = None

                # -------------------------------------------------------------
                # Bước 9: PLC nhận DO1 -> tự tăng DB15.DBW6 + 1
                # -------------------------------------------------------------
                if self.plc_mgr.simulator_mode:
                    await self.plc_mgr.increment_staff_count()

                await self.log_event(
                    f"✅ [Bước 9] Hoàn tất kiện {target_slot}. PLC nhận xung DO1, chạy băng tải và đếm sản phẩm ({len(self.outbound_completed)}/{total_items})."
                )
                await self.broadcast_status()

            if not self._stop_requested:
                self.status = "COMPLETED"
                await self.log_event(
                    f"🎉 Hoàn tất chu trình lấy hàng (Tổng {len(self.outbound_completed)}/{total_items} kiện hàng đã ra băng tải)!"
                )
                device_lock_manager.unlock_station()

        except asyncio.CancelledError:
            self.status = "CANCELLED"
            await self.log_event("🛑 Chu trình lấy hàng đã bị dừng.")
        except Exception as err:
            logger.error("Outbound loop exception: %s", err, exc_info=True)
            self.status = "ERROR"
            await self.log_event(f"❌ Lỗi trong chu trình xuất hàng: {err}")
        finally:
            self._holding_product_info = None
            device_lock_manager.unlock_station()
            self.outbound_current_slot = None
            await self.broadcast_status()

    # =========================================================================
    # INBOUND STORING FLOW (Nạp chủ động liên tục -> Tự kết thúc khi đầy kho hoặc bấm Dừng)
    # =========================================================================
    async def start_inbound(self, target_count: int = 6) -> Dict[str, Any]:
        if self.status == "RUNNING":
            if self.active_type == "OUTBOUND":
                logger.info("📥 [Chế độ THÊM HÀNG]: Tự động TẮT / HỦY tiến trình LẤY HÀNG (Outbound)...")
                await self.cancel_outbound()
                await asyncio.sleep(0.4)
            elif self.active_type == "INBOUND":
                raise RuntimeError("Tiến trình thêm hàng đang chạy. Vui lòng dừng hoặc chờ hoàn tất.")
            else:
                raise RuntimeError("Đang có tiến trình khác đang chạy. Vui lòng dừng hoặc chờ hoàn tất.")

        # Check safety interlock: ensure station is not busy with a Drone Mission
        if device_lock_manager.is_station_busy() and device_lock_manager._locks.get("STATION", {}).get("locked_by") != "STAFF_OPERATION":
            lock_mission = device_lock_manager.get_locking_mission_id("STATION")
            raise RuntimeError(f"Trạm Drone đang bận thực thi Nhiệm vụ #{lock_mission}. Vui lòng đợi hoàn tất trước khi thêm hàng!")

        # Xóa sạch token cũ trong queue
        while not self._inbound_ready_queue.empty():
            try:
                self._inbound_ready_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self._holding_product_info = None

        # Acquire lock on hardware
        device_lock_manager.lock_device("STATION", locked_by="STAFF_OPERATION", reason="Nhân viên đang thêm hàng vào kho")
        device_lock_manager.lock_device("PLC01", locked_by="STAFF_OPERATION", reason="Nhân viên đang thêm hàng vào kho")
        device_lock_manager.lock_device("ROBOT01", locked_by="STAFF_OPERATION", reason="Nhân viên đang thêm hàng vào kho")

        # 1. Reset cờ cancel/stop (DB15.DBX1.2 & 1.4) về 0 trước khi bắt đầu thêm hàng
        await self.plc_mgr.clear_staff_cancel_bits()

        # 2. Ensure we switch system mode to STAFF_OPERATION
        await system_mode_manager.set_operation_mode("STAFF_OPERATION")

        # 3. Enable Staff Mode & Inbound on PLC
        await self.plc_mgr.execute_command(PLCCommand.STAFF_MODE_ENABLE)
        await self.plc_mgr.execute_command(PLCCommand.STAFF_INBOUND_START)

        self.active_type = "INBOUND"
        self.status = "RUNNING"
        self.inbound_mode = "CONTINUOUS"
        self.inbound_target_count = target_count
        self.inbound_current_count = 0
        self.inbound_current_slot = None
        self.last_scanned_qr = None
        self._stop_requested = False

        await self.log_event(f"📥 Bắt đầu nạp hàng chủ động (Mục tiêu: {target_count} kiện hoặc đến khi đầy 6 ô hoạt động A1..B3)...")

        self._current_task = asyncio.create_task(self._run_inbound_loop())
        return self.get_status()

    async def stop_inbound(self) -> Dict[str, Any]:
        if self.status != "RUNNING":
            return self.get_status()

        self._stop_requested = True
        try:
            self._inbound_ready_queue.put_nowait(False)
        except asyncio.QueueFull:
            pass

        # [Issue #2] Nếu Robot đang kẹp hàng trên tay:
        if self._holding_product_info:
            target_slot = self._holding_product_info.get("target_slot")
            await self.log_event(
                f"⚠️ Nhân viên yêu cầu Dừng khi Robot đang kẹp kiện hàng! "
                f"Hệ thống cho phép cất an toàn kiện hàng vào ô {target_slot} trước khi dừng..."
            )
            if self._current_task and not self._current_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(self._current_task), timeout=30.0)
                except Exception as e:
                    logger.warning("Chờ cất hàng khi dừng Inbound: %s", e)

        if self._current_task and not self._current_task.done():
            self._current_task.cancel()

        # Gửi lệnh DỪNG sang PLC (bật DB15.DBX1.4 = 1)
        await self.plc_mgr.execute_command(PLCCommand.STAFF_INBOUND_STOP)

        # Gửi lệnh CANCEL xuống Robot để xóa cờ WAITING_SLOT và đưa Robot về IDLE an toàn
        try:
            await self.robot_mgr.execute_command(RobotCommand.CANCEL)
        except Exception as e:
            logger.warning("Không thể gửi CANCEL xuống Robot: %s", e)

        self._holding_product_info = None
        device_lock_manager.unlock_station()
        self.status = "COMPLETED"
        await self.log_event(f"🏁 Nhân viên đã bấm Kết thúc nạp hàng (Tổng nạp: {self.inbound_current_count} sản phẩm).")
        return self.get_status()

    async def _run_inbound_loop(self) -> None:
        """
        Chu trình thêm hàng (Inbound) 9 bước phối hợp PLC - Robot - Camera - Backend:
        1. Bắt đầu phiên nạp hàng (Mục tiêu tối đa inbound_target_count).
        2. Băng tải chạy -> Cảm biến O1 có hàng -> PLC dừng băng tải và kích DI2 sang Robot.
        3. Robot nhận DI2 -> gửi ROBOT_INBOUND_READY về Backend.
        4. [Issue #10] Sau khi có hàng tại O1 -> Backend tìm ô trống khả dụng (A1..B3) -> Hạ Z xuống O1.
        5. Trục Z đến O1 (Xác thực an toàn DBX2.7) -> Robot gắp hàng tại O1 (PICK O1).
        6. Robot đưa kiện hàng qua Camera CAM01 để quét mã QR sản phẩm (tối đa 8s).
        7. Quét xong -> Backend yêu cầu PLC nâng Z lên tầng ô kho.
        8. Z đến tầng ô kho (Xác thực an toàn DBX2.7) -> Robot cất hàng vào ô kho (STORE target_slot).
        9. Robot cất xong -> Cập nhật kho OCCUPIED -> Kích xung DO2 sang PLC -> PLC chạy tiếp kiện sau.
        """
        try:
            while not self._stop_requested:
                # [Issue #13]: Kiểm tra số lượng mục tiêu đã đạt chưa
                if self.inbound_target_count > 0 and self.inbound_current_count >= self.inbound_target_count:
                    await self.log_event(
                        f"🎉 Đã hoàn tất nạp đủ số lượng mục tiêu ({self.inbound_current_count}/{self.inbound_target_count} kiện)! Kết thúc Inbound."
                    )
                    self.status = "COMPLETED"
                    break

                # -------------------------------------------------------------
                # [Issue #10]: Đảo thứ tự -> Chờ cảm biến quang O1 có hàng TRƯỚC
                # (PLC kích DI2 -> Robot gửi ROBOT_INBOUND_READY)
                # -------------------------------------------------------------
                if self.robot_mgr.simulator_mode or self.plc_mgr.simulator_mode:
                    await asyncio.sleep(1.0)
                    self.notify_inbound_ready()

                await self.log_event(
                    f"⏳ [Bước 2-3] Chờ nhân viên đặt hàng tại O1 (Cảm biến O1 kích DI2 sang Robot)..."
                )

                inbound_ready_received = False
                step_start_time = time.time()
                while not inbound_ready_received and not self._stop_requested:
                    try:
                        token = await asyncio.wait_for(self._inbound_ready_queue.get(), timeout=1.0)
                        if token is True:
                            inbound_ready_received = True
                            break
                    except asyncio.TimeoutError:
                        # [Issue #7]: Giám sát Timeout 180s
                        if time.time() - step_start_time > 180.0:
                            await self.log_event(
                                "⚠️ [Bước 2-3] Quá 180s chưa có kiện hàng tại O1 (chưa kích DI2). Vui lòng đặt hàng hoặc bấm Dừng."
                            )
                            step_start_time = time.time()

                if self._stop_requested:
                    return

                # -------------------------------------------------------------
                # Bước 1 & 4a: Sau khi có hàng tại O1, tìm ô kho khả dụng trong kho (A1..B3)
                # -------------------------------------------------------------
                async with async_session() as session:
                    inv_mgr = InventoryManager(session)
                    empty_slot = await inv_mgr.find_available_slot()
                    if not empty_slot:
                        await self.log_event("⚠️ Cả 6 ô kho hoạt động đã ĐẦY (6/6)! Tự động kết thúc chu trình nạp hàng!")
                        self.status = "COMPLETED"
                        break
                    target_slot = empty_slot.slot_name

                self.inbound_current_slot = target_slot

                # -------------------------------------------------------------
                # Bước 4b: Có hàng tại O1 -> Backend yêu cầu PLC hạ Z xuống tầng Băng tải O1
                # -------------------------------------------------------------
                z_o1 = slot_to_z_level("O1")
                z_o1_label = Z_LEVEL_LABELS.get(z_o1, str(z_o1))
                await self.log_event(
                    f"⬇️ [Bước 4] Đã phát hiện hàng tại O1 và phân bổ ô {target_slot}! Yêu cầu PLC di chuyển Z đến tầng {z_o1_label} (DB15.DBW8={z_o1})..."
                )
                if not await self.plc_mgr.move_z_to_level(z_o1, timeout_sec=60.0):
                    self.status = "ERROR"
                    await self.log_event(f"❌ PLC trục Z không thể đến tầng Băng tải {z_o1_label}! Dừng chu trình nạp.")
                    return

                # [Issue #1]: Xác thực kép Trục Z in-position trước khi Robot gắp tại O1
                if not await self._verify_z_in_position(z_o1, z_o1_label):
                    self.status = "ERROR"
                    await self.log_event(f"❌ Trục Z chưa ổn định ở tầng Băng tải O1! Dừng chu trình nạp.")
                    return

                # -------------------------------------------------------------
                # Bước 5: Robot gắp hàng tại O1
                # -------------------------------------------------------------
                await self.log_event(f"🤖 [Bước 5] Trục Z đã ở tầng O1. Yêu cầu Robot gắp hàng tại O1 (PICK O1)...")
                try:
                    await self._execute_robot_command_safe(RobotCommand.PICK, slot="O1")
                except Exception as e:
                    logger.error("Lỗi Robot khi gắp hàng tại O1: %s", e)
                    self.status = "ERROR"
                    await self.log_event(f"❌ Lỗi Robot khi gắp hàng tại O1: {str(e)}")
                    return

                # [Issue #2]: Đánh dấu Robot đang giữ hàng
                self._holding_product_info = {
                    "source_slot": "O1",
                    "target_slot": target_slot,
                    "operation": "INBOUND",
                }

                # -------------------------------------------------------------
                # Bước 6: Quét mã QR kiện hàng qua Camera CAM01 (Tối đa 8s -> Tự động tắt Camera)
                # -------------------------------------------------------------
                await self.log_event("📷 [Bước 6] Robot đã gắp kiện hàng, đưa qua Camera CAM01 để quét mã QR (tối đa 8s)...")
                await system_ws_manager.broadcast("CAMERA_VISION_UPDATE", {
                    "status": "SCANNING",
                    "product_id": "Đang quét...",
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "message": f"📷 Nhân viên kho: Đang quét mã QR kiện hàng cho ô {target_slot} (tối đa 8s)...",
                })
                scanned_qr_text = None
                try:
                    scan_res = await self.cam_mgr.scan_qr_auto(timeout_sec=8.0, is_verify=False)
                    if scan_res.get("status") == "success" and scan_res.get("product_id"):
                        scanned_qr_text = scan_res.get("product_id")
                        await self.log_event(f"✅ Camera đã nhận diện mã QR: {scanned_qr_text}")
                    else:
                        err_msg = scan_res.get("message", "Quá thời gian quét mã QR 8s")
                        await system_ws_manager.broadcast("CAMERA_VISION_UPDATE", {
                            "status": "NOT_FOUND",
                            "product_id": f"PROD_{target_slot}",
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "message": f"⚠️ Nhân viên kho: Hết thời gian 8s không quét được QR ({err_msg}). Sử dụng mã mặc định và tiếp tục nạp vào kho.",
                        })
                        await self.log_event(f"⚠️ Hết thời gian 8s không quét được QR ({err_msg}), sử dụng mã mặc định và tiếp tục chu trình.")
                except Exception as cam_err:
                    logger.debug("Staff Inbound camera scan note: %s", cam_err)
                    await self.log_event(f"⚠️ Lỗi đọc camera: {cam_err}. Tiếp tục cất hàng vào kho.")
                finally:
                    try:
                        self.cam_mgr.stop_camera()
                        logger.info("📷 Staff Inbound: Đã tự động tắt Camera CAM01 ngay sau Bước 6 quét QR.")
                    except Exception as stop_err:
                        logger.warning("Lỗi khi tắt Camera sau Bước 6 Inbound: %s", stop_err)

                qr_code = scanned_qr_text or f"SP_STAFF_{(self.inbound_current_count + 1):03d}"
                prod_id = scanned_qr_text or f"PROD_{target_slot}"
                self.last_scanned_qr = qr_code
                if scanned_qr_text:
                    await system_ws_manager.broadcast("CAMERA_VISION_UPDATE", {
                        "status": "DETECTED",
                        "product_id": prod_id,
                        "qr_code": qr_code,
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "message": f"✅ Nhân viên kho: Đã nhận diện mã QR kiện hàng: {prod_id}",
                    })

                # -------------------------------------------------------------
                # Bước 7: Backend yêu cầu PLC nâng trục Z lên tầng ô kho
                # -------------------------------------------------------------
                z_slot = slot_to_z_level(target_slot)
                z_slot_label = Z_LEVEL_LABELS.get(z_slot, str(z_slot))
                await self.log_event(
                    f"⬆️ [Bước 7] Quét QR xong. Yêu cầu PLC di chuyển trục Z lên tầng {z_slot_label} (DB15.DBW8={z_slot})..."
                )
                if not await self.plc_mgr.move_z_to_level(z_slot, timeout_sec=60.0):
                    self.status = "ERROR"
                    await self.log_event(f"❌ PLC trục Z không thể đến tầng {z_slot_label}! Dừng chu trình nạp.")
                    return

                # [Issue #1]: Xác thực kép Trục Z in-position trước khi Robot cất vào ô
                if not await self._verify_z_in_position(z_slot, z_slot_label):
                    self.status = "ERROR"
                    await self.log_event(f"❌ Trục Z chưa ổn định ở tầng {z_slot_label}! Dừng chu trình để bảo vệ Robot.")
                    return

                # -------------------------------------------------------------
                # Bước 8 & 9: Robot cất kiện hàng vào ô kho (STORE target_slot)
                # -------------------------------------------------------------
                await self.log_event(f"📦 [Bước 8] Trục Z đã đến tầng {z_slot_label}. Yêu cầu Robot cất kiện {prod_id} vào ô {target_slot}...")
                try:
                    await self._execute_robot_command_safe(RobotCommand.STORE, slot=target_slot)
                except Exception as e:
                    logger.error("Lỗi Robot khi cất hàng vào ô %s: %s", target_slot, e)
                    self.status = "ERROR"
                    await self.log_event(f"❌ Lỗi Robot khi cất vào ô {target_slot}: {str(e)}")
                    return

                # Xóa cờ holding sau khi đã cất an toàn vào ô
                self._holding_product_info = None

                # Cập nhật CSDL kho: Ô chuyển sang CÓ HÀNG (OCCUPIED)
                async with async_session() as session:
                    inv_mgr = InventoryManager(session)

                    stmt_p = select(ProductRecord).where(ProductRecord.product_id == prod_id)
                    res_p = await session.execute(stmt_p)
                    prod = res_p.scalar_one_or_none()
                    if not prod:
                        prod = ProductRecord(
                            product_id=prod_id,
                            product_name=f"Sản phẩm {prod_id}",
                            qr_code=qr_code,
                            status="IN_STOCK",
                            created_at=datetime.utcnow(),
                        )
                        session.add(prod)
                    else:
                        prod.status = "IN_STOCK"
                        prod.qr_code = qr_code
                        prod.updated_at = datetime.utcnow()
                    await session.commit()

                    await inv_mgr.update_slot(
                        slot_name=target_slot,
                        status=StorageSlotStatus.OCCUPIED,
                        product_id=prod_id,
                        qr_code=qr_code,
                        auto_broadcast=True,
                    )

                await self.log_event(
                    f"📥 [Cập nhật kho] Đã nạp thành công kiện {prod_id} vào ô {target_slot} -> Trạng thái: CÓ HÀNG (OCCUPIED)!"
                )

                self.inbound_current_count += 1
                if self.plc_mgr.simulator_mode:
                    await self.plc_mgr.increment_staff_count()

                await self.log_event(
                    f"✅ [Bước 9] Đã cất kiện hàng vào ô {target_slot} thành công (Tổng nạp: {self.inbound_current_count} kiện). "
                    f"Robot kích xung DO2 báo PLC cho băng tải chạy tiếp kiện sau."
                )
                self.inbound_current_slot = None
                await self.broadcast_status()

                await asyncio.sleep(0.5)

            if self.status != "ERROR" and not self._stop_requested:
                self.status = "COMPLETED"
                await self.log_event(f"🎉 Hoàn tất phiên nạp hàng (Tổng cộng: {self.inbound_current_count} sản phẩm đã vào kho)!")

        except asyncio.CancelledError:
            self.status = "COMPLETED" if self.inbound_current_count > 0 else "CANCELLED"
            await self.log_event(f"🛑 Đã dừng nạp hàng (Tổng: {self.inbound_current_count} sản phẩm).")
        except Exception as err:
            logger.error("Inbound loop exception: %s", err, exc_info=True)
            self.status = "ERROR"
            await self.log_event(f"❌ Lỗi trong quá trình nạp hàng: {err}")
        finally:
            self._holding_product_info = None
            try:
                self.cam_mgr.stop_camera()
            except Exception as cam_err:
                logger.warning("Error stopping camera after staff inbound: %s", cam_err)
            device_lock_manager.unlock_station()
            self.inbound_current_slot = None
            await self.broadcast_status()


staff_operation_manager = StaffOperationManager.get_instance()


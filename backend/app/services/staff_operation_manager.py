import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database.repository import async_session
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

        # 1. Ensure we switch system mode to STAFF_OPERATION
        await system_mode_manager.set_operation_mode("STAFF_OPERATION")

        # 2. Send Target Quantity & Outbound Start to PLC
        await self.plc_mgr.set_staff_target_count(target_count)
        await self.plc_mgr.execute_command(PLCCommand.STAFF_MODE_ENABLE)
        await self.plc_mgr.execute_command(PLCCommand.STAFF_OUTBOUND_START)

        self.active_type = "OUTBOUND"
        self.status = "RUNNING"
        self.outbound_queue = resolved_slots
        self.outbound_completed = []
        self.outbound_current_slot = None
        self._stop_requested = False

        await self.log_event(f"🚀 Backend đã gửi xuống PLC: Chế độ Outbound Picking (Mục tiêu: {target_count} kiện: {', '.join(self.outbound_queue)})")

        # Launch worker task
        self._current_task = asyncio.create_task(self._run_outbound_loop())
        return self.get_status()

    async def cancel_outbound(self) -> Dict[str, Any]:
        if self.status != "RUNNING":
            return self.get_status()

        self._stop_requested = True
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()

        await self.plc_mgr.execute_command(PLCCommand.STAFF_OUTBOUND_CANCEL)
        device_lock_manager.unlock_station()
        self.status = "CANCELLED"
        await self.log_event("🛑 Tiến trình lấy hàng đã bị hủy bởi nhân viên.")
        return self.get_status()

    async def _run_outbound_loop(self) -> None:
        try:
            total_items = len(self.outbound_queue)
            while self.outbound_queue and not self._stop_requested:
                target_slot = self.outbound_queue[0]
                self.outbound_current_slot = target_slot
                await self.log_event(f"📦 Điều phối Robot xuất ô {target_slot} ra băng tải ({len(self.outbound_completed) + 1}/{total_items})...")

                # Bước Z: PLC nâng/hạ trục Z đến tầng ô kho trước khi Robot gắp
                z_level = slot_to_z_level(target_slot)
                z_label = Z_LEVEL_LABELS.get(z_level, str(z_level))
                await self.log_event(f"⬆️ PLC nâng trục Z đến tầng {z_label} (DB15.DBW8={z_level})...")
                if not await self.plc_mgr.move_z_to_level(z_level):
                    self.status = "ERROR"
                    await self.log_event(f"❌ PLC trục Z không thể đến tầng {z_label}! Dừng chu trình xuất.")
                    return

                # Giao toàn quyền chu trình cơ khí cho Robot & PLC:
                # Robot tự nhận tín hiệu DI2 (O1 trống) -> Gắp từ ô kho -> Đặt xuống O1 -> Kích xung DO2 sang PLC
                # PLC tự nhận DO2 -> Tự kích động cơ băng tải chạy đưa hàng ra cho nhân viên
                try:
                    await self.robot_mgr.execute_command(RobotCommand.OUTBOUND_CYCLE, slot=target_slot)
                except Exception as e:
                    logger.error("Lỗi điều khiển Robot chu trình xuất ô %s: %s", target_slot, e)
                    self.status = "ERROR"
                    await self.log_event(f"❌ Lỗi Robot khi xuất ô {target_slot}: {str(e)}")
                    return

                # Backend xử lý nghiệp vụ CSDL kho: Giải phóng ô kho thành EMPTY
                async with async_session() as session:
                    inv_mgr = InventoryManager(session)
                    await inv_mgr.update_slot(
                        slot_name=target_slot,
                        status=StorageSlotStatus.EMPTY,
                        product_id=None,
                        qr_code=None,
                    )

                self.outbound_completed.append(target_slot)
                self.outbound_queue.pop(0)
                self.outbound_current_slot = None

                # Đồng bộ bộ đếm sản phẩm (Trong Simulator mode cập nhật biến đếm ảo)
                await self.plc_mgr.increment_staff_count()
                await self.log_event(f"✅ Đã xuất xong ô {target_slot}. Băng tải tự động chuyển hàng đến nhân viên ({len(self.outbound_completed)}/{total_items}).")

                await self.broadcast_status()

            if not self._stop_requested:
                self.status = "COMPLETED"
                await self.log_event(f"🎉 Hoàn tất chu trình xuất ({len(self.outbound_completed)} kiện hàng đã chuyển ra băng tải)!")

        except asyncio.CancelledError:
            self.status = "CANCELLED"
            await self.log_event("🛑 Chu trình lấy hàng đã bị dừng.")
        except Exception as err:
            logger.error("Outbound loop exception: %s", err, exc_info=True)
            self.status = "ERROR"
            await self.log_event(f"❌ Lỗi trong quá trình lấy hàng: {err}")
        finally:
            device_lock_manager.unlock_station()
            self.outbound_current_slot = None
            await self.broadcast_status()

    # =========================================================================
    # INBOUND STORING FLOW (Nạp chủ động liên tục -> Tự kết thúc khi đầy kho hoặc bấm Dừng)
    # =========================================================================
    async def start_inbound(self) -> Dict[str, Any]:
        if self.status == "RUNNING":
            raise RuntimeError("Đang có tiến trình khác đang chạy. Vui lòng dừng hoặc chờ hoàn tất.")

        # Check safety interlock: ensure station is not busy with a Drone Mission
        if device_lock_manager.is_station_busy() and device_lock_manager._locks.get("STATION", {}).get("locked_by") != "STAFF_OPERATION":
            lock_mission = device_lock_manager.get_locking_mission_id("STATION")
            raise RuntimeError(f"Trạm Drone đang bận thực thi Nhiệm vụ #{lock_mission}. Vui lòng đợi hoàn tất trước khi thêm hàng!")

        # Acquire lock on hardware
        device_lock_manager.lock_device("STATION", locked_by="STAFF_OPERATION", reason="Nhân viên đang thêm hàng vào kho")
        device_lock_manager.lock_device("PLC01", locked_by="STAFF_OPERATION", reason="Nhân viên đang thêm hàng vào kho")
        device_lock_manager.lock_device("ROBOT01", locked_by="STAFF_OPERATION", reason="Nhân viên đang thêm hàng vào kho")

        await system_mode_manager.set_operation_mode("STAFF_OPERATION")

        # Enable Staff Mode & Inbound on PLC
        await self.plc_mgr.execute_command(PLCCommand.STAFF_MODE_ENABLE)
        await self.plc_mgr.execute_command(PLCCommand.STAFF_INBOUND_START)

        self.active_type = "INBOUND"
        self.status = "RUNNING"
        self.inbound_mode = "CONTINUOUS"
        self.inbound_target_count = 6
        self.inbound_current_count = 0
        self.inbound_current_slot = None
        self.last_scanned_qr = None
        self._stop_requested = False

        await self.log_event("📥 Bắt đầu nạp hàng chủ động (Liên tục: Tự kết thúc khi đầy 6 ô hoạt động A1..B3 hoặc nhân viên bấm Kết thúc)...")

        self._current_task = asyncio.create_task(self._run_inbound_loop())
        return self.get_status()

    async def stop_inbound(self) -> Dict[str, Any]:
        if self.status != "RUNNING":
            return self.get_status()

        self._stop_requested = True
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()

        await self.plc_mgr.execute_command(PLCCommand.STAFF_INBOUND_STOP)
        device_lock_manager.unlock_station()
        self.status = "COMPLETED"
        await self.log_event(f"🏁 Nhân viên đã bấm Kết thúc nạp hàng (Tổng nạp: {self.inbound_current_count} sản phẩm).")
        return self.get_status()

    async def _run_inbound_loop(self) -> None:
        try:
            while not self._stop_requested:
                # Bước 1: Backend quản lý CSDL: Phân bổ vị trí kho (tìm ô trống trong 6 ô hoạt động A1..B3)
                async with async_session() as session:
                    inv_mgr = InventoryManager(session)
                    empty_slot = await inv_mgr.find_available_slot()
                    if not empty_slot:
                        await self.log_event("⚠️ Cả 6 ô kho hoạt động đã ĐẦY (6/6)! Tự động kết thúc chu trình nạp hàng!")
                        self.status = "COMPLETED"
                        break
                    target_slot = empty_slot.slot_name

                self.inbound_current_slot = target_slot
                await self.log_event(f"📦 Đã phân bổ ô trống {target_slot}. Chờ PLC kích DI2 báo Robot có hàng tại O1...")

                # Bước 2: PLC kiểm tra cảm biến đầu băng tải và kích DI2 sang Robot (logic phần cứng PLC <-> Robot).
                # Robot nhận DI2 = 1 và gửi tín hiệu REQUEST_STORE_SLOT lên Backend.
                # (Trong chế độ mô phỏng, tự động mô phỏng tín hiệu sau khi sẵn sàng)
                if self.robot_mgr.simulator_mode:
                    await asyncio.sleep(0.8)

                if self._stop_requested:
                    break

                # Bước 3a: PLC nâng/hạ trục Z đến tầng Băng tải O1 trước khi Robot gắp
                z_o1 = slot_to_z_level("O1")
                z_o1_label = Z_LEVEL_LABELS.get(z_o1, str(z_o1))
                await self.log_event(f"⬆️ PLC di chuyển trục Z đến tầng {z_o1_label} (DB15.DBW8={z_o1})...")
                if not await self.plc_mgr.move_z_to_level(z_o1):
                    self.status = "ERROR"
                    await self.log_event(f"❌ PLC trục Z không thể đến tầng {z_o1_label}! Dừng chu trình nạp.")
                    return

                # Bước 3b: Backend nhận tín hiệu có hàng -> Yêu cầu Robot xuống gắp hàng tại O1 (PICK O1)
                await self.log_event("🤖 Robot nhận tín hiệu DI2 từ PLC có hàng tại O1! Backend điều phối Robot gắp hàng tại O1...")
                try:
                    await self.robot_mgr.execute_command(RobotCommand.PICK, slot="O1")
                except Exception as e:
                    logger.error("Lỗi Robot khi gắp hàng tại O1: %s", e)
                    self.status = "ERROR"
                    await self.log_event(f"❌ Lỗi Robot khi gắp hàng tại O1: {str(e)}")
                    return

                # Bước 4: Gắp hàng OK xong mới quét mã QR kiện hàng qua Camera CAM01 (tương tự UNLOAD_PRODUCT)
                await self.log_event("📷 Robot đã gắp hàng thành công, đưa kiện hàng qua Camera CAM01 để quét mã QR...")
                await system_ws_manager.broadcast("CAMERA_VISION_UPDATE", {
                    "status": "SCANNING",
                    "product_id": "Đang quét...",
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "message": f"📷 Nhân viên kho: Đang quét mã QR kiện hàng cho ô {target_slot}...",
                })
                scanned_qr_text = None
                try:
                    scan_res = await self.cam_mgr.scan_qr_auto(timeout_sec=4.0, is_verify=False)
                    if scan_res.get("status") == "success" and scan_res.get("product_id"):
                        scanned_qr_text = scan_res.get("product_id")
                        await self.log_event(f"✅ Camera đã nhận diện mã QR: {scanned_qr_text}")
                    else:
                        err_msg = scan_res.get("message", "Quá thời gian quét mã QR")
                        await system_ws_manager.broadcast("CAMERA_VISION_UPDATE", {
                            "status": "NOT_FOUND",
                            "product_id": f"PROD_{target_slot}",
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "message": f"⚠️ Nhân viên kho: Cảnh báo không quét được mã QR ({err_msg}). Sử dụng mã mặc định và tiếp tục nạp vào kho.",
                        })
                        await self.log_event(f"⚠️ Không nhận dạng được mã QR ({err_msg}), sử dụng mã mặc định và tiếp tục chu trình.")
                except Exception as cam_err:
                    logger.debug("Staff Inbound camera scan note: %s", cam_err)
                    await self.log_event(f"⚠️ Lỗi đọc camera: {cam_err}. Tiếp tục cất hàng vào kho.")

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

                # Bước 5a: PLC nâng/hạ trục Z đến tầng ô kho trước khi Robot cất
                z_slot = slot_to_z_level(target_slot)
                z_slot_label = Z_LEVEL_LABELS.get(z_slot, str(z_slot))
                await self.log_event(f"⬆️ PLC di chuyển trục Z đến tầng {z_slot_label} (DB15.DBW8={z_slot})...")
                if not await self.plc_mgr.move_z_to_level(z_slot):
                    self.status = "ERROR"
                    await self.log_event(f"❌ PLC trục Z không thể đến tầng {z_slot_label}! Dừng chu trình nạp.")
                    return

                # Bước 5b: Quét mã QR xong, Robot di chuyển cất hàng vào ô kho trống đã phân bổ (STORE target_slot)
                await self.log_event(f"📦 Robot di chuyển cất kiện hàng {prod_id} vào ô kho {target_slot}...")
                try:
                    await self.robot_mgr.execute_command(RobotCommand.STORE, slot=target_slot)
                except Exception as e:
                    logger.error("Lỗi Robot khi cất hàng vào ô %s: %s", target_slot, e)
                    self.status = "ERROR"
                    await self.log_event(f"❌ Lỗi Robot khi cất vào ô {target_slot}: {str(e)}")
                    return

                # Bước 6: Backend xử lý nghiệp vụ CSDL kho: Gán ô kho thành OCCUPIED
                async with async_session() as session:
                    inv_mgr = InventoryManager(session)
                    await inv_mgr.update_slot(
                        slot_name=target_slot,
                        status=StorageSlotStatus.OCCUPIED,
                        product_id=prod_id,
                        qr_code=qr_code,
                    )

                self.inbound_current_count += 1
                await self.plc_mgr.increment_staff_count()
                await self.log_event(f"✅ Đã nạp kiện hàng vào ô {target_slot} thành công (Tổng nạp: {self.inbound_current_count} kiện).")
                self.inbound_current_slot = None
                await self.broadcast_status()

                # Nghỉ ngắn giữa các lượt nạp
                await asyncio.sleep(0.5)

            if self.status != "ERROR" and not self._stop_requested:
                self.status = "COMPLETED"
                await self.log_event(f"🎉 Hoàn tất phiên nạp hàng (Tổng cộng: {self.inbound_current_count} sản phẩm đã vào kho)!")

        except asyncio.CancelledError:
            self.status = "COMPLETED"
            await self.log_event(f"🛑 Đã dừng nạp hàng (Tổng: {self.inbound_current_count} sản phẩm).")
        except Exception as err:
            logger.error("Inbound loop exception: %s", err, exc_info=True)
            self.status = "ERROR"
            await self.log_event(f"❌ Lỗi trong quá trình nạp hàng: {err}")
        finally:
            try:
                self.cam_mgr.stop_camera()
            except Exception as cam_err:
                logger.warning("Error stopping camera after staff inbound: %s", cam_err)
            device_lock_manager.unlock_station()
            self.inbound_current_slot = None
            await self.broadcast_status()


staff_operation_manager = StaffOperationManager.get_instance()

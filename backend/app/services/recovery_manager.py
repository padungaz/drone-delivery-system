import logging
from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import IntralogisticsMissionRecord, SystemLogRecord
from app.services.device_lock_manager import device_lock_manager
from app.services.plc_manager import PLCManager
from app.services.robot_manager import RobotManager
from app.websocket.manager import system_ws_manager

logger = logging.getLogger(__name__)


class RecoveryManager:
    """Startup & Fail-Safe Recovery Service.
    
    Responsibilities:
    1. Detect and recover orphaned missions left in 'RUNNING' or 'STATION_PROCESSING' state across server restarts.
    2. Reset interlock locks safely.
    3. Check hardware physical states (PLC clamps, Robot grip) and notify operator if physical recovery is needed.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.plc_mgr = PLCManager.get_instance()
        self.robot_mgr = RobotManager.get_instance()

    async def check_and_recover_on_startup(self) -> Dict[str, Any]:
        """Runs once during backend lifespan initialization."""
        logger.info("[RecoveryManager] 🔍 Checking database for orphaned missions & hardware state...")
        
        # 1. Clear any in-memory device locks on startup
        device_lock_manager.unlock_station()

        # 2. Find orphaned RUNNING missions
        stmt = select(IntralogisticsMissionRecord).where(
            IntralogisticsMissionRecord.status == "RUNNING"
        )
        res = await self.session.execute(stmt)
        orphaned_missions: List[IntralogisticsMissionRecord] = list(res.scalars().all())

        recovered_count = 0
        now = datetime.utcnow()

        for mission in orphaned_missions:
            logger.warning("[RecoveryManager] Found orphaned Mission #%d (%s) in phase '%s'. Marking FAILED.",
                           mission.id, mission.mission_type, mission.current_phase)
            mission.status = "FAILED"
            mission.state = "FAILED"
            mission.current_phase = "FAILED"
            mission.error_reason = "SYSTEM_RESTART_ORPHANED_TASK"
            mission.step_details = f"🛑 Nhiệm vụ bị gián đoạn do Hệ thống Backend Khởi động lại lúc {now.strftime('%H:%M:%S')}."
            mission.completed_at = now
            recovered_count += 1

            self.session.add(SystemLogRecord(
                log_type="ERROR_LOG",
                source="RECOVERY",
                message=f"Mission #{mission.id} recovered after system restart (Status set to FAILED)",
                created_at=now,
            ))

        if recovered_count > 0:
            await self.session.commit()
            logger.info("[RecoveryManager] ✅ Successfully cleaned up %d orphaned mission(s).", recovered_count)

            # Broadcast WebSocket alert
            await system_ws_manager.broadcast("SYSTEM_ALERT", {
                "level": "WARNING",
                "message": f"⚠️ Hệ thống vừa khởi động lại. Đã tự động thu hồi {recovered_count} nhiệm vụ bị gián đoạn. Vui lòng kiểm tra thiết bị!",
            })

        # 3. Check physical hardware safety states
        plc_state = self.plc_mgr.get_status()
        robot_state = self.robot_mgr.get_status()

        hardware_warning = False
        warning_notes = []

        if plc_state.plc_locked_state:
            hardware_warning = True
            warning_notes.append("PLC Drone Clamp đang ở trạng thái KHÓA (LOCKED)")

        if robot_state.holding_product:
            hardware_warning = True
            warning_notes.append(f"Robot Arm đang kẹp giữ sản phẩm ({robot_state.holding_product})")

        if hardware_warning:
            msg = f"⚠️ Cảnh báo an toàn phần cứng khi khởi động: {', '.join(warning_notes)}. Vui lòng kiểm tra trạm trước khi chạy AUTO!"
            logger.warning("[RecoveryManager] %s", msg)
            await system_ws_manager.broadcast("SYSTEM_ALERT", {
                "level": "WARNING",
                "message": msg,
            })

        return {
            "recovered_orphaned_missions": recovered_count,
            "hardware_warning": hardware_warning,
            "warning_notes": warning_notes,
            "timestamp": now.isoformat(),
        }

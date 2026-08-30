import asyncio
import logging
from datetime import datetime
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import IntralogisticsMissionRecord
from app.websocket.manager import system_ws_manager

logger = logging.getLogger(__name__)


class MissionQueueManager:
    """Service handling First In - First Out (FIFO) Mission Queue processing."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _serialize_mission(self, mission: IntralogisticsMissionRecord) -> dict:
        status_val = getattr(mission, "status", None) or getattr(mission, "state", None) or "WAITING"
        return {
            "id": mission.id,
            "order_id": mission.order_id,
            "mission_type": mission.mission_type,
            "drone_id": mission.drone_id,
            "product_id": mission.product_id,
            "target_slot": mission.target_slot,
            "status": status_val,
            "current_phase": mission.current_phase or "WAITING",
            "state": status_val,
            "priority": getattr(mission, "priority", 0) or 0,
            "error_reason": getattr(mission, "error_reason", None),
            "step_details": mission.step_details or "",
            "created_at": mission.created_at.isoformat() if mission.created_at else "",
            "started_at": mission.started_at.isoformat() if getattr(mission, "started_at", None) else None,
            "completed_at": mission.completed_at.isoformat() if getattr(mission, "completed_at", None) else None,
            "updated_at": mission.updated_at.isoformat() if mission.updated_at else "",
        }

    async def broadcast_queue_state(self) -> None:
        """Broadcast updated Queue state to all connected WebSockets clients."""
        try:
            active = await self.get_active_mission()
            waiting = await self.get_waiting_queue()
            
            payload = {
                "active_mission": self._serialize_mission(active) if active else None,
                "waiting_queue": [self._serialize_mission(m) for m in waiting],
                "total_waiting": len(waiting),
            }
            await system_ws_manager.broadcast("MISSION_QUEUE_UPDATE", payload)
        except Exception as err:
            logger.error("Error broadcasting MISSION_QUEUE_UPDATE: %s", err)

    async def add_mission_to_queue(
        self,
        mission_type: str,
        product_id: str,
        target_slot: str,
        drone_id: str = "UAV01",
        order_id: Optional[int] = None,
        priority: int = 0,
    ) -> IntralogisticsMissionRecord:
        """Create and enqueue a new mission with WAITING status."""
        mission = IntralogisticsMissionRecord(
            order_id=order_id,
            mission_type=mission_type.upper(),
            drone_id=drone_id,
            product_id=product_id,
            target_slot=target_slot,
            status="WAITING",
            current_phase="WAITING",
            state="WAITING",
            priority=priority,
            created_at=datetime.utcnow(),
        )
        self.session.add(mission)
        await self.session.commit()
        await self.session.refresh(mission)

        logger.info("[MissionQueueManager] Enqueued new mission #%s (%s slot %s)", mission.id, mission_type, target_slot)
        await self.broadcast_queue_state()
        return mission

    async def get_active_mission(self) -> Optional[IntralogisticsMissionRecord]:
        """Fetch current RUNNING mission if any."""
        stmt = (
            select(IntralogisticsMissionRecord)
            .where(IntralogisticsMissionRecord.status == "RUNNING")
            .order_by(IntralogisticsMissionRecord.id.asc())
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_waiting_queue(self) -> List[IntralogisticsMissionRecord]:
        """Fetch all WAITING missions sorted by Priority desc, ID asc (FIFO)."""
        stmt = (
            select(IntralogisticsMissionRecord)
            .where(IntralogisticsMissionRecord.status.in_(["WAITING", "QUEUED"]))
            .order_by(IntralogisticsMissionRecord.priority.desc(), IntralogisticsMissionRecord.id.asc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def cancel_mission(self, mission_id: int) -> Optional[IntralogisticsMissionRecord]:
        """Cancel a WAITING mission."""
        stmt = select(IntralogisticsMissionRecord).where(IntralogisticsMissionRecord.id == mission_id)
        res = await self.session.execute(stmt)
        mission = res.scalars().first()

        if not mission:
            return None

        if mission.status == "RUNNING":
            raise ValueError("Cannot cancel a RUNNING mission. Use pause/E-STOP.")

        mission.status = "CANCELLED"
        mission.state = "CANCELLED"
        mission.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(mission)

        await self.broadcast_queue_state()
        return mission

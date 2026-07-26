from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repository import get_session
from app.models.database import IntralogisticsMissionRecord
from app.models.schemas import IntralogisticsMissionCreate, IntralogisticsMissionResponse
from app.services.mission_manager import MissionManager
from app.websocket.manager import system_ws_manager

mission_router = APIRouter(prefix="/api/mission", tags=["Intralogistics Mission Manager"])


@mission_router.post("/pickup", response_model=IntralogisticsMissionResponse)
async def trigger_pickup_mission(
    req: IntralogisticsMissionCreate,
    session: AsyncSession = Depends(get_session),
):
    mgr = MissionManager(session)
    mission = await mgr.execute_drone_pickup(drone_id=req.drone_id, product_id=req.product_id)

    await system_ws_manager.broadcast("MISSION_PROGRESS", {
        "mission_id": mission.id,
        "type": mission.mission_type,
        "drone_id": mission.drone_id,
        "product_id": mission.product_id,
        "state": mission.state,
        "step_details": mission.step_details,
    })

    return mission


@mission_router.post("/delivery", response_model=IntralogisticsMissionResponse)
async def trigger_delivery_mission(
    req: IntralogisticsMissionCreate,
    session: AsyncSession = Depends(get_session),
):
    mgr = MissionManager(session)
    mission = await mgr.execute_drone_delivery(drone_id=req.drone_id, product_id=req.product_id)

    await system_ws_manager.broadcast("MISSION_PROGRESS", {
        "mission_id": mission.id,
        "type": mission.mission_type,
        "drone_id": mission.drone_id,
        "product_id": mission.product_id,
        "state": mission.state,
        "step_details": mission.step_details,
    })

    return mission


@mission_router.get("/history", response_model=List[IntralogisticsMissionResponse])
async def get_mission_history(
    session: AsyncSession = Depends(get_session),
):
    stmt = select(IntralogisticsMissionRecord).order_by(IntralogisticsMissionRecord.id.desc())
    res = await session.execute(stmt)
    return list(res.scalars().all())

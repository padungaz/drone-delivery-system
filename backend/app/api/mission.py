from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repository import get_session
from app.models.database import IntralogisticsMissionRecord
from app.models.schemas import IntralogisticsMissionCreate, IntralogisticsMissionResponse
from app.services.mission_manager import MissionManager
from app.websocket.manager import system_ws_manager

mission_router = APIRouter(tags=["Intralogistics Mission Manager"])


@mission_router.post("/api/mission/create", response_model=IntralogisticsMissionResponse)
@mission_router.post("/api/missions/create", response_model=IntralogisticsMissionResponse)
@mission_router.post("/api/mission/start", response_model=IntralogisticsMissionResponse)
@mission_router.post("/api/missions/start", response_model=IntralogisticsMissionResponse)
async def create_intralogistics_mission(
    req: IntralogisticsMissionCreate,
    session: AsyncSession = Depends(get_session),
):
    mgr = MissionManager(session)
    m_type = (req.mission_type or req.task or "DRONE_PICKUP").upper()
    if m_type in ("DRONE_PICKUP", "PICKUP"):
        mission = await mgr.execute_drone_pickup(drone_id=req.drone_id, product_id=req.product_id)
    else:
        mission = await mgr.execute_drone_delivery(drone_id=req.drone_id, product_id=req.product_id)

    mission_dict = {
        "id": mission.id,
        "mission_type": mission.mission_type,
        "drone_id": mission.drone_id,
        "product_id": mission.product_id,
        "target_slot": mission.target_slot,
        "state": mission.state,
        "step_details": mission.step_details,
        "created_at": mission.created_at.isoformat() if mission.created_at else "",
        "updated_at": mission.updated_at.isoformat() if mission.updated_at else "",
    }

    await system_ws_manager.broadcast("MISSION_PROGRESS", {
        "mission": mission_dict,
        "mission_id": mission.id,
        "type": mission.mission_type,
        "drone_id": mission.drone_id,
        "product_id": mission.product_id,
        "state": mission.state,
        "step_details": mission.step_details,
    })

    return mission


@mission_router.post("/api/mission/pickup", response_model=IntralogisticsMissionResponse)
@mission_router.post("/api/missions/pickup", response_model=IntralogisticsMissionResponse)
async def trigger_pickup_mission(
    req: IntralogisticsMissionCreate,
    session: AsyncSession = Depends(get_session),
):
    mgr = MissionManager(session)
    mission = await mgr.execute_drone_pickup(drone_id=req.drone_id, product_id=req.product_id)

    mission_dict = {
        "id": mission.id,
        "mission_type": mission.mission_type,
        "drone_id": mission.drone_id,
        "product_id": mission.product_id,
        "target_slot": mission.target_slot,
        "state": mission.state,
        "step_details": mission.step_details,
        "created_at": mission.created_at.isoformat() if mission.created_at else "",
        "updated_at": mission.updated_at.isoformat() if mission.updated_at else "",
    }

    await system_ws_manager.broadcast("MISSION_PROGRESS", {
        "mission": mission_dict,
        "mission_id": mission.id,
        "type": mission.mission_type,
        "drone_id": mission.drone_id,
        "product_id": mission.product_id,
        "state": mission.state,
        "step_details": mission.step_details,
    })

    return mission


@mission_router.post("/api/mission/delivery", response_model=IntralogisticsMissionResponse)
@mission_router.post("/api/missions/delivery", response_model=IntralogisticsMissionResponse)
async def trigger_delivery_mission(
    req: IntralogisticsMissionCreate,
    session: AsyncSession = Depends(get_session),
):
    mgr = MissionManager(session)
    mission = await mgr.execute_drone_delivery(drone_id=req.drone_id, product_id=req.product_id)

    mission_dict = {
        "id": mission.id,
        "mission_type": mission.mission_type,
        "drone_id": mission.drone_id,
        "product_id": mission.product_id,
        "target_slot": mission.target_slot,
        "state": mission.state,
        "step_details": mission.step_details,
        "created_at": mission.created_at.isoformat() if mission.created_at else "",
        "updated_at": mission.updated_at.isoformat() if mission.updated_at else "",
    }

    await system_ws_manager.broadcast("MISSION_PROGRESS", {
        "mission": mission_dict,
        "mission_id": mission.id,
        "type": mission.mission_type,
        "drone_id": mission.drone_id,
        "product_id": mission.product_id,
        "state": mission.state,
        "step_details": mission.step_details,
    })

    return mission


@mission_router.get("/api/mission", response_model=List[IntralogisticsMissionResponse])
@mission_router.get("/api/missions", response_model=List[IntralogisticsMissionResponse])
@mission_router.get("/api/mission/history", response_model=List[IntralogisticsMissionResponse])
@mission_router.get("/api/missions/history", response_model=List[IntralogisticsMissionResponse])
async def get_mission_history(
    session: AsyncSession = Depends(get_session),
):
    stmt = select(IntralogisticsMissionRecord).order_by(IntralogisticsMissionRecord.id.desc())
    res = await session.execute(stmt)
    return list(res.scalars().all())


@mission_router.get("/api/mission/active", response_model=Optional[IntralogisticsMissionResponse])
@mission_router.get("/api/missions/active", response_model=Optional[IntralogisticsMissionResponse])
async def get_active_mission(
    session: AsyncSession = Depends(get_session),
):
    mgr = MissionManager(session)
    active = await mgr.get_active_mission()
    return active


@mission_router.post("/api/mission/pause")
@mission_router.post("/api/missions/pause")
async def pause_active_mission(
    session: AsyncSession = Depends(get_session),
):
    mgr = MissionManager(session)
    mission = await mgr.pause_mission()
    if not mission:
        raise HTTPException(status_code=400, detail="No active mission to pause")
    return {"message": "Nhiệm vụ đã tạm dừng", "mission": mission}


@mission_router.post("/api/mission/resume")
@mission_router.post("/api/missions/resume")
async def resume_active_mission(
    session: AsyncSession = Depends(get_session),
):
    mgr = MissionManager(session)
    mission = await mgr.resume_mission()
    if not mission:
        raise HTTPException(status_code=400, detail="No paused mission to resume")
    return {"message": "Nhiệm vụ đã tiếp tục", "mission": mission}


class QROverrideRequest(BaseModel):
    product_id: str


@mission_router.post("/api/mission/override-qr")
@mission_router.post("/api/missions/override-qr")
async def override_qr_code(
    req: QROverrideRequest,
    session: AsyncSession = Depends(get_session),
):
    mgr = MissionManager(session)
    mission = await mgr.manual_override_qr(req.product_id)
    if not mission:
        raise HTTPException(status_code=400, detail="No active mission to override QR")
    return {"message": f"Đã nhập mã QR thủ công: {req.product_id}", "mission": mission}


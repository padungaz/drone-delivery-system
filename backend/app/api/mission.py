from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repository import get_session
from app.models.database import IntralogisticsMissionRecord
from app.models.schemas import (
    IntralogisticsMissionCreate,
    IntralogisticsMissionResponse,
    MissionQueueResponse,
)
from app.services.mission_manager import MissionManager
from app.services.mission_queue_manager import MissionQueueManager
from app.websocket.manager import system_ws_manager

mission_router = APIRouter(tags=["Intralogistics Mission Manager"])


def _format_mission_response(mission: IntralogisticsMissionRecord) -> dict:
    status_val = getattr(mission, "status", None) or getattr(mission, "state", None) or "WAITING"
    phase_val = getattr(mission, "current_phase", None) or "WAITING"
    return {
        "id": mission.id,
        "order_id": getattr(mission, "order_id", None),
        "mission_type": mission.mission_type,
        "drone_id": mission.drone_id,
        "product_id": mission.product_id,
        "target_slot": mission.target_slot,
        "status": status_val,
        "current_phase": phase_val,
        "state": status_val,
        "priority": getattr(mission, "priority", 0) or 0,
        "error_reason": getattr(mission, "error_reason", None),
        "step_details": mission.step_details or "",
        "created_at": mission.created_at,
        "started_at": getattr(mission, "started_at", None),
        "completed_at": getattr(mission, "completed_at", None),
        "updated_at": mission.updated_at,
    }


@mission_router.get("/api/mission/queue", response_model=MissionQueueResponse)
@mission_router.get("/api/missions/queue", response_model=MissionQueueResponse, include_in_schema=False)
async def get_mission_queue(
    session: AsyncSession = Depends(get_session),
):
    q_mgr = MissionQueueManager(session)
    active = await q_mgr.get_active_mission()
    waiting = await q_mgr.get_waiting_queue()
    
    # Calculate totals
    stmt_comp = select(IntralogisticsMissionRecord).where(IntralogisticsMissionRecord.status == "COMPLETED")
    res_comp = await session.execute(stmt_comp)
    total_completed = len(res_comp.scalars().all())

    stmt_fail = select(IntralogisticsMissionRecord).where(IntralogisticsMissionRecord.status == "FAILED")
    res_fail = await session.execute(stmt_fail)
    total_failed = len(res_fail.scalars().all())

    return {
        "active_mission": _format_mission_response(active) if active else None,
        "waiting_queue": [_format_mission_response(m) for m in waiting],
        "total_waiting": len(waiting),
        "total_completed": total_completed,
        "total_failed": total_failed,
    }


@mission_router.post("/api/mission/{mission_id}/cancel")
@mission_router.post("/api/missions/{mission_id}/cancel", include_in_schema=False)
async def cancel_waiting_mission(
    mission_id: int,
    session: AsyncSession = Depends(get_session),
):
    q_mgr = MissionQueueManager(session)
    try:
        mission = await q_mgr.cancel_mission(mission_id)
        if not mission:
            raise HTTPException(status_code=404, detail=f"Mission #{mission_id} not found")
        return {"message": f"Nhiệm vụ #{mission_id} đã bị hủy thành công", "mission": _format_mission_response(mission)}
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@mission_router.post("/api/mission/start", response_model=IntralogisticsMissionResponse)

@mission_router.post("/api/missions/start", response_model=IntralogisticsMissionResponse, include_in_schema=False)
@mission_router.post("/api/mission/create", response_model=IntralogisticsMissionResponse, include_in_schema=False)
@mission_router.post("/api/missions/create", response_model=IntralogisticsMissionResponse, include_in_schema=False)
async def create_intralogistics_mission(
    req: IntralogisticsMissionCreate,
    session: AsyncSession = Depends(get_session),
):
    mgr = MissionManager(session)
    m_type = (req.mission_type or req.task or "DRONE_PICKUP").upper()
    if m_type in ("DRONE_PICKUP", "PICKUP"):
        mission = await mgr.execute_drone_pickup(drone_id=req.drone_id, product_id=req.product_id, order_id=req.order_id)
    else:
        mission = await mgr.execute_drone_delivery(drone_id=req.drone_id, product_id=req.product_id, order_id=req.order_id)

    mission_dict = _format_mission_response(mission)

    await system_ws_manager.broadcast("MISSION_PROGRESS", {
        "mission": mission_dict,
        "mission_id": mission.id,
        "type": mission.mission_type,
        "drone_id": mission.drone_id,
        "product_id": mission.product_id,
        "status": mission_dict["status"],
        "current_phase": mission_dict["current_phase"],
        "state": mission_dict["status"],
        "step_details": mission.step_details,
    })

    return mission_dict


@mission_router.post("/api/mission/pickup", response_model=IntralogisticsMissionResponse)
@mission_router.post("/api/missions/pickup", response_model=IntralogisticsMissionResponse, include_in_schema=False)
async def trigger_pickup_mission(
    req: IntralogisticsMissionCreate,
    session: AsyncSession = Depends(get_session),
):
    mgr = MissionManager(session)
    mission = await mgr.execute_drone_pickup(drone_id=req.drone_id, product_id=req.product_id, order_id=req.order_id)
    mission_dict = _format_mission_response(mission)

    await system_ws_manager.broadcast("MISSION_PROGRESS", {
        "mission": mission_dict,
        "mission_id": mission.id,
        "type": mission.mission_type,
        "drone_id": mission.drone_id,
        "product_id": mission.product_id,
        "status": mission_dict["status"],
        "current_phase": mission_dict["current_phase"],
        "state": mission_dict["status"],
        "step_details": mission.step_details,
    })

    return mission_dict


@mission_router.post("/api/mission/delivery", response_model=IntralogisticsMissionResponse)
@mission_router.post("/api/missions/delivery", response_model=IntralogisticsMissionResponse, include_in_schema=False)
async def trigger_delivery_mission(
    req: IntralogisticsMissionCreate,
    session: AsyncSession = Depends(get_session),
):
    mgr = MissionManager(session)
    mission = await mgr.execute_drone_delivery(drone_id=req.drone_id, product_id=req.product_id, order_id=req.order_id)
    mission_dict = _format_mission_response(mission)

    await system_ws_manager.broadcast("MISSION_PROGRESS", {
        "mission": mission_dict,
        "mission_id": mission.id,
        "type": mission.mission_type,
        "drone_id": mission.drone_id,
        "product_id": mission.product_id,
        "status": mission_dict["status"],
        "current_phase": mission_dict["current_phase"],
        "state": mission_dict["status"],
        "step_details": mission.step_details,
    })

    return mission_dict


@mission_router.get("/api/mission/history", response_model=List[IntralogisticsMissionResponse])
@mission_router.get("/api/missions/history", response_model=List[IntralogisticsMissionResponse], include_in_schema=False)
@mission_router.get("/api/mission", response_model=List[IntralogisticsMissionResponse], include_in_schema=False)
@mission_router.get("/api/missions", response_model=List[IntralogisticsMissionResponse], include_in_schema=False)
async def get_mission_history(
    session: AsyncSession = Depends(get_session),
):
    stmt = select(IntralogisticsMissionRecord).order_by(IntralogisticsMissionRecord.id.desc())
    res = await session.execute(stmt)
    missions = res.scalars().all()
    return [_format_mission_response(m) for m in missions]


@mission_router.get("/api/mission/active", response_model=Optional[IntralogisticsMissionResponse])
@mission_router.get("/api/missions/active", response_model=Optional[IntralogisticsMissionResponse], include_in_schema=False)
async def get_active_mission(
    session: AsyncSession = Depends(get_session),
):
    mgr = MissionManager(session)
    active = await mgr.get_active_mission()
    return _format_mission_response(active) if active else None


@mission_router.post("/api/mission/pause")
@mission_router.post("/api/missions/pause", include_in_schema=False)
async def pause_active_mission(
    session: AsyncSession = Depends(get_session),
):
    mgr = MissionManager(session)
    mission = await mgr.pause_mission()
    if not mission:
        raise HTTPException(status_code=400, detail="No active mission to pause")
    return {"message": "Nhiệm vụ đã tạm dừng", "mission": _format_mission_response(mission)}


@mission_router.post("/api/mission/resume")
@mission_router.post("/api/missions/resume", include_in_schema=False)
async def resume_active_mission(
    session: AsyncSession = Depends(get_session),
):
    mgr = MissionManager(session)
    mission = await mgr.resume_mission()
    if not mission:
        raise HTTPException(status_code=400, detail="No paused mission to resume")
    return {"message": "Nhiệm vụ đã tiếp tục", "mission": _format_mission_response(mission)}


class QROverrideRequest(BaseModel):
    product_id: str


@mission_router.post("/api/mission/override-qr")
@mission_router.post("/api/missions/override-qr", include_in_schema=False)
async def override_qr_code(
    req: QROverrideRequest,
    session: AsyncSession = Depends(get_session),
):
    mgr = MissionManager(session)
    mission = await mgr.manual_override_qr(req.product_id)
    if not mission:
        raise HTTPException(status_code=400, detail="No active mission to override QR")
    return {"message": f"Đã nhập mã QR thủ công: {req.product_id}", "mission": _format_mission_response(mission)}


@mission_router.post("/api/mission/auto-start")
@mission_router.post("/api/missions/auto-start", include_in_schema=False)
async def auto_start_batch_missions(
    session: AsyncSession = Depends(get_session),
):
    mgr = MissionManager(session)
    mission = await mgr.auto_dispatch_next_mission()
    if not mission:
        return {"message": "Không có đơn hàng nào chờ chạy hoặc đang có nhiệm vụ đang hoạt động.", "started": False}
    return {"message": f"🚀 Đã kích hoạt Chạy Tự Động Hàng Chờ! Đang thực thi Đơn Nhiệm vụ #{mission.id}", "started": True, "mission": _format_mission_response(mission)}

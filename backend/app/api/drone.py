from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repository import Repository, get_session
from app.models.schemas import DroneStatusResponse, IntralogisticsMissionCreate
from app.services.drone_manager import drone_manager
from app.services.mission_manager import MissionManager
from app.websocket.manager import system_ws_manager

drone_router = APIRouter(prefix="/api/drone", tags=["Drone Management"])


@drone_router.get("/status", response_model=DroneStatusResponse)
async def get_drone_status(
    drone_id: str = "UAV01",
    session: AsyncSession = Depends(get_session),
):
    repo = Repository(session)
    record = await repo.get_drone_status(drone_id)
    telemetry = drone_manager.get_latest_telemetry(drone_id)

    if record is None and telemetry is None:
        return DroneStatusResponse(
            drone_id=drone_id,
            connected=False,
            can_stop=False,
        )

    return DroneStatusResponse(
        drone_id=drone_id,
        connected=record.connected if record else True,
        last_telemetry=telemetry,
        can_stop=False,
    )


@drone_router.post("/mission")
async def create_drone_mission(
    req: IntralogisticsMissionCreate,
    session: AsyncSession = Depends(get_session),
):
    mgr = MissionManager(session)
    if req.task.upper() == "PICKUP":
        mission = await mgr.execute_drone_pickup(drone_id=req.drone_id, product_id=req.product_id)
    elif req.task.upper() == "DELIVERY":
        mission = await mgr.execute_drone_delivery(drone_id=req.drone_id, product_id=req.product_id)
    else:
        raise HTTPException(status_code=400, detail="Invalid task. Must be 'PICKUP' or 'DELIVERY'")

    # Broadcast mission update via WebSocket
    await system_ws_manager.broadcast("MISSION_PROGRESS", {
        "mission_id": mission.id,
        "type": mission.mission_type,
        "drone_id": mission.drone_id,
        "state": mission.state,
        "step_details": mission.step_details,
    })

    return {
        "status": "SUCCESS",
        "mission_id": mission.id,
        "mission_type": mission.mission_type,
        "state": mission.state,
        "step_details": mission.step_details,
    }

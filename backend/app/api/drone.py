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
    task_type = (req.mission_type or req.task or "PICKUP").upper()
    if "PICKUP" in task_type:
        mission = await mgr.execute_drone_pickup(drone_id=req.drone_id, product_id=req.product_id)
    elif "DELIVERY" in task_type:
        mission = await mgr.execute_drone_delivery(drone_id=req.drone_id, product_id=req.product_id)
    else:
        raise HTTPException(status_code=400, detail="Invalid mission type. Must be 'DRONE_PICKUP' or 'DRONE_DELIVERY'")

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


# =============================================================================
# UAV MISSION FLIGHT SIMULATION API (Pure Software Simulation)
# =============================================================================
from typing import Optional
from pydantic import BaseModel
from app.services.uav_mission_simulator import uav_mission_simulator


class UavSimFlightRequest(BaseModel):
    mission_id: Optional[int] = None
    mission_type: str = "DRONE_DELIVERY"
    home_lat: Optional[float] = None
    home_lon: Optional[float] = None
    target_lat: Optional[float] = None
    target_lon: Optional[float] = None
    speed_multiplier: float = 1.0


class UavSimSpeedRequest(BaseModel):
    speed_multiplier: float = 1.0


@drone_router.post("/sim/start-flight")
async def start_sim_flight(req: UavSimFlightRequest):
    """Start simulated mission flight (Home -> Target -> Return -> Land)."""
    res = await uav_mission_simulator.start_flight(
        mission_id=req.mission_id,
        mission_type=req.mission_type,
        home_lat=req.home_lat,
        home_lon=req.home_lon,
        target_lat=req.target_lat,
        target_lon=req.target_lon,
        speed_multiplier=req.speed_multiplier,
    )
    return {"status": "SUCCESS", "flight": res}


@drone_router.post("/sim/pause-flight")
async def pause_sim_flight():
    """Pause simulated mission flight (Hover in place)."""
    res = await uav_mission_simulator.pause_flight()
    return {"status": "SUCCESS", "flight": res}


@drone_router.post("/sim/resume-flight")
async def resume_sim_flight():
    """Resume simulated mission flight."""
    res = await uav_mission_simulator.resume_flight()
    return {"status": "SUCCESS", "flight": res}


@drone_router.post("/sim/rtl-flight")
async def rtl_sim_flight():
    """Trigger Return To Home (RTL) for simulated flight."""
    res = await uav_mission_simulator.return_to_home()
    return {"status": "SUCCESS", "flight": res}


@drone_router.post("/sim/stop-flight")
async def stop_sim_flight():
    """Cancel and stop simulated flight."""
    res = await uav_mission_simulator.cancel_flight()
    return {"status": "SUCCESS", "flight": res}


@drone_router.post("/sim/set-speed")
async def set_sim_flight_speed(req: UavSimSpeedRequest):
    """Change flight speed multiplier (1x, 2x, 5x)."""
    uav_mission_simulator.set_speed(req.speed_multiplier)
    return {"status": "SUCCESS", "speed_multiplier": req.speed_multiplier}


@drone_router.get("/sim/status")
async def get_sim_flight_status():
    """Get live status of simulated mission flight."""
    return uav_mission_simulator.get_status()


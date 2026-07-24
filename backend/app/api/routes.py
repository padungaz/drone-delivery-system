import logging

from fastapi import APIRouter, Depends, HTTPException, WebSocket

from app.database.repository import Repository, async_session
from app.models.schemas import (
    DroneStatusResponse,
    MissionAction,
    MissionCommand,
    MissionHistoryItem,
)
from app.services.drone_service import drone_service, mission_service
from app.websocket.handler import forward_mission_to_drone, handle_client_websocket, handle_drone_websocket, manager

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_repo():
    async with async_session() as session:
        yield Repository(session)


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "drone-delivery-backend"}


@router.get("/drones/{drone_id}/status", response_model=DroneStatusResponse)
async def get_drone_status(drone_id: str, repo: Repository = Depends(get_repo)):
    return await drone_service.get_status(repo, drone_id)


@router.get("/missions/history", response_model=list[MissionHistoryItem])
async def get_mission_history(repo: Repository = Depends(get_repo)):
    return await mission_service.get_history(repo)


@router.post("/missions/start")
async def start_mission(command: MissionCommand, repo: Repository = Depends(get_repo)):
    if not manager.is_drone_connected(command.drone_id):
        raise HTTPException(status_code=503, detail=f"Drone {command.drone_id} not connected")

    start_cmd = mission_service.build_start_command(command)
    record = await repo.create_mission(start_cmd)

    sent = await forward_mission_to_drone(start_cmd)
    if not sent:
        await repo.update_mission_status(record.id, "FAILED")
        raise HTTPException(status_code=503, detail="Failed to send mission to drone")

    await repo.update_mission_status(record.id, "ACTIVE")
    logger.info("Mission started for drone %s", command.drone_id)
    return {"status": "START_MISSION sent", "mission_id": record.id}


@router.post("/missions/pickup-complete")
async def pickup_complete(command: MissionCommand, repo: Repository = Depends(get_repo)):
    """Operator confirms package has been picked up.
    Drone must be in WAIT_PICKUP_CONFIRM state (validated on Pi side).
    """
    if not manager.is_drone_connected(command.drone_id):
        raise HTTPException(status_code=503, detail=f"Drone {command.drone_id} not connected")

    cmd = MissionCommand(
        action=MissionAction.PICKUP_COMPLETE,
        home_lat=command.home_lat,
        home_lon=command.home_lon,
        pickup_lat=command.pickup_lat,
        pickup_lon=command.pickup_lon,
        drop_lat=command.drop_lat,
        drop_lon=command.drop_lon,
        drone_id=command.drone_id,
    )
    record = await repo.create_mission(cmd)
    sent = await forward_mission_to_drone(cmd)
    if not sent:
        await repo.update_mission_status(record.id, "FAILED")
        raise HTTPException(status_code=503, detail="Failed to send PICKUP_COMPLETE to drone")

    await repo.update_mission_status(record.id, "PICKUP_CONFIRMED")
    logger.info("PICKUP_COMPLETE sent to drone %s", command.drone_id)
    return {"status": "PICKUP_COMPLETE sent", "mission_id": record.id}


@router.post("/missions/drop-complete")
async def drop_complete(command: MissionCommand, repo: Repository = Depends(get_repo)):
    """Operator confirms package has been delivered.
    Drone must be in WAIT_DROP_CONFIRM state (validated on Pi side).
    """
    if not manager.is_drone_connected(command.drone_id):
        raise HTTPException(status_code=503, detail=f"Drone {command.drone_id} not connected")

    cmd = MissionCommand(
        action=MissionAction.DROP_COMPLETE,
        home_lat=command.home_lat,
        home_lon=command.home_lon,
        pickup_lat=command.pickup_lat,
        pickup_lon=command.pickup_lon,
        drop_lat=command.drop_lat,
        drop_lon=command.drop_lon,
        drone_id=command.drone_id,
    )
    record = await repo.create_mission(cmd)
    sent = await forward_mission_to_drone(cmd)
    if not sent:
        await repo.update_mission_status(record.id, "FAILED")
        raise HTTPException(status_code=503, detail="Failed to send DROP_COMPLETE to drone")

    await repo.update_mission_status(record.id, "DROP_CONFIRMED")
    logger.info("DROP_COMPLETE sent to drone %s", command.drone_id)
    return {"status": "DROP_COMPLETE sent", "mission_id": record.id}


@router.post("/missions/force-rtl")
async def force_rtl(command: MissionCommand, repo: Repository = Depends(get_repo)):
    if not manager.is_drone_connected(command.drone_id):
        raise HTTPException(status_code=503, detail=f"Drone {command.drone_id} not connected")

    rtl_cmd = MissionCommand(
        action=MissionAction.FORCE_RTL,
        home_lat=command.home_lat,
        home_lon=command.home_lon,
        pickup_lat=command.pickup_lat,
        pickup_lon=command.pickup_lon,
        drop_lat=command.drop_lat,
        drop_lon=command.drop_lon,
        drone_id=command.drone_id,
    )
    record = await repo.create_mission(rtl_cmd)
    sent = await forward_mission_to_drone(rtl_cmd)
    if not sent:
        await repo.update_mission_status(record.id, "FAILED")
        raise HTTPException(status_code=503, detail="Failed to send FORCE_RTL to drone")

    await repo.update_mission_status(record.id, "RTL_SENT")
    return {"status": "FORCE_RTL sent", "mission_id": record.id}


@router.post("/missions/stop")
async def stop_mission(command: MissionCommand, repo: Repository = Depends(get_repo)):
    telemetry = drone_service.get_telemetry(command.drone_id)
    drone_service.validate_stop(telemetry)

    if not manager.is_drone_connected(command.drone_id):
        raise HTTPException(status_code=503, detail=f"Drone {command.drone_id} not connected")

    stop_cmd = MissionCommand(
        action=MissionAction.STOP,
        home_lat=command.home_lat,
        home_lon=command.home_lon,
        pickup_lat=command.pickup_lat,
        pickup_lon=command.pickup_lon,
        drop_lat=command.drop_lat,
        drop_lon=command.drop_lon,
        drone_id=command.drone_id,
    )
    record = await repo.create_mission(stop_cmd)
    sent = await forward_mission_to_drone(stop_cmd)
    if not sent:
        await repo.update_mission_status(record.id, "FAILED")
        raise HTTPException(status_code=503, detail="Failed to send STOP to drone")

    await repo.update_mission_status(record.id, "STOPPED")
    return {"status": "STOP sent", "mission_id": record.id}


# ---------------------------------------------------------------------------
# Camera test endpoints (lightweight — no mission record needed)
# ---------------------------------------------------------------------------

@router.post("/camera/start")
async def camera_start(drone_id: str = "drone-01"):
    """Send CAMERA_START command to drone to open USB camera + start ArUco detection."""
    if not manager.is_drone_connected(drone_id):
        raise HTTPException(status_code=503, detail=f"Drone {drone_id} not connected")

    sent = await manager.send_to_drone(drone_id, {
        "type": "command",
        "payload": {"action": "CAMERA_START"},
    })
    if not sent:
        raise HTTPException(status_code=503, detail="Failed to send CAMERA_START to drone")

    logger.info("CAMERA_START sent to drone %s", drone_id)
    return {"status": "CAMERA_START sent", "drone_id": drone_id}


@router.post("/camera/stop")
async def camera_stop(drone_id: str = "drone-01"):
    """Send CAMERA_STOP command to drone to close USB camera."""
    if not manager.is_drone_connected(drone_id):
        raise HTTPException(status_code=503, detail=f"Drone {drone_id} not connected")

    sent = await manager.send_to_drone(drone_id, {
        "type": "command",
        "payload": {"action": "CAMERA_STOP"},
    })
    if not sent:
        raise HTTPException(status_code=503, detail="Failed to send CAMERA_STOP to drone")

    logger.info("CAMERA_STOP sent to drone %s", drone_id)
    return {"status": "CAMERA_STOP sent", "drone_id": drone_id}


@router.post("/missions/set-mode")
async def set_mode(mode: str, drone_id: str = "drone-01"):
    """Send SET_MODE command to drone."""
    if not manager.is_drone_connected(drone_id):
        raise HTTPException(status_code=503, detail=f"Drone {drone_id} not connected")

    sent = await manager.send_to_drone(drone_id, {
        "type": "command",
        "payload": {"action": "SET_MODE", "mode": mode},
    })
    if not sent:
        raise HTTPException(status_code=503, detail="Failed to send SET_MODE to drone")

    logger.info("SET_MODE (%s) sent to drone %s", mode, drone_id)
    return {"status": "SET_MODE sent", "drone_id": drone_id}


@router.post("/missions/move-relative")
async def move_relative(dx: float = 0.0, dy: float = 0.0, dz: float = 0.0, drone_id: str = "drone-01"):
    """Send MOVE_RELATIVE command to drone."""
    if not manager.is_drone_connected(drone_id):
        raise HTTPException(status_code=503, detail=f"Drone {drone_id} not connected")

    sent = await manager.send_to_drone(drone_id, {
        "type": "command",
        "payload": {"action": "MOVE_RELATIVE", "dx": dx, "dy": dy, "dz": dz},
    })
    if not sent:
        raise HTTPException(status_code=503, detail="Failed to send MOVE_RELATIVE to drone")

    logger.info("MOVE_RELATIVE (dx=%.1f, dy=%.1f, dz=%.1f) sent to drone %s", dx, dy, dz, drone_id)
    return {"status": "MOVE_RELATIVE sent", "drone_id": drone_id}


@router.post("/missions/arm")
async def arm_drone(drone_id: str = "drone-01"):
    """Send ARM command to drone (manual arm, outside mission flow)."""
    if not manager.is_drone_connected(drone_id):
        raise HTTPException(status_code=503, detail=f"Drone {drone_id} not connected")

    sent = await manager.send_to_drone(drone_id, {
        "type": "command",
        "payload": {"action": "ARM"},
    })
    if not sent:
        raise HTTPException(status_code=503, detail="Failed to send ARM to drone")

    logger.info("ARM sent to drone %s", drone_id)
    return {"status": "ARM sent", "drone_id": drone_id}


@router.post("/missions/disarm")
async def disarm_drone(force: bool = False, drone_id: str = "drone-01"):
    """Send DISARM command to drone."""
    if not manager.is_drone_connected(drone_id):
        raise HTTPException(status_code=503, detail=f"Drone {drone_id} not connected")

    sent = await manager.send_to_drone(drone_id, {
        "type": "command",
        "payload": {"action": "DISARM", "force": force},
    })
    if not sent:
        raise HTTPException(status_code=503, detail="Failed to send DISARM to drone")

    logger.info("DISARM (force=%s) sent to drone %s", force, drone_id)
    return {"status": "DISARM sent", "drone_id": drone_id}


@router.websocket("/ws/drone/{drone_id}")
async def drone_websocket(websocket: WebSocket, drone_id: str):
    async with async_session() as session:
        repo = Repository(session)
        await handle_drone_websocket(websocket, drone_id, repo)


@router.websocket("/ws/client")
async def client_websocket(websocket: WebSocket):
    await handle_client_websocket(websocket)

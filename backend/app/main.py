import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.customer_routes import customer_router
from app.api.device import device_router
from app.api.drone import drone_router
from app.api.inventory import inventory_router
from app.api.mission import mission_router
from app.api.plc import plc_router
from app.api.robot import robot_router
from app.api.station import station_router
from app.api.fleet import fleet_router
from app.api.staff import staff_router
from app.api.routes import router
from app.config import settings
from app.database.repository import async_session, init_db
from app.models.schemas import DeviceHeartbeatRequest, DeviceRegisterRequest, DeviceStatus, DeviceType
from app.services.camera_manager import CameraManager
from app.services.device_manager import DeviceManager
from app.services.inventory_manager import InventoryManager
from app.services.plc_manager import PLCManager
from app.services.robot_manager import RobotManager
from app.services.fleet_manager import fleet_manager
from app.websocket.manager import system_ws_manager
from app.websocket.handler import manager as drone_ws_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class RoutinePollingFilter(logging.Filter):
    """Filter out routine high-frequency polling GET 200 OK requests to keep console logs clean."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        polling_patterns = (
            "GET /api/device/list",
            "GET /api/mission/queue",
            "GET /api/device/logs",
            "GET /api/inventory/slots",
            "GET /api/plc/status",
            "GET /api/robot/status",
            "GET /api/station/status",
            "GET /api/fleet",
            "GET /api/mission/active",
        )
        if any(pattern in msg for pattern in polling_patterns) and " 200 " in msg:
            return False
        return True


# Apply filter to uvicorn access logs
logging.getLogger("uvicorn.access").addFilter(RoutinePollingFilter())


async def heartbeat_monitor_task():
    """Background task syncing device heartbeats and checking timeouts every 5 seconds."""
    while True:
        try:
            await asyncio.sleep(5)
            async with async_session() as session:
                mgr = DeviceManager(session)

                # Sync PLC01 heartbeat — ping PLC to check if TCP connection is still alive
                plc_mgr = PLCManager.get_instance()
                await plc_mgr.check_connection()
                plc_status = DeviceStatus.ONLINE if (plc_mgr.is_connected or plc_mgr.simulator_mode) else DeviceStatus.OFFLINE
                await mgr.update_heartbeat(DeviceHeartbeatRequest(name="PLC01", status=plc_status))

                # Sync ROBOT01 heartbeat based on RobotManager state
                robot_mgr = RobotManager.get_instance()
                await robot_mgr.check_connection()
                robot_status = DeviceStatus.ONLINE if (robot_mgr.is_connected or robot_mgr.simulator_mode) else DeviceStatus.OFFLINE
                await mgr.update_heartbeat(DeviceHeartbeatRequest(name="ROBOT01", status=robot_status))

                # Sync CAM01 heartbeat based on CameraManager state
                cam_mgr = CameraManager.get_instance()
                cam_info = cam_mgr.get_status()
                cam_status = DeviceStatus.ONLINE if (cam_info.get("is_active") or cam_info.get("simulator_mode")) else DeviceStatus.OFFLINE
                await mgr.update_heartbeat(DeviceHeartbeatRequest(name="CAM01", status=cam_status))

                # Sync UAV01 heartbeat based on Drone WebSocket connection or simulator mode
                uav_sim = os.getenv("UAV_SIMULATOR_MODE", "false").lower() in ("true", "1")
                uav_connected = drone_ws_manager.is_drone_connected("UAV01") or drone_ws_manager.is_drone_connected("drone-01") or uav_sim
                uav_status = DeviceStatus.ONLINE if uav_connected else DeviceStatus.OFFLINE
                await mgr.update_heartbeat(DeviceHeartbeatRequest(name="UAV01", status=uav_status))

                # Broadcast realtime heartbeat & status via WebSocket
                await system_ws_manager.broadcast("DEVICE_HEARTBEAT", {
                    "device_name": "PLC01",
                    "status": plc_status.value,
                })
                await system_ws_manager.broadcast("DEVICE_HEARTBEAT", {
                    "device_name": "ROBOT01",
                    "status": robot_status.value,
                })
                await system_ws_manager.broadcast("DEVICE_HEARTBEAT", {
                    "device_name": "CAM01",
                    "status": cam_status.value,
                })
                await system_ws_manager.broadcast("PLC_STATUS", plc_mgr.get_status().model_dump())
                await system_ws_manager.broadcast("ROBOT_STATUS", robot_mgr.get_status().model_dump())
                await system_ws_manager.broadcast("CAMERA_STATUS", cam_info)
                await fleet_manager.broadcast_fleet_state()

                timed_out = await mgr.check_device_timeouts()
                for dev_name in timed_out:
                    await system_ws_manager.broadcast("DEVICE_TIMEOUT", {
                        "device_name": dev_name,
                        "status": "OFFLINE",
                    })
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Error in heartbeat monitor task: %s", exc)


from app.services.recovery_manager import RecoveryManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Silence routine HTTP access logs from uvicorn so console is clean
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    await init_db()
    # Seed 9 storage slots & 4 LAN devices (UAV01, PLC01, ROBOT01, CAM01)
    async with async_session() as session:
        # 1. Run startup recovery for orphaned missions & hardware state check
        recovery_mgr = RecoveryManager(session)
        await recovery_mgr.check_and_recover_on_startup()

        inventory_mgr = InventoryManager(session)
        await inventory_mgr.init_default_slots()

        dev_mgr = DeviceManager(session)
        plc_ip = os.getenv("PLC_IP", "192.168.58.10")
        robot_ip = os.getenv("ROBOT_IP", "192.168.57.2")
        await dev_mgr.register_device(DeviceRegisterRequest(name="UAV01", type=DeviceType.UAV, ip="192.168.137.88", port=14550))
        await dev_mgr.register_device(DeviceRegisterRequest(name="PLC01", type=DeviceType.PLC, ip=plc_ip, port=102))
        await dev_mgr.register_device(DeviceRegisterRequest(name="ROBOT01", type=DeviceType.ROBOT, ip=robot_ip, port=8090))
        cam_idx = int(os.getenv("CAMERA_INDEX", "0"))
        await dev_mgr.register_device(DeviceRegisterRequest(name="CAM01", type=DeviceType.CAMERA, ip="USB_CAMERA", port=cam_idx))

        # Sync live singleton hardware managers with stored device configurations
        all_devs = await dev_mgr.get_all_devices()
        for d in all_devs:
            if d.device_name == "ROBOT01":
                RobotManager.get_instance().update_config(
                    robot_ip=d.ip_address,
                    robot_port=d.port,
                    simulator_mode=d.simulator_mode,
                )
            elif d.device_name == "PLC01":
                PLCManager.get_instance().update_config(
                    plc_ip=d.ip_address,
                    rack=d.rack,
                    slot=d.slot,
                    db_number=d.db_number,
                    simulator_mode=d.simulator_mode,
                )
            elif d.device_name == "CAM01":
                CameraManager.get_instance().update_config(
                    simulator_mode=d.simulator_mode,
                    camera_index=int(d.port) if d.port is not None else 0,
                )


    # Start background heartbeat monitor
    monitor = asyncio.create_task(heartbeat_monitor_task())

    # Start PLC Watchdog heartbeat (DB15.DBX0.7) if explicitly enabled.
    # Only activate after the S7-1200 program has matching TON watchdog logic.
    # Enable via env: PLC_WATCHDOG_ENABLED=true
    plc_mgr = PLCManager.get_instance()
    if os.getenv("PLC_WATCHDOG_ENABLED", "false").lower() in ("true", "1", "yes"):
        await plc_mgr.start_watchdog()
        logger.info("PLC Watchdog heartbeat enabled (DB15.DBX0.7 toggling every 1s)")
    else:
        logger.info("PLC Watchdog disabled (set PLC_WATCHDOG_ENABLED=true to enable after PLC program update)")

    logger.info("Smart Intralogistics Controller Backend started on %s:%d", settings.host, settings.port)
    yield

    # Shutdown: stop watchdog cleanly before closing connections
    await plc_mgr.stop_watchdog()
    monitor.cancel()
    logger.info("Backend shutting down")


app = FastAPI(
    title="Smart Intralogistics Controller System",
    description="LAN-based Centralized Orchestrator for UAV, PLC S7-1200, FAIRINO Robot Arm, QR Vision & Smart Warehouse",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_important_actions(request: Request, call_next):
    """Log meaningful state-modifying actions while skipping repetitive polling."""
    method = request.method
    path = request.url.path
    if method in ("POST", "PUT", "DELETE", "PATCH"):
        client_ip = request.client.host if request.client else "unknown"
        logger.info("👉 [ACTION] %s %s (from %s)", method, path, client_ip)
    return await call_next(request)

# Existing routers (Backward Compatible)
app.include_router(router)
app.include_router(customer_router)

# Smart Intralogistics Routers
app.include_router(device_router)
app.include_router(drone_router)
app.include_router(plc_router)
app.include_router(robot_router)
app.include_router(station_router)
app.include_router(inventory_router)
app.include_router(mission_router)
app.include_router(fleet_router)
app.include_router(staff_router)


@app.websocket("/ws/system")
async def websocket_system_endpoint(websocket: WebSocket):
    await system_ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        system_ws_manager.disconnect(websocket)

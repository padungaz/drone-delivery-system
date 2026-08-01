import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.customer_routes import customer_router
from app.api.device import device_router
from app.api.drone import drone_router
from app.api.inventory import inventory_router
from app.api.mission import mission_router
from app.api.plc import plc_router
from app.api.robot import robot_router
from app.api.routes import router
from app.config import settings
from app.database.repository import async_session, init_db
from app.models.schemas import DeviceHeartbeatRequest, DeviceRegisterRequest, DeviceStatus, DeviceType
from app.services.device_manager import DeviceManager
from app.services.inventory_manager import InventoryManager
from app.services.plc_manager import PLCManager
from app.services.robot_manager import RobotManager
from app.storage.repository import StorageRepository
from app.storage.routes import storage_router
from app.websocket.manager import system_ws_manager
from app.websocket.handler import manager as drone_ws_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


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
                robot_status = DeviceStatus.ONLINE if (robot_mgr.is_connected or robot_mgr.simulator_mode) else DeviceStatus.OFFLINE
                await mgr.update_heartbeat(DeviceHeartbeatRequest(name="ROBOT01", status=robot_status))

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
                await system_ws_manager.broadcast("PLC_STATUS", plc_mgr.get_status().model_dump())
                await system_ws_manager.broadcast("ROBOT_STATUS", robot_mgr.get_status().model_dump())

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Seed 9 storage slots & 3 LAN devices (UAV01, PLC01, ROBOT01)
    async with async_session() as session:
        storage_repo = StorageRepository(session)
        await storage_repo.init_storage_slots()
        inventory_mgr = InventoryManager(session)
        await inventory_mgr.init_default_slots()

        dev_mgr = DeviceManager(session)
        plc_ip = os.getenv("PLC_IP", "192.168.58.10")
        await dev_mgr.register_device(DeviceRegisterRequest(name="UAV01", type=DeviceType.UAV, ip="192.168.137.88"))
        await dev_mgr.register_device(DeviceRegisterRequest(name="PLC01", type=DeviceType.PLC, ip=plc_ip))
        await dev_mgr.register_device(DeviceRegisterRequest(name="ROBOT01", type=DeviceType.ROBOT, ip="192.168.58.2"))
        await dev_mgr.remove_device("CAM01")

    # Start background heartbeat monitor
    monitor = asyncio.create_task(heartbeat_monitor_task())
    logger.info("Smart Intralogistics Controller Backend started on %s:%d", settings.host, settings.port)
    yield
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Existing routers (Backward Compatible)
app.include_router(router)
app.include_router(customer_router)
app.include_router(storage_router)

# Smart Intralogistics Routers
app.include_router(device_router)
app.include_router(drone_router)
app.include_router(plc_router)
app.include_router(robot_router)
app.include_router(inventory_router)
app.include_router(mission_router)


@app.websocket("/ws/system")
async def websocket_system_endpoint(websocket: WebSocket):
    await system_ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        system_ws_manager.disconnect(websocket)

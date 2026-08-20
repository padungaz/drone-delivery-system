import asyncio
import logging
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.repository import async_session, init_db
from app.services.camera_manager import CameraManager
from app.services.qr_scanner_service import QRScannerService
from app.services.plc_manager import PLCManager
from app.services.robot_manager import RobotManager
from app.services.station_service import StationService
from app.services.system_mode_manager import system_mode_manager
from app.models.schemas import StorageSlotStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestCameraModes")


async def test_camera_config_and_status():
    """Test 1: Updating CAM01 config toggles simulator_mode dynamically."""
    await init_db()
    cam_mgr = CameraManager.get_instance()
    
    # Toggle to Simulator
    cam_mgr.update_config(simulator_mode=True)
    status_sim = cam_mgr.get_status()
    assert status_sim["simulator_mode"] is True
    assert status_sim["device_name"] == "CAM01"
    assert status_sim["type"] == "CAMERA"
    
    # Toggle to Real
    cam_mgr.update_config(simulator_mode=False)
    status_real = cam_mgr.get_status()
    assert status_real["simulator_mode"] is False


async def test_camera_auto_scan_in_station_fsm():
    """Test 2: StationService FSM executes real CameraManager.scan_qr_auto at Step 5 and Step 8."""
    await init_db()
    cam_mgr = CameraManager.get_instance()
    cam_mgr.update_config(simulator_mode=True)  # Using simulator for automated CI test

    plc_mgr = PLCManager.get_instance()
    plc_mgr.simulator_mode = True

    robot_mgr = RobotManager.get_instance()
    robot_mgr.simulator_mode = True

    async with async_session() as session:
        station_svc = StationService.get_instance()

        # 1. Test execute_load_product (Step 5 QR Verify)
        res_load = await station_svc.execute_load_product(
            target_slot="A1",
            product_id="TEST_PROD_CAM_VERIFY",
            session=session,
        )
        assert res_load is True
        assert station_svc.status == "COMPLETED"
        assert station_svc.current_operation == "LOAD_PRODUCT"

        # 2. Test execute_unload_product (Step 8 QR Scan)
        res_unload = await station_svc.execute_unload_product(
            target_slot="A2",
            product_id="TEST_PROD_CAM_SCAN",
            session=session,
        )
        assert res_unload is True
        assert station_svc.status == "COMPLETED"
        assert station_svc.current_operation == "UNLOAD_PRODUCT"


async def test_camera_manual_api_endpoints():
    """Test 3: Manual Camera API endpoints (Start/Stop stream, QR test trigger, and Config update)."""
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Start Camera
        res_start = await client.post("/api/device/camera/start")
        assert res_start.status_code == 200
        assert res_start.json()["status"] == "DONE"

        # 2. Test Manual QR Scan
        res_scan = await client.post("/api/device/camera/qr_scan", json={"qr_code": "PROD-MANUAL-1234"})
        assert res_scan.status_code == 200
        data = res_scan.json()
        assert data["command"] == "QR_SCAN"
        assert data["result"]["status"] in ("success", "already_assigned")

        # 3. Stop Camera
        res_stop = await client.post("/api/device/camera/stop")
        assert res_stop.status_code == 200
        assert res_stop.json()["status"] == "DONE"

        # 4. Update CAM01 Device Config via API
        res_cfg = await client.put("/api/device/config/CAM01", json={"simulator_mode": True})
        assert res_cfg.status_code == 200
        assert res_cfg.json()["simulator_mode"] is True
        assert CameraManager.get_instance().get_status()["simulator_mode"] is True


if __name__ == "__main__":
    async def run_all():
        logger.info("=== Running Camera Modes & Station Vision Test Suite ===")
        await test_camera_config_and_status()
        logger.info("✓ Test 1: Camera Config & Status Toggle PASSED!")

        await test_camera_auto_scan_in_station_fsm()
        logger.info("✓ Test 2: StationService FSM Auto QR Scan & Verify PASSED!")

        await test_camera_manual_api_endpoints()
        logger.info("✓ Test 3: Manual Camera Controls & API Endpoints PASSED!")

        logger.info("=== ALL CAMERA MODES INTEGRATION TESTS PASSED! ===")

    asyncio.run(run_all())

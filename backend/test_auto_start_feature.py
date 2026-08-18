import asyncio
import logging
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.repository import async_session, init_db
from app.services.system_mode_manager import system_mode_manager
from app.services.plc_manager import PLCManager
from app.services.robot_manager import RobotManager
from app.services.mission_manager import MissionManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestAutoStartFeature")


@pytest.mark.asyncio
async def test_auto_mode_defaults_to_standby():
    """Test 1: Switching to AUTO mode enters STANDBY state without auto-dispatching."""
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Switch to AUTO
        res = await client.post("/api/system/mode", json={"mode": "AUTO"})
        assert res.status_code == 200

        # Check mode status
        res_status = await client.get("/api/system/mode")
        assert res_status.status_code == 200
        data = res_status.json()
        assert data["mode"] == "AUTO"
        assert data["auto_state"] == "STANDBY"
        assert data["is_scheduler_active"] is False
        assert data["is_auto_running"] is False
        assert system_mode_manager.can_auto_dispatch() is False


@pytest.mark.asyncio
async def test_start_auto_triggers_homing_and_running_state():
    """Test 2: POST /api/system/start-auto executes homing, sets auto_state=RUNNING, and activates scheduler."""
    await init_db()
    RobotManager.get_instance().simulator_mode = True
    PLCManager.get_instance().simulator_mode = True
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a WAITING mission in queue
        async with async_session() as session:
            mgr = MissionManager(session)
            mission = await mgr.execute_drone_pickup(
                drone_id="UAV01",
                product_id="TEST_PROD_START_AUTO",
                auto_run=False
            )
            assert mission.status == "WAITING"

        # Execute Auto Start
        res_start = await client.post("/api/system/start-auto")
        assert res_start.status_code == 200
        start_data = res_start.json()
        assert start_data["status"] == "SUCCESS"
        assert start_data["auto_state"] == "RUNNING"
        assert start_data["mode"] == "AUTO"

        # Verify SystemModeManager state
        assert system_mode_manager.is_auto_running() is True
        assert system_mode_manager.can_auto_dispatch() is True

        # Verify Robot and PLC are homed / ready
        robot_mgr = RobotManager.get_instance()
        plc_mgr = PLCManager.get_instance()
        assert robot_mgr.state in ("READY", "MOVING", "PICKING")
        assert plc_mgr.plc_on is True


@pytest.mark.asyncio
async def test_pause_auto_pauses_scheduler():
    """Test 3: POST /api/system/pause-auto sets auto_state=PAUSED and stops auto-dispatch."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Pause Auto
        res_pause = await client.post("/api/system/pause-auto")
        assert res_pause.status_code == 200
        pause_data = res_pause.json()
        assert pause_data["auto_state"] == "PAUSED"
        assert pause_data["is_scheduler_active"] is False
        assert system_mode_manager.can_auto_dispatch() is False

        # Resume Queue
        res_resume = await client.post("/api/system/resume-queue")
        assert res_resume.status_code == 200
        resume_data = res_resume.json()
        assert resume_data["auto_state"] == "RUNNING"
        assert system_mode_manager.can_auto_dispatch() is True


@pytest.mark.asyncio
async def test_manual_mode_disables_scheduler():
    """Test 4: Switching to MANUAL mode sets auto_state=PAUSED and locks auto scheduler."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/system/mode", json={"mode": "MANUAL"})
        assert res.status_code == 200

        res_status = await client.get("/api/system/mode")
        data = res_status.json()
        assert data["mode"] == "MANUAL"
        assert data["auto_state"] == "PAUSED"
        assert data["is_scheduler_active"] is False
        assert system_mode_manager.can_auto_dispatch() is False


if __name__ == "__main__":
    async def run_all():
        logger.info("=== Running Station Auto Start Feature Test Suite ===")
        await test_auto_mode_defaults_to_standby()
        logger.info("✓ Test 1: AUTO Mode Default to STANDBY PASSED!")

        await test_start_auto_triggers_homing_and_running_state()
        logger.info("✓ Test 2: Start Auto Homing & RUNNING Transition PASSED!")

        await test_pause_auto_pauses_scheduler()
        logger.info("✓ Test 3: Pause & Resume Auto Scheduler PASSED!")

        await test_manual_mode_disables_scheduler()
        logger.info("✓ Test 4: MANUAL Mode Scheduler Disabling PASSED!")

        logger.info("=== ALL STATION AUTO START TESTS PASSED! ===")

    asyncio.run(run_all())

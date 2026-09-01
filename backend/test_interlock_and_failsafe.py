import asyncio
import logging
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.repository import async_session, init_db
from app.models.database import IntralogisticsMissionRecord
from app.services.device_lock_manager import device_lock_manager
from app.services.system_mode_manager import system_mode_manager
from app.services.plc_manager import PLCManager
from app.services.robot_manager import RobotManager
from app.services.recovery_manager import RecoveryManager
from app.services.mission_manager import MissionManager
from app.models.schemas import PLCCommand, RobotCommand

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestInterlockFailSafe")


@pytest.mark.asyncio
async def test_safety_interlock_blocks_manual_commands():
    """Phase 1 Test: Manual commands return HTTP 409 Conflict when Station is locked by AUTO mission."""
    await init_db()
    PLCManager.get_instance().simulator_mode = True
    RobotManager.get_instance().simulator_mode = True
    device_lock_manager.unlock_station()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Lock station as if AUTO mission #999 is running
        device_lock_manager.lock_station(999, "Testing Safety Interlock")
        assert device_lock_manager.is_station_busy() is True
        assert device_lock_manager.is_device_locked("PLC01") is True
        assert device_lock_manager.is_device_locked("ROBOT01") is True

        # 2. Try manual PLC motion command -> Must get 409
        res_plc = await client.post("/api/plc/lock", json={"action": "LOCK"})
        assert res_plc.status_code == 409
        assert "bị khóa bởi Nhiệm vụ AUTO #999" in res_plc.json()["detail"]

        # 3. Try manual Robot motion command -> Must get 409
        res_robot = await client.post("/api/robot/pick", json={"slot": "A1"})
        assert res_robot.status_code == 409
        assert "bị khóa bởi Nhiệm vụ AUTO #999" in res_robot.json()["detail"]

        # 4. Try manual Device raw command -> Must get 409
        res_raw = await client.post("/api/device/send-raw-command", json={
            "device_name": "ROBOT01",
            "command_text": "PICK A1"
        })
        assert res_raw.status_code == 409

        # 5. Emergency STOP command -> Must be ALLOWED (200)
        res_stop = await client.post("/api/plc/stop")
        assert res_stop.status_code == 200

        # 6. Unlock station -> Commands allowed again
        device_lock_manager.unlock_station()
        assert device_lock_manager.is_station_busy() is False

        res_plc_after = await client.post("/api/plc/lock", json={"action": "LOCK"})
        assert res_plc_after.status_code == 200


@pytest.mark.asyncio
async def test_manual_mode_prevents_auto_dispatch():
    """Phase 2 Test: In MANUAL mode, new missions remain in WAITING and are not dispatched."""
    await init_db()
    device_lock_manager.unlock_station()
    async with async_session() as session:
        # Set to MANUAL mode
        await system_mode_manager.set_mode("MANUAL")
        assert system_mode_manager.is_manual() is True
        assert system_mode_manager.can_auto_dispatch() is False

        mgr = MissionManager(session)
        # Create pickup mission
        mission = await mgr.execute_drone_pickup(
            drone_id="UAV01",
            product_id="TEST_PROD_MANUAL",
            auto_run=True
        )

        # In MANUAL mode, mission must stay WAITING, not RUNNING
        assert mission.status == "WAITING"
        assert device_lock_manager.is_station_busy() is False

        # Switch back to AUTO mode
        await system_mode_manager.set_mode("AUTO")
        assert system_mode_manager.is_auto() is True


@pytest.mark.asyncio
async def test_robot_dock_slot_maps_to_n1():
    """Phase 5 Test: Slot 'DOCK' or 'PAD' maps to 'N1' for Fairino socket protocol."""
    robot_mgr = RobotManager.get_instance()
    robot_mgr.simulator_mode = True

    # Execute PICK with slot='DOCK'
    res = await robot_mgr.execute_command(RobotCommand.PICK_PRODUCT, slot="DOCK")
    assert res.current_slot == "N1"

    # Execute PLACE with slot='DOCK'
    res2 = await robot_mgr.execute_command(RobotCommand.PLACE_PRODUCT, slot="DOCK")
    assert res2.current_slot == "N1"


@pytest.mark.asyncio
async def test_plc_unlock_keeps_drone_detected():
    """Phase 6 Test: UNLOCK_DRONE does not reset drone_detected to False."""
    plc_mgr = PLCManager.get_instance()
    plc_mgr.simulator_mode = True
    plc_mgr.set_drone_detected(True)

    # Lock drone
    await plc_mgr.execute_command(PLCCommand.LOCK_DRONE)
    assert plc_mgr.drone_locked is True
    assert plc_mgr.drone_detected is True

    # Unlock drone -> drone_detected must STILL be True
    await plc_mgr.execute_command(PLCCommand.UNLOCK_DRONE)
    assert plc_mgr.drone_locked is False
    assert plc_mgr.drone_detected is True


@pytest.mark.asyncio
async def test_plc_estop_and_error_interlock():
    """Phase 7 Test: PLC E-Stop and Error state reject motion commands with HTTP 400."""
    await init_db()
    plc_mgr = PLCManager.get_instance()
    plc_mgr.simulator_mode = True
    device_lock_manager.unlock_station()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Trigger Emergency Stop via API
        res_estop = await client.post("/api/plc/emergency-stop", json={"emergency_stop": True})
        assert res_estop.status_code == 200
        assert plc_mgr.emergency_stop is True

        # 2. Attempt motion command -> must fail with HTTP 400
        res_lock = await client.post("/api/plc/lock", json={"action": "LOCK"})
        assert res_lock.status_code == 400
        assert "Emergency Stop" in res_lock.json()["detail"]

        res_hatch = await client.post("/api/plc/hatch", json={"action": "OPEN"})
        assert res_hatch.status_code == 400
        assert "Emergency Stop" in res_hatch.json()["detail"]

        # 3. Emergency STOP_PLC is always allowed
        res_stop = await client.post("/api/plc/stop")
        assert res_stop.status_code == 200

        # 4. RESET_PLC clears emergency stop and error
        res_reset = await client.post("/api/plc/reset")
        assert res_reset.status_code == 200
        assert plc_mgr.emergency_stop is False
        assert plc_mgr.plc_error is False

        # 5. Motion commands are now operational
        res_lock_ok = await client.post("/api/plc/lock", json={"action": "LOCK"})
        assert res_lock_ok.status_code == 200


@pytest.mark.asyncio
async def test_recovery_manager_cleans_orphaned_missions():
    """Phase 9 Test: RecoveryManager recovers orphaned RUNNING missions on startup."""
    await init_db()
    async with async_session() as session:
        # Create an orphaned RUNNING mission
        orphaned = IntralogisticsMissionRecord(
            mission_type="DRONE_DELIVERY",
            drone_id="UAV01",
            product_id="ORPHANED_PROD",
            target_slot="A1",
            status="RUNNING",
            current_phase="STATION_PROCESSING",
            state="RUNNING",
        )
        session.add(orphaned)
        await session.commit()
        await session.refresh(orphaned)
        orphan_id = orphaned.id

        # Run RecoveryManager
        rec_mgr = RecoveryManager(session)
        result = await rec_mgr.check_and_recover_on_startup()
        assert result["recovered_orphaned_missions"] >= 1

        # Check that orphaned mission is now FAILED
        updated = await session.get(IntralogisticsMissionRecord, orphan_id)
        assert updated.status == "FAILED"
        assert updated.error_reason == "SYSTEM_RESTART_ORPHANED_TASK"


if __name__ == "__main__":
    async def run_all():
        logger.info("=== Running Safety Interlock & Fail-Safe Test Suite ===")
        PLCManager.get_instance().simulator_mode = True
        RobotManager.get_instance().simulator_mode = True
        await test_safety_interlock_blocks_manual_commands()
        logger.info("✓ Test 1: Safety Interlock Blocked Manual Commands (HTTP 409) PASSED!")

        await test_manual_mode_prevents_auto_dispatch()
        logger.info("✓ Test 2: System Mode AUTO/MANUAL Control PASSED!")

        await test_robot_dock_slot_maps_to_n1()
        logger.info("✓ Test 3: Fairino Robot N1 Protocol Mapping PASSED!")

        await test_plc_unlock_keeps_drone_detected()
        logger.info("✓ Test 4: PLC DB15 UNLOCK Drone Detected Preservation PASSED!")

        await test_recovery_manager_cleans_orphaned_missions()
        logger.info("✓ Test 5: Recovery Manager Startup Orphan Clean-up PASSED!")

        logger.info("=== ALL SAFETY, INTERLOCK & RECOVERY TESTS PASSED! ===")

    asyncio.run(run_all())

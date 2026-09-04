import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.robot_manager import RobotManager
from app.services.plc_manager import PLCManager
from app.services.staff_operation_manager import staff_operation_manager
from app.services.system_mode_manager import system_mode_manager
from app.services.device_lock_manager import device_lock_manager


@pytest.mark.asyncio
async def test_system_reset_tasks():
    """Verify system_reset_tasks forces all defaults, clears temp warehouse queue, and resets robot/PLC."""
    robot_mgr = RobotManager.get_instance()
    robot_mgr.simulator_mode = True
    robot_mgr.state = "MOVING"
    robot_mgr.current_slot = "A2"
    robot_mgr.holding_product = "PRD-1002"

    plc_mgr = PLCManager.get_instance()
    plc_mgr.simulator_mode = True
    plc_mgr.cmd_staff_outbound_cancel = True
    plc_mgr.cmd_staff_inbound_stop = True

    # Seed temporary outbound queue
    staff_operation_manager.outbound_queue = ["A1", "B2"]
    staff_operation_manager.outbound_current_slot = "A1"
    staff_operation_manager.status = "RUNNING"
    staff_operation_manager.active_type = "OUTBOUND"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/system/reset-tasks")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "SUCCESS"
        assert data["auto_state"] == "STANDBY"
        assert data["operation_mode"] == "STATION_AUTO"
        assert data["robot_state"] == "READY"

    # Verify temp warehouse / staff queue is cleared
    assert len(staff_operation_manager.outbound_queue) == 0
    assert staff_operation_manager.outbound_current_slot is None
    assert staff_operation_manager.status == "IDLE"
    assert staff_operation_manager.active_type is None

    # Verify robot is reset to default
    assert robot_mgr.state == "READY"
    assert robot_mgr.current_slot is None
    assert robot_mgr.holding_product is None
    assert robot_mgr._is_busy_moving is False

    # Verify PLC cancel bits cleared
    assert plc_mgr.cmd_staff_outbound_cancel is False
    assert plc_mgr.cmd_staff_inbound_stop is False
    assert plc_mgr.cmd_staff_mode_enable is False

    # Verify locks unlocked
    assert not device_lock_manager.is_device_locked("ROBOT01")
    assert not device_lock_manager.is_device_locked("PLC01")

import asyncio
import pytest
from app.database.repository import async_session
from app.models.schemas import RobotCommand, StorageSlotStatus
from app.services.inventory_manager import InventoryManager
from app.services.plc_manager import PLCManager
from app.services.robot_manager import RobotManager
from app.services.staff_operation_manager import staff_operation_manager


@pytest.mark.asyncio
async def test_z_position_safety_interlock():
    """Verify that _verify_z_in_position properly validates Z status before motion."""
    plc_mgr = PLCManager.get_instance()
    plc_mgr.simulator_mode = True

    # When Z is not in position
    plc_mgr.plc_z_in_position = False
    plc_mgr.current_z_level = 1
    assert await staff_operation_manager._verify_z_in_position(1, "Hàng A") is False

    # When Z level does not match target
    plc_mgr.plc_z_in_position = True
    plc_mgr.current_z_level = 2
    assert await staff_operation_manager._verify_z_in_position(1, "Hàng A") is False

    # When Z level matches and in position
    plc_mgr.plc_z_in_position = True
    plc_mgr.current_z_level = 1
    assert await staff_operation_manager._verify_z_in_position(1, "Hàng A") is True


@pytest.mark.asyncio
async def test_robot_manager_blocks_uncoordinated_fallback():
    """Verify that _handle_robot_pick_request and _handle_robot_store_request
    do NOT auto-assign and send PICK/STORE if StaffOperationManager is not running.
    """
    robot_mgr = RobotManager.get_instance()
    robot_mgr.simulator_mode = True

    # Ensure staff operation is IDLE
    staff_operation_manager.status = "IDLE"
    staff_operation_manager.active_type = None

    replies = []

    async def mock_send(msg: str):
        replies.append(msg)

    robot_mgr._send_raw_socket_reply = mock_send

    # Trigger pick request when idle -> should reply NONE, not PICK <slot>
    await robot_mgr._handle_robot_pick_request()
    assert len(replies) == 1
    assert replies[-1] == "NONE\n"

    # Trigger store request when idle -> should reply FULL, not STORE <slot>
    await robot_mgr._handle_robot_store_request()
    assert len(replies) == 2
    assert replies[-1] == "FULL\n"


@pytest.mark.asyncio
async def test_staff_queue_signaling():
    """Verify that notify_robot_ready queues tokens and can be consumed reliably."""
    staff_operation_manager.active_type = "OUTBOUND"

    # Drain queue
    while not staff_operation_manager._robot_ready_queue.empty():
        staff_operation_manager._robot_ready_queue.get_nowait()

    # Send 2 notifications
    staff_operation_manager.notify_robot_ready()
    staff_operation_manager.notify_robot_ready()

    # Consume both tokens
    token1 = await asyncio.wait_for(staff_operation_manager._robot_ready_queue.get(), timeout=1.0)
    token2 = await asyncio.wait_for(staff_operation_manager._robot_ready_queue.get(), timeout=1.0)
    assert token1 is True
    assert token2 is True
    assert staff_operation_manager._robot_ready_queue.empty()

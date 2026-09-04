import asyncio
import pytest
from app.database.repository import async_session
from app.models.schemas import StorageSlotStatus
from app.services.inventory_manager import InventoryManager
from app.services.plc_manager import PLCManager
from app.services.robot_manager import RobotManager
from app.services.staff_operation_manager import staff_operation_manager


@pytest.mark.asyncio
async def test_staff_mutual_exclusive_operations():
    """Verify that starting Outbound cancels Inbound, and starting Inbound cancels Outbound."""
    plc_mgr = PLCManager.get_instance()
    robot_mgr = RobotManager.get_instance()
    plc_mgr.simulator_mode = True
    robot_mgr.simulator_mode = True

    # 1. Setup slot A1 as OCCUPIED so outbound has something to pick
    async with async_session() as session:
        inv_mgr = InventoryManager(session)
        await inv_mgr.init_default_slots()
        await inv_mgr.update_slot(
            slot_name="A1",
            status=StorageSlotStatus.OCCUPIED,
            product_id="TEST_PROD_MUTUAL_01",
            qr_code="TEST_PROD_MUTUAL_01",
            auto_broadcast=False,
        )

    # 2. Start Inbound
    await staff_operation_manager.start_inbound()
    assert staff_operation_manager.status == "RUNNING"
    assert staff_operation_manager.active_type == "INBOUND"

    # 3. Trigger Outbound while Inbound is RUNNING -> Should automatically shut down Inbound and start Outbound
    await staff_operation_manager.start_outbound(slots=["A1"])
    assert staff_operation_manager.status == "RUNNING"
    assert staff_operation_manager.active_type == "OUTBOUND"
    assert "A1" in staff_operation_manager.outbound_queue

    # 4. Trigger Inbound while Outbound is RUNNING -> Should automatically cancel Outbound and start Inbound
    await staff_operation_manager.start_inbound()
    assert staff_operation_manager.status == "RUNNING"
    assert staff_operation_manager.active_type == "INBOUND"

    # Cleanup
    await staff_operation_manager.stop_inbound()
    assert staff_operation_manager.status in ("COMPLETED", "IDLE")

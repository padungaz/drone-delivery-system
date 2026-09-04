import asyncio
import pytest
from datetime import datetime
from sqlalchemy import select
from app.database.repository import async_session
from app.models.database import StorageSlotRecord, ProductRecord
from app.models.schemas import StorageSlotStatus
from app.services.inventory_manager import InventoryManager
from app.services.plc_manager import PLCManager
from app.services.robot_manager import RobotManager
from app.services.staff_operation_manager import staff_operation_manager


@pytest.mark.asyncio
async def test_staff_outbound_frees_slot_to_empty():
    """Verify that picking an occupied slot during Staff Outbound immediately frees the slot to EMPTY
    and updates the associated ProductRecord to EXPORTED.
    """
    plc_mgr = PLCManager.get_instance()
    robot_mgr = RobotManager.get_instance()
    plc_mgr.simulator_mode = True
    robot_mgr.simulator_mode = True

    # 1. Setup slot A2 as OCCUPIED with a test product
    test_prod_id = "PROD_TEST_OUTBOUND_01"
    async with async_session() as session:
        inv_mgr = InventoryManager(session)
        await inv_mgr.init_default_slots()

        # Ensure product record exists
        stmt_p = select(ProductRecord).where(ProductRecord.product_id == test_prod_id)
        res_p = await session.execute(stmt_p)
        p = res_p.scalar_one_or_none()
        if not p:
            p = ProductRecord(
                product_id=test_prod_id,
                product_name="Sản phẩm kiểm thử xuất kho",
                qr_code=test_prod_id,
                status="IN_STOCK",
                created_at=datetime.utcnow(),
            )
            session.add(p)
        else:
            p.status = "IN_STOCK"
        await session.commit()

        # Update slot A2 to OCCUPIED
        await inv_mgr.update_slot(
            slot_name="A2",
            status=StorageSlotStatus.OCCUPIED,
            product_id=test_prod_id,
            qr_code=test_prod_id,
            auto_broadcast=False,
        )

    # 2. Start Outbound on slot A2
    await staff_operation_manager.start_outbound(slots=["A2"])
    assert staff_operation_manager.status == "RUNNING"
    assert "A2" in staff_operation_manager.outbound_queue

    # 3. Wait for background worker task to pick slot A2
    max_wait = 10
    start_time = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start_time < max_wait:
        await asyncio.sleep(0.5)
        if staff_operation_manager.status in ("COMPLETED", "IDLE"):
            break

    # Clean up task if running
    if staff_operation_manager.status == "RUNNING":
        await staff_operation_manager.cancel_outbound()

    # 4. Assert slot A2 is now EMPTY and ProductRecord is EXPORTED
    async with async_session() as session:
        stmt_slot = select(StorageSlotRecord).where(StorageSlotRecord.slot_name == "A2")
        res_slot = await session.execute(stmt_slot)
        slot_a2 = res_slot.scalar_one_or_none()
        assert slot_a2 is not None
        assert slot_a2.status == StorageSlotStatus.EMPTY.value
        assert slot_a2.product_id is None

        stmt_p = select(ProductRecord).where(ProductRecord.product_id == test_prod_id)
        res_p = await session.execute(stmt_p)
        prod = res_p.scalar_one_or_none()
        assert prod is not None
        assert prod.status == "EXPORTED"


@pytest.mark.asyncio
async def test_staff_inbound_occupies_slot_with_product():
    """Verify that storing an item during Staff Inbound updates the target empty slot to OCCUPIED
    and registers/updates the ProductRecord to IN_STOCK.
    """
    plc_mgr = PLCManager.get_instance()
    robot_mgr = RobotManager.get_instance()
    plc_mgr.simulator_mode = True
    robot_mgr.simulator_mode = True

    # 1. Ensure at least one slot (e.g. A1) is EMPTY
    async with async_session() as session:
        inv_mgr = InventoryManager(session)
        await inv_mgr.init_default_slots()
        await inv_mgr.clear_slot("A1")

    # 2. Start Inbound
    await staff_operation_manager.start_inbound()
    assert staff_operation_manager.status == "RUNNING"

    # 3. Wait for at least 1 item to be stored
    max_wait = 12
    start_time = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start_time < max_wait:
        await asyncio.sleep(0.5)
        if staff_operation_manager.inbound_current_count >= 1:
            break

    # Stop inbound
    await staff_operation_manager.stop_inbound()

    # 4. Verify that the slot that was used (e.g. A1) is now OCCUPIED with a product
    async with async_session() as session:
        stmt_slot = select(StorageSlotRecord).where(StorageSlotRecord.slot_name == "A1")
        res_slot = await session.execute(stmt_slot)
        slot_a1 = res_slot.scalar_one_or_none()
        assert slot_a1 is not None
        assert slot_a1.status == StorageSlotStatus.OCCUPIED.value
        assert slot_a1.product_id is not None

        # Verify ProductRecord exists and is IN_STOCK
        stmt_p = select(ProductRecord).where(ProductRecord.product_id == slot_a1.product_id)
        res_p = await session.execute(stmt_p)
        prod = res_p.scalar_one_or_none()
        assert prod is not None
        assert prod.status == "IN_STOCK"

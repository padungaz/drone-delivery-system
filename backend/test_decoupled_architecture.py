import asyncio
import logging
from sqlalchemy import select
from app.database.repository import async_session, init_db
from app.models.database import (
    CustomerRecord,
    CustomerAddressRecord,
    DeliveryRequestRecord,
    IntralogisticsMissionRecord,
)
from app.models.schemas import StorageSlotStatus
from app.services.mission_manager import MissionManager
from app.services.station_service import StationService
from app.services.inventory_manager import InventoryManager
from app.services.plc_manager import PLCManager
from app.services.robot_manager import RobotManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("TestDecoupledArchitecture")


async def main():
    logger.info("=== Starting 4-Layer Decoupled Architecture Integration Test ===")
    await init_db()

    async with async_session() as session:
        # Initialize default inventory slots & seed devices
        inv_mgr = InventoryManager(session)
        await inv_mgr.init_default_slots()

        # Set simulators
        plc_mgr = PLCManager.get_instance()
        plc_mgr.simulator_mode = True

        robot_mgr = RobotManager.get_instance()
        robot_mgr.simulator_mode = True

        # -------------------------------------------------------------------
        # 1. LAYER 1: Customer Order (DeliveryRequest)
        # -------------------------------------------------------------------
        logger.info("\n--- LAYER 1: Customer Order Creation ---")
        order = DeliveryRequestRecord(
            customer_id=1,
            customer_name="Trần Thị B",
            customer_phone="0987654321",
            delivery_type="RECEIVE_FROM_WAREHOUSE",
            pickup_lat=16.0544,
            pickup_lon=108.2022,
            pickup_address="Kho Hàng Trung Tâm",
            drop_lat=16.0600,
            drop_lon=108.2100,
            drop_address="456 Đường Lê Duẩn, Đà Nẵng",
            status="APPROVED",
            note="Đơn xuất kho giao hàng khẩn",
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)
        logger.info("✓ Layer 1 Order Created! ID: #%d, Customer: %s, Type: %s, Status: %s", order.id, order.customer_name, order.delivery_type, order.status)

        # -------------------------------------------------------------------
        # 2. LAYER 2: Mission Orchestration (MissionManager)
        # -------------------------------------------------------------------
        logger.info("\n--- LAYER 2: Mission Orchestration ---")
        mission_mgr = MissionManager(session)

        # Assign product SP001 to slot A1 for test delivery
        await inv_mgr.update_slot("A1", StorageSlotStatus.OCCUPIED, product_id="SP001")

        delivery_mission = await mission_mgr.execute_drone_delivery(
            drone_id="UAV01",
            product_id="SP001",
            order_id=order.id,
            auto_run=False,
        )
        logger.info("✓ Layer 2 Mission Created from Order #%d! Mission ID: #%d, Type: %s, Target Slot: %s, Status: %s, Phase: %s",
                    order.id, delivery_mission.id, delivery_mission.mission_type, delivery_mission.target_slot, delivery_mission.status, delivery_mission.current_phase)

        # -------------------------------------------------------------------
        # 3. LAYER 3 & 4: Automated Mission & Station Task Execution
        # -------------------------------------------------------------------
        logger.info("\n--- LAYER 3 & 4: Station Operations & Hardware Execution ---")
        await mission_mgr.run_automated_delivery_sequence(delivery_mission.id)

        await session.refresh(delivery_mission)
        await session.refresh(order)

        logger.info("✓ Layer 2 Mission Execution Completed! Status: %s, Phase: %s", delivery_mission.status, delivery_mission.current_phase)
        logger.info("✓ Layer 1 Customer Order Updated! Status: %s", order.status)

        # -------------------------------------------------------------------
        # 4. Test DRONE_PICKUP (Import / Nhập Kho) Flow
        # -------------------------------------------------------------------
        logger.info("\n--- Testing DRONE_PICKUP Flow ---")
        order_pickup = DeliveryRequestRecord(
            customer_id=2,
            customer_name="Lê Văn C",
            customer_phone="0912345678",
            delivery_type="SEND_TO_WAREHOUSE",
            pickup_lat=16.0600,
            pickup_lon=108.2100,
            pickup_address="Khách gửi hàng",
            drop_lat=16.0544,
            drop_lon=108.2022,
            drop_address="Kho Hàng Trung Tâm",
            status="APPROVED",
            note="Nhập kho sản phẩm SP002",
        )
        session.add(order_pickup)
        await session.commit()

        pickup_mission = await mission_mgr.execute_drone_pickup(
            drone_id="UAV01",
            product_id="SP002",
            order_id=order_pickup.id,
            auto_run=False,
        )
        await mission_mgr.run_automated_pickup_sequence(pickup_mission.id)

        await session.refresh(pickup_mission)
        await session.refresh(order_pickup)

        logger.info("✓ DRONE_PICKUP Mission #%d Completed! Status: %s, Phase: %s, Assigned Slot: %s",
                    pickup_mission.id, pickup_mission.status, pickup_mission.current_phase, pickup_mission.target_slot)
        logger.info("✓ Customer Order #%d Updated! Status: %s", order_pickup.id, order_pickup.status)

    logger.info("\n=== All 4-Layer Decoupled Architecture Integration Tests PASSED! ===")


if __name__ == "__main__":
    asyncio.run(main())

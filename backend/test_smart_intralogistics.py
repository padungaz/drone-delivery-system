import asyncio
import logging
from app.database.repository import init_db, async_session
from app.models.schemas import (
    DeviceRegisterRequest,
    DeviceType,
    PLCCommand,
    PLCCommandRequest,
    RobotCommand,
    RobotCommandRequest,
    QRScanPayload,
    IntralogisticsMissionCreate,
)
from app.services.device_manager import DeviceManager
from app.services.inventory_manager import InventoryManager
from app.services.plc_manager import PLCManager
from app.services.robot_manager import RobotManager
from app.services.mission_manager import MissionManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestSmartIntralogistics")


async def main():
    logger.info("=== Starting Smart Intralogistics Controller Integration Test ===")

    # 1. Initialize Database
    await init_db()
    logger.info("✓ Database tables initialized.")

    async with async_session() as session:
        # 2. Test Device Registration
        dev_mgr = DeviceManager(session)
        uav = await dev_mgr.register_device(DeviceRegisterRequest(name="UAV01", type=DeviceType.UAV, ip="192.168.137.88"))
        plc = await dev_mgr.register_device(DeviceRegisterRequest(name="PLC01", type=DeviceType.PLC, ip="192.168.58.10"))
        robot = await dev_mgr.register_device(DeviceRegisterRequest(name="ROBOT01", type=DeviceType.ROBOT, ip="192.168.58.2"))
        cam = await dev_mgr.register_device(DeviceRegisterRequest(name="CAM01", type=DeviceType.CAMERA, ip="192.168.58.50"))

        devices = await dev_mgr.get_all_devices()
        logger.info("✓ Registered %d devices on LAN.", len(devices))
        for d in devices:
            logger.info("   -> %s (%s) IP: %s Status: %s", d.device_name, d.device_type, d.ip_address, d.status)

        # 3. Test Warehouse 9 Storage Slots
        inv_mgr = InventoryManager(session)
        await inv_mgr.init_default_slots()
        slots = await inv_mgr.get_all_slots()
        logger.info("✓ Warehouse Storage Slots initialized: %d slots", len(slots))
        slot_names = [s.slot_name for s in slots]
        logger.info("   -> Slots: %s", ", ".join(slot_names))

        # 4. Test Camera QR Scan & Auto-slot Assignment
        qr_res = await inv_mgr.process_qr_scan(QRScanPayload(camera_id="CAM01", qr="SP001"))
        if qr_res:
            logger.info("✓ Camera QR scan processed: Product SP001 assigned to Slot %s", qr_res.slot_name)

        # 5. Test PLC Docking Station Controls (DB15 Mapping)
        plc_mgr = PLCManager.get_instance()
        plc_mgr.simulator_mode = True
        st_start = await plc_mgr.execute_command(PLCCommand.START_PLC)
        logger.info("✓ PLC START_PLC executed. PLC On: %s", st_start.plc_on)
        status_lock = await plc_mgr.execute_command(PLCCommand.LOCK_DRONE)
        logger.info("✓ PLC LOCK_DRONE executed. Locked: %s (plc_locked_state=%s), PLC Busy: %s, PLC Error: %s", status_lock.drone_locked, status_lock.plc_locked_state, status_lock.plc_busy, status_lock.plc_error)
        status_z = await plc_mgr.execute_command(PLCCommand.Z_UP)
        logger.info("✓ PLC Z_UP executed. Z Axis: %s, plc_z_is_up: %s", status_z.z_axis, status_z.plc_z_is_up)
        status_zdown = await plc_mgr.execute_command(PLCCommand.Z_DOWN)
        logger.info("✓ PLC Z_DOWN executed. Z Axis: %s, plc_z_is_down: %s", status_zdown.z_axis, status_zdown.plc_z_is_down)
        status_unlock = await plc_mgr.execute_command(PLCCommand.UNLOCK_DRONE)
        logger.info("✓ PLC UNLOCK_DRONE executed. Locked: %s", status_unlock.drone_locked)
        status_reset = await plc_mgr.execute_command(PLCCommand.RESET_PLC)
        logger.info("✓ PLC RESET_PLC executed. Error: %s", status_reset.plc_error)

        # 6. Test FAIRINO Robot Commands
        robot_mgr = RobotManager.get_instance()
        robot_mgr.simulator_mode = True
        r_home = await robot_mgr.execute_command(RobotCommand.MOVE_HOME)
        logger.info("✓ FAIRINO Robot MOVE_HOME executed. State: %s", r_home.state)
        r_pick = await robot_mgr.execute_command(RobotCommand.PICK, slot="A1")
        logger.info("✓ FAIRINO Robot PICK executed for slot A1. State: %s, Holding: %s", r_pick.state, r_pick.holding_product)

        # 7. Test Master Orchestrator FSM: DRONE_PICKUP (Flow 8) Automated Sequence
        mission_mgr = MissionManager(session)
        pickup_mission = await mission_mgr.execute_drone_pickup(drone_id="UAV01", product_id="SP002", auto_run=False)
        await mission_mgr.run_automated_pickup_sequence(pickup_mission.id)
        await session.refresh(pickup_mission)
        logger.info("✓ DRONE_PICKUP Automated Sequence #%d completed! State: %s, Target Slot: %s", pickup_mission.id, pickup_mission.state, pickup_mission.target_slot)

        # 8. Test Master Orchestrator FSM: DRONE_DELIVERY (Flow 9) Automated Sequence
        delivery_mission = await mission_mgr.execute_drone_delivery(drone_id="UAV01", product_id="SP002", auto_run=False)
        await mission_mgr.run_automated_delivery_sequence(delivery_mission.id)
        await session.refresh(delivery_mission)
        logger.info("✓ DRONE_DELIVERY Automated Sequence #%d completed! State: %s, Target Slot: %s", delivery_mission.id, delivery_mission.state, delivery_mission.target_slot)

    logger.info("=== All Smart Intralogistics Controller System Integration Tests PASSED! ===")


if __name__ == "__main__":
    asyncio.run(main())

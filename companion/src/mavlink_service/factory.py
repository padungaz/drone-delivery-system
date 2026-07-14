"""Factory — chọn MAVLink backend theo config."""

import logging

import config

logger = logging.getLogger(__name__)


def create_mavlink_controller():
    """
    Trả về controller phù hợp:
      sim + mock  → MavlinkSimulator (không cần PX4)
      sim + sitl  → MavlinkController qua UDP (PX4 SITL)
      pi          → MavlinkController qua UART
    """
    if config.IS_SIM and config.MAVLINK_BACKEND == "mock":
        from src.mavlink_service.simulator import MavlinkSimulator
        logger.info("Using MAVLink MOCK (PC simulation)")
        return MavlinkSimulator()

    from src.mavlink_service.controller import MavlinkController
    ctrl = MavlinkController()

    if config.IS_SIM and config.MAVLINK_BACKEND == "sitl":
        ctrl.connection_uri = config.MAVLINK_SITL_URI
        ctrl.use_baud = False
        logger.info("Using MAVLink SITL: %s", config.MAVLINK_SITL_URI)
    else:
        ctrl.connection_uri = config.MAVLINK_DEVICE
        ctrl.use_baud = True
        logger.info("Using MAVLink serial: %s", config.MAVLINK_DEVICE)

    return ctrl

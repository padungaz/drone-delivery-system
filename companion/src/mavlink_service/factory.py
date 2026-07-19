"""
MAVLink factory — trả về MavlinkController kết nối UART tới Pixhawk 6C.

Raspberry Pi 5 production deployment:
  MAVLINK_DEVICE = /dev/ttyAMA0  (GPIO UART — Pixhawk TELEM1)
               hoặc /dev/ttyUSB0  (USB-Serial adapter)
  MAVLINK_BAUD   = 57600 | 921600
"""

import logging

import config
from src.mavlink_service.controller import MavlinkController

logger = logging.getLogger(__name__)


def create_mavlink_controller() -> MavlinkController:
    """
    Tạo và cấu hình MavlinkController cho Raspberry Pi 5.

    Device và baudrate được đọc từ environment variables:
      MAVLINK_DEVICE (default: /dev/ttyAMA0)
      MAVLINK_BAUD   (default: 921600)
    """
    ctrl = MavlinkController()
    ctrl.connection_uri = config.MAVLINK_DEVICE
    ctrl.use_baud = True

    logger.info(
        "MAVLink controller: serial %s @ %d baud",
        config.MAVLINK_DEVICE,
        config.MAVLINK_BAUD,
    )
    return ctrl

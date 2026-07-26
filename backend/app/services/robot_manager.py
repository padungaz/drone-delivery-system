import asyncio
import logging
from typing import Optional

from app.models.schemas import RobotCommand, RobotStatusResponse

logger = logging.getLogger(__name__)


class RobotManager:
    """Manager for FAIRINO Robot Arm (Cobot).
    Controls:
      - Motion states (IDLE, READY, MOVING, PICKING, PLACING, ERROR)
      - Picking & placing items from UAV or Storage Slots (A1..C3)
      - Sending Z-axis height requests to PLC
    """

    _instance: Optional["RobotManager"] = None

    def __init__(self, simulator_mode: bool = True):
        self.simulator_mode = simulator_mode
        self.state: str = "IDLE"
        self.current_slot: Optional[str] = None
        self.holding_product: Optional[str] = None

    @classmethod
    def get_instance(cls) -> "RobotManager":
        if cls._instance is None:
            cls._instance = RobotManager(simulator_mode=True)
        return cls._instance

    def get_status(self) -> RobotStatusResponse:
        return RobotStatusResponse(
            state=self.state,
            current_slot=self.current_slot,
            holding_product=self.holding_product,
        )

    async def execute_command(self, cmd: RobotCommand, slot: Optional[str] = None) -> RobotStatusResponse:
        logger.info("Executing FAIRINO Robot command: %s (slot: %s, simulator: %s)", cmd.value, slot, self.simulator_mode)

        if cmd in (RobotCommand.MOVE_HOME, RobotCommand.REQUEST_Z_DOWN):
            self.state = "MOVING"
            if self.simulator_mode:
                await asyncio.sleep(0.4)
            self.state = "READY"
            self.current_slot = None
            logger.info("FAIRINO Robot: Returned to HOME position")

        elif cmd == RobotCommand.REQUEST_Z_UP:
            self.state = "READY"
            logger.info("FAIRINO Robot: Ready for Z_UP operation")

        elif cmd in (RobotCommand.PICK_PRODUCT, RobotCommand.PICK):
            self.state = "PICKING"
            self.current_slot = slot
            if self.simulator_mode:
                await asyncio.sleep(0.6)
            self.holding_product = f"PROD_{slot}" if slot else "SP001"
            self.state = "READY"
            logger.info("FAIRINO Robot: Successfully picked product from slot %s", slot)

        elif cmd in (RobotCommand.PLACE_PRODUCT, RobotCommand.STORE):
            self.state = "PLACING"
            self.current_slot = slot
            if self.simulator_mode:
                await asyncio.sleep(0.6)
            self.holding_product = None
            self.state = "READY"
            logger.info("FAIRINO Robot: Successfully placed product into slot %s", slot)

        return self.get_status()

import asyncio
import logging
from typing import Dict, Any, Optional

from app.models.schemas import PLCCommand, PLCStatusResponse

logger = logging.getLogger(__name__)


class PLCManager:
    """Manager for PLC S7-1200 Docking Station.
    Controls:
      - Sensor detect drone on landing pad
      - Clamp X & Clamp Y mechanical lock
      - Lift Z axis for Robot Arm
    """

    _instance: Optional["PLCManager"] = None

    def __init__(self, simulator_mode: bool = True):
        self.simulator_mode = simulator_mode
        self.drone_detected: bool = False
        self.clamp_x: str = "OPEN"      # "OPEN", "LOCKING", "DONE"
        self.clamp_y: str = "OPEN"      # "OPEN", "LOCKING", "DONE"
        self.drone_locked: bool = False
        self.z_axis: str = "HOME"       # "HOME", "UP", "DOWN"

    @classmethod
    def get_instance(cls) -> "PLCManager":
        if cls._instance is None:
            cls._instance = PLCManager(simulator_mode=True)
        return cls._instance

    def get_status(self) -> PLCStatusResponse:
        return PLCStatusResponse(
            drone_detected=self.drone_detected,
            clamp_x=self.clamp_x,
            clamp_y=self.clamp_y,
            drone_locked=self.drone_locked,
            z_axis=self.z_axis,
        )

    async def execute_command(self, cmd: PLCCommand) -> PLCStatusResponse:
        logger.info("Executing PLC command: %s (Simulator Mode: %s)", cmd.value, self.simulator_mode)

        if cmd == PLCCommand.LOCK_DRONE:
            self.clamp_x = "LOCKING"
            self.clamp_y = "LOCKING"
            if self.simulator_mode:
                await asyncio.sleep(0.5)  # Simulate mechanical clamp movement
            self.clamp_x = "DONE"
            self.clamp_y = "DONE"
            self.drone_locked = True
            logger.info("PLC: Drone locked successfully by Clamps X & Y")

        elif cmd == PLCCommand.UNLOCK_DRONE:
            self.clamp_x = "OPEN"
            self.clamp_y = "OPEN"
            self.drone_locked = False
            self.drone_detected = False
            logger.info("PLC: Drone unlocked and clamps released")

        elif cmd == PLCCommand.Z_UP:
            if self.simulator_mode:
                await asyncio.sleep(0.3)
            self.z_axis = "UP"
            logger.info("PLC: Lift Z-axis moved to UP position")

        elif cmd == PLCCommand.Z_DOWN:
            if self.simulator_mode:
                await asyncio.sleep(0.3)
            self.z_axis = "DOWN"
            logger.info("PLC: Lift Z-axis moved to DOWN position")

        return self.get_status()

    def set_drone_detected(self, detected: bool) -> None:
        self.drone_detected = detected
        logger.info("PLC Sensor: Drone detection set to %s", detected)

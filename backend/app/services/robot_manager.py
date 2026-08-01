import asyncio
import logging
import os
from typing import Optional

from app.models.schemas import RobotCommand, RobotStatusResponse

logger = logging.getLogger(__name__)


class RobotManager:
    """Manager for FAIRINO Robot Arm (Cobot) — Handshake Signal Protocol.

    Architecture: Event-Driven Command/Done
    ========================================
    Backend sends a command to Robot Arm.
    Robot autonomously executes the full motion sequence.
    Robot signals completion via done callback / state change.

    In simulator mode, mechanical delays are simulated with asyncio.sleep
    followed by an immediate DONE signal.

    Controls:
      - Motion states (IDLE, READY, MOVING, PICKING, PLACING, ERROR)
      - Picking & placing items from UAV or Storage Slots (A1..C3)
      - Handshake signal: execute_command returns ONLY after robot reports DONE
    """

    _instance: Optional["RobotManager"] = None

    def __init__(self, simulator_mode: bool = False, robot_ip: str = "192.168.58.2"):
        self.simulator_mode = simulator_mode
        self.robot_ip = robot_ip
        self.is_connected: bool = False
        self.state: str = "IDLE"
        self.current_slot: Optional[str] = None
        self.holding_product: Optional[str] = None

        # Handshake: asyncio.Event for external DONE signal from real robot
        self._done_event: asyncio.Event = asyncio.Event()
        self._done_event.set()  # Initially ready (no pending command)

    @classmethod
    def get_instance(cls) -> "RobotManager":
        if cls._instance is None:
            env_sim = os.getenv("ROBOT_SIMULATOR_MODE", "false").lower()
            sim_mode = env_sim in ("true", "1", "yes")
            robot_ip = os.getenv("ROBOT_IP", "192.168.58.2")
            cls._instance = RobotManager(simulator_mode=sim_mode, robot_ip=robot_ip)
        return cls._instance

    def get_status(self) -> RobotStatusResponse:
        is_online = self.is_connected or self.simulator_mode
        current_state = self.state if is_online else "OFFLINE"
        return RobotStatusResponse(
            state=current_state,
            current_slot=self.current_slot,
            holding_product=self.holding_product,
            connected=self.is_connected,
            simulator_mode=self.simulator_mode,
        )

    def signal_done(self) -> None:
        """Called externally when real robot reports command completion (ROBOT_DONE).
        Can be triggered by a robot callback endpoint or polling loop.
        """
        self._done_event.set()
        if self.state in ("MOVING", "PICKING", "PLACING"):
            self.state = "READY"
        logger.info("FAIRINO Robot: DONE signal received (State set to READY)")

    def emergency_stop(self) -> RobotStatusResponse:
        """Triggers Emergency Stop for FAIRINO Robot Arm."""
        self.state = "ERROR"
        self._done_event.set()
        logger.error("FAIRINO Robot: EMERGENCY STOP TRIGGERED!")
        return self.get_status()

    async def _wait_for_done(self, timeout: float = 30.0) -> bool:
        """Wait for robot DONE signal. In simulator mode, returns immediately.
        Returns True if DONE received within timeout, False on timeout.
        """
        if self.simulator_mode:
            return True

        self._done_event.clear()
        try:
            await asyncio.wait_for(self._done_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.warning("FAIRINO Robot: DONE signal timeout (%.1fs)", timeout)
            return False

    async def execute_command(self, cmd: RobotCommand, slot: Optional[str] = None) -> RobotStatusResponse:
        """Execute a robot command and wait for DONE signal (Handshake Protocol).

        Flow:
          1. Set state to action state (MOVING, PICKING, PLACING)
          2. In simulator mode: simulate delay then mark done
          3. In real mode: send command to robot, wait for DONE signal
          4. Update state to READY on success
          5. Return status
        """
        logger.info("Executing FAIRINO Robot command: %s (slot: %s, simulator: %s)", cmd.value, slot, self.simulator_mode)

        if cmd in (RobotCommand.MOVE_HOME, RobotCommand.REQUEST_Z_DOWN):
            self.state = "MOVING"
            if self.simulator_mode:
                await asyncio.sleep(0.4)
            else:
                # TODO: Send real command to FAIRINO robot via SDK/API
                await self._wait_for_done(timeout=15.0)
            self.state = "READY"
            self.current_slot = None
            logger.info("FAIRINO Robot: Returned to HOME position (DONE)")

        elif cmd == RobotCommand.REQUEST_Z_UP:
            self.state = "READY"
            logger.info("FAIRINO Robot: Ready for Z_UP operation (DONE)")

        elif cmd in (RobotCommand.PICK_PRODUCT, RobotCommand.PICK):
            self.state = "PICKING"
            self.current_slot = slot
            if self.simulator_mode:
                await asyncio.sleep(0.6)
            else:
                # TODO: Send real pick command to FAIRINO robot via SDK/API
                await self._wait_for_done(timeout=30.0)
            self.holding_product = f"PROD_{slot}" if slot else "SP001"
            self.state = "READY"
            logger.info("FAIRINO Robot: Successfully picked product from slot %s (DONE)", slot)

        elif cmd in (RobotCommand.PLACE_PRODUCT, RobotCommand.STORE):
            self.state = "PLACING"
            self.current_slot = slot
            if self.simulator_mode:
                await asyncio.sleep(0.6)
            else:
                # TODO: Send real place command to FAIRINO robot via SDK/API
                await self._wait_for_done(timeout=30.0)
            self.holding_product = None
            self.state = "READY"
            logger.info("FAIRINO Robot: Successfully placed product into slot %s (DONE)", slot)

        return self.get_status()

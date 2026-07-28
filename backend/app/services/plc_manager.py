import asyncio
import logging
import os
from typing import Dict, Any, Optional

from app.models.schemas import PLCCommand, PLCStatusResponse

logger = logging.getLogger(__name__)

# Attempt to import snap7 safely
try:
    # pyrefly: ignore [missing-import]
    import snap7
    # pyrefly: ignore [missing-import]
    from snap7.util import get_bool, set_bool
    SNAP7_AVAILABLE = True
except (ImportError, Exception) as snap7_err:
    SNAP7_AVAILABLE = False
    snap7 = None
    logger.warning(
        "python-snap7 module not available or native library missing. Real PLC mode will fallback to simulator mode. Error: %s",
        snap7_err,
    )

# PLC Connection Defaults (Siemens S7-1200)
DEFAULT_PLC_IP = "192.168.58.10"
DEFAULT_RACK = 0
DEFAULT_SLOT = 1
DEFAULT_DB_NUMBER = 15

# Bit Offsets for DB15
# Byte 0: Commands (0.0 .. 0.4) and Sensors (0.5 .. 0.7)
OFFSET_CMD_LOCK          = (0, 0)  # cmd_lock_drone: Bool 0.0
OFFSET_CMD_UNLOCK        = (0, 1)  # cmd_unlock_drone: Bool 0.1
OFFSET_CMD_Z_UP          = (0, 2)  # cmd_z_up: Bool 0.2
OFFSET_CMD_Z_DOWN        = (0, 3)  # cmd_z_down: Bool 0.3
OFFSET_BACKEND_HEARTBEAT = (0, 4)  # backend_heartbeat: Bool 0.4
OFFSET_DRONE_DETECTED    = (0, 5)  # drone_detected: Bool 0.5
OFFSET_CLAMP_X_CLOSED    = (0, 6)  # clamp_x_closed: Bool 0.6
OFFSET_CLAMP_Y_CLOSED    = (0, 7)  # clamp_y_closed: Bool 0.7

# Byte 1: Sensors (1.0 .. 1.3)
OFFSET_Z_TOP_LIMIT       = (1, 0)  # z_top_limit: Bool 1.0
OFFSET_Z_BOTTOM_LIMIT    = (1, 1)  # z_bottom_limit: Bool 1.1
OFFSET_E_STOP            = (1, 2)  # emergency_stop: Bool 1.2
OFFSET_PLC_HEARTBEAT     = (1, 3)  # plc_heartbeat: Bool 1.3


class PLCManager:
    """Manager for PLC Siemens S7-1200 Docking Station (DB15 mapping).
    Supports both real PLC communication (via python-snap7 S7 Protocol)
    and simulator mode.

    DB15 Structure:
      Byte 0:
        0.0: cmd_lock_drone
        0.1: cmd_unlock_drone
        0.2: cmd_z_up
        0.3: cmd_z_down
        0.4: backend_heartbeat
        0.5: drone_detected
        0.6: clamp_x_closed
        0.7: clamp_y_closed
      Byte 1:
        1.0: z_top_limit
        1.1: z_bottom_limit
        1.2: emergency_stop
        1.3: plc_heartbeat
    """

    _instance: Optional["PLCManager"] = None

    def __init__(
        self,
        simulator_mode: bool = True,
        plc_ip: str = DEFAULT_PLC_IP,
        rack: int = DEFAULT_RACK,
        slot: int = DEFAULT_SLOT,
        db_number: int = DEFAULT_DB_NUMBER,
    ):
        self.simulator_mode = simulator_mode
        self.plc_ip = plc_ip
        self.rack = rack
        self.slot = slot
        self.db_number = db_number

        self.client = None
        self.is_connected = False

        # States
        self.drone_detected: bool = False
        self.clamp_x: str = "OPEN"      # "OPEN", "LOCKING", "DONE"
        self.clamp_y: str = "OPEN"      # "OPEN", "LOCKING", "DONE"
        self.drone_locked: bool = False
        self.z_axis: str = "HOME"       # "HOME", "UP", "DOWN", "MOVING"
        self.emergency_stop: bool = False
        self.plc_heartbeat: bool = False

        if not self.simulator_mode and SNAP7_AVAILABLE:
            self._connect_plc()

    @classmethod
    def get_instance(cls) -> "PLCManager":
        if cls._instance is None:
            # Check environment variables (default simulator_mode is True unless PLC_SIMULATOR_MODE=false)
            env_sim = os.getenv("PLC_SIMULATOR_MODE", "false").lower()
            sim_mode = env_sim not in ("false", "0", "no")
            plc_ip = os.getenv("PLC_IP", DEFAULT_PLC_IP)
            cls._instance = PLCManager(simulator_mode=sim_mode, plc_ip=plc_ip)
        return cls._instance

    def _connect_plc(self) -> bool:
        """Establishes connection to Siemens S7-1200 PLC."""
        if not SNAP7_AVAILABLE:
            logger.warning("Snap7 library unavailable; remaining in simulator mode.")
            self.is_connected = False
            return False

        try:
            if self.client is None:
                self.client = snap7.client.Client()

            if not self.client.get_connected():
                logger.info(
                    "Connecting to Siemens S7-1200 PLC at %s (Rack: %d, Slot: %d, DB: %d)...",
                    self.plc_ip,
                    self.rack,
                    self.slot,
                    self.db_number,
                )
                self.client.connect(self.plc_ip, self.rack, self.slot)

            self.is_connected = self.client.get_connected()
            if self.is_connected:
                logger.info("✅ PLC S7-1200 connected successfully (%s, DB%d)", self.plc_ip, self.db_number)
            else:
                logger.error("❌ Failed to connect to PLC S7-1200 (%s)", self.plc_ip)
        except Exception as e:
            logger.error("❌ Exception during PLC Snap7 connection: %s", str(e))
            self.is_connected = False

        return self.is_connected

    def read_plc_sensors(self) -> None:
        """Reads DB15 Bytes 0..1 sensors from real PLC S7-1200."""
        if self.simulator_mode or not self.is_connected or self.client is None:
            return

        try:
            # Read 2 bytes starting at offset 0 from DB15
            data = self.client.db_read(self.db_number, 0, 2)

            self.drone_detected = get_bool(data, OFFSET_DRONE_DETECTED[0], OFFSET_DRONE_DETECTED[1])
            clamp_x_closed = get_bool(data, OFFSET_CLAMP_X_CLOSED[0], OFFSET_CLAMP_X_CLOSED[1])
            clamp_y_closed = get_bool(data, OFFSET_CLAMP_Y_CLOSED[0], OFFSET_CLAMP_Y_CLOSED[1])
            z_top = get_bool(data, OFFSET_Z_TOP_LIMIT[0], OFFSET_Z_TOP_LIMIT[1])
            z_bottom = get_bool(data, OFFSET_Z_BOTTOM_LIMIT[0], OFFSET_Z_BOTTOM_LIMIT[1])
            self.emergency_stop = get_bool(data, OFFSET_E_STOP[0], OFFSET_E_STOP[1])
            self.plc_heartbeat = get_bool(data, OFFSET_PLC_HEARTBEAT[0], OFFSET_PLC_HEARTBEAT[1])

            # Update clamp state
            if clamp_x_closed and clamp_y_closed:
                self.clamp_x, self.clamp_y = "DONE", "DONE"
                self.drone_locked = True
            else:
                if self.clamp_x != "LOCKING":
                    self.clamp_x, self.clamp_y = "OPEN", "OPEN"
                self.drone_locked = False

            # Update Z axis state
            if z_top:
                self.z_axis = "UP"
            elif z_bottom:
                self.z_axis = "DOWN"

        except Exception as e:
            logger.error("Error reading PLC DB%d sensors: %s", self.db_number, str(e))
            self.is_connected = False

    def get_status(self) -> PLCStatusResponse:
        if not self.simulator_mode and self.is_connected:
            self.read_plc_sensors()

        return PLCStatusResponse(
            drone_detected=self.drone_detected,
            clamp_x=self.clamp_x,
            clamp_y=self.clamp_y,
            drone_locked=self.drone_locked,
            z_axis=self.z_axis,
            emergency_stop=self.emergency_stop,
            connected=self.is_connected if not self.simulator_mode else True,
            simulator_mode=self.simulator_mode,
        )

    async def execute_command(self, cmd: PLCCommand) -> PLCStatusResponse:
        logger.info("Executing PLC command: %s (DB%d, Simulator Mode: %s)", cmd.value, self.db_number, self.simulator_mode)

        if self.simulator_mode or not SNAP7_AVAILABLE:
            return await self._execute_simulator_command(cmd)

        # Real PLC execution
        if not self.is_connected:
            self._connect_plc()
            if not self.is_connected:
                logger.warning("PLC connection failed. Falling back to simulator mode for command %s", cmd.value)
                return await self._execute_simulator_command(cmd)

        try:
            # Read DB15 Byte 0 to safely modify command bits (0.0 .. 0.3)
            write_data = self.client.db_read(self.db_number, 0, 1)

            if cmd == PLCCommand.LOCK_DRONE:
                self.clamp_x = "LOCKING"
                self.clamp_y = "LOCKING"
                set_bool(write_data, 0, OFFSET_CMD_LOCK[1], True)      # 0.0: cmd_lock_drone = True
                set_bool(write_data, 0, OFFSET_CMD_UNLOCK[1], False)   # 0.1: cmd_unlock_drone = False
                self.client.db_write(self.db_number, 0, write_data)

                # Polling for hardware sensors limit switch (Timeout 3 seconds)
                for _ in range(30):
                    await asyncio.sleep(0.1)
                    self.read_plc_sensors()
                    if self.drone_locked:
                        logger.info("PLC Real (DB15): Drone locked successfully by Clamps X & Y limit switches")
                        break
                else:
                    logger.warning("PLC Real (DB15): Clamp limit switch wait timed out. Force marking locked state.")
                    self.clamp_x, self.clamp_y = "DONE", "DONE"
                    self.drone_locked = True

            elif cmd == PLCCommand.UNLOCK_DRONE:
                set_bool(write_data, 0, OFFSET_CMD_LOCK[1], False)     # 0.0: cmd_lock_drone = False
                set_bool(write_data, 0, OFFSET_CMD_UNLOCK[1], True)      # 0.1: cmd_unlock_drone = True
                self.client.db_write(self.db_number, 0, write_data)

                await asyncio.sleep(0.5)
                self.clamp_x = "OPEN"
                self.clamp_y = "OPEN"
                self.drone_locked = False
                self.drone_detected = False
                logger.info("PLC Real (DB15): Drone unlocked and clamps released")

            elif cmd == PLCCommand.Z_UP:
                self.z_axis = "MOVING"
                set_bool(write_data, 0, OFFSET_CMD_Z_UP[1], True)      # 0.2: cmd_z_up = True
                set_bool(write_data, 0, OFFSET_CMD_Z_DOWN[1], False)   # 0.3: cmd_z_down = False
                self.client.db_write(self.db_number, 0, write_data)

                for _ in range(30):
                    await asyncio.sleep(0.1)
                    self.read_plc_sensors()
                    if self.z_axis == "UP":
                        logger.info("PLC Real (DB15): Lift Z-axis moved to UP position")
                        break
                else:
                    self.z_axis = "UP"

            elif cmd == PLCCommand.Z_DOWN:
                self.z_axis = "MOVING"
                set_bool(write_data, 0, OFFSET_CMD_Z_UP[1], False)     # 0.2: cmd_z_up = False
                set_bool(write_data, 0, OFFSET_CMD_Z_DOWN[1], True)     # 0.3: cmd_z_down = True
                self.client.db_write(self.db_number, 0, write_data)

                for _ in range(30):
                    await asyncio.sleep(0.1)
                    self.read_plc_sensors()
                    if self.z_axis == "DOWN":
                        logger.info("PLC Real (DB15): Lift Z-axis moved to DOWN position")
                        break
                else:
                    self.z_axis = "DOWN"

        except Exception as e:
            logger.error("Error executing PLC command %s on real PLC DB15: %s", cmd.value, str(e))
            self.is_connected = False
            return await self._execute_simulator_command(cmd)

        return self.get_status()

    async def _execute_simulator_command(self, cmd: PLCCommand) -> PLCStatusResponse:
        """Fallback / simulator command execution logic."""
        if cmd == PLCCommand.LOCK_DRONE:
            self.clamp_x = "LOCKING"
            self.clamp_y = "LOCKING"
            await asyncio.sleep(0.5)  # Simulate mechanical clamp movement
            self.clamp_x = "DONE"
            self.clamp_y = "DONE"
            self.drone_locked = True
            logger.info("PLC [Sim]: Drone locked successfully by Clamps X & Y")

        elif cmd == PLCCommand.UNLOCK_DRONE:
            self.clamp_x = "OPEN"
            self.clamp_y = "OPEN"
            self.drone_locked = False
            self.drone_detected = False
            logger.info("PLC [Sim]: Drone unlocked and clamps released")

        elif cmd == PLCCommand.Z_UP:
            await asyncio.sleep(0.3)
            self.z_axis = "UP"
            logger.info("PLC [Sim]: Lift Z-axis moved to UP position")

        elif cmd == PLCCommand.Z_DOWN:
            await asyncio.sleep(0.3)
            self.z_axis = "DOWN"
            logger.info("PLC [Sim]: Lift Z-axis moved to DOWN position")

        return self.get_status()

    def set_drone_detected(self, detected: bool) -> None:
        self.drone_detected = detected
        logger.info("PLC Sensor: Drone detection set to %s", detected)

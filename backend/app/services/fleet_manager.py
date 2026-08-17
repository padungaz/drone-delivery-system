import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.services.plc_manager import PLCManager
from app.websocket.manager import system_ws_manager

logger = logging.getLogger(__name__)


class FleetUavState(str, Enum):
    READY = "READY"                              # Ở vị trí chờ/Home, sẵn sàng nhận nhiệm vụ
    FLYING_TO_WAREHOUSE = "FLYING_TO_WAREHOUSE"  # Đang bay về trạm lấy/giao hàng
    LANDED = "LANDED"                            # Đã hạ cánh tại Bãi đáp Trạm Docking N1
    LOADING = "LOADING"                          # Trạm kho đang thực thi nạp/dỡ hàng
    READY_TO_DEPART_HOME = "READY_TO_DEPART_HOME"         # Trạm đã dỡ xong, sẵn sàng cất cánh về Home
    READY_TO_DEPART_DELIVERY = "READY_TO_DEPART_DELIVERY" # Trạm đã nạp xong, sẵn sàng cất cánh đi giao
    FLYING_DELIVERY = "FLYING_DELIVERY"          # Đang bay đi giao hàng cho khách
    RETURN_HOME = "RETURN_HOME"                  # Đang bay về Home sau giao hàng
    OFFLINE = "OFFLINE"                          # Mất kết nối / bảo trì


class UavFleetUnit(BaseModel):
    drone_id: str
    is_real: bool = False
    flight_mode: str = "AUTO"  # "AUTO" | "MANUAL"
    state: FleetUavState = FleetUavState.READY
    battery: float = 100.0
    latitude: float = 16.0544
    longitude: float = 108.2022
    altitude_agl: float = 0.0
    current_mission_id: Optional[int] = None
    target_location: Optional[str] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class FleetManager:
    """Manages multi-UAV Fleet (UAV01 Physical, UAV02/UAV03 Virtual Fleet)
    
    Responsibilities:
    - Multi-UAV State Machine tracking
    - Signal-only loose coupling with Warehouse Docking Station
    - Arrival / Departure Handshake simulation & execution
    """

    _instance: Optional["FleetManager"] = None

    def __init__(self):
        self.fleet: Dict[str, UavFleetUnit] = {
            "UAV01": UavFleetUnit(
                drone_id="UAV01",
                is_real=True,
                flight_mode="AUTO",
                state=FleetUavState.READY,
                battery=95.0,
                latitude=16.0544,
                longitude=108.2022,
            ),
            "UAV02": UavFleetUnit(
                drone_id="UAV02",
                is_real=False,
                flight_mode="AUTO",
                state=FleetUavState.READY,
                battery=98.0,
                latitude=16.0545,
                longitude=108.2025,
            ),
            "UAV03": UavFleetUnit(
                drone_id="UAV03",
                is_real=False,
                flight_mode="AUTO",
                state=FleetUavState.READY,
                battery=100.0,
                latitude=16.0546,
                longitude=108.2028,
            ),
        }
        self.plc_mgr = PLCManager.get_instance()

    @classmethod
    def get_instance(cls) -> "FleetManager":
        if cls._instance is None:
            cls._instance = FleetManager()
        return cls._instance

    def get_all_uavs(self) -> List[Dict[str, Any]]:
        return [u.model_dump(mode="json") for u in self.fleet.values()]

    def get_uav(self, drone_id: str) -> Optional[UavFleetUnit]:
        return self.fleet.get(drone_id)

    async def broadcast_fleet_state(self) -> None:
        try:
            payload = {
                "fleet": self.get_all_uavs(),
                "timestamp": datetime.utcnow().isoformat(),
            }
            await system_ws_manager.broadcast("FLEET_UPDATE", payload)
        except Exception as err:
            logger.error("Error broadcasting FLEET_UPDATE: %s", err)

    def assign_available_uav(self, mission_id: int, mission_type: str) -> UavFleetUnit:
        """Finds a READY UAV or returns the best available unit."""
        # Prefer READY UAVs, prioritizing UAV01 if ready
        ready_uavs = [u for u in self.fleet.values() if u.state == FleetUavState.READY]
        assigned: UavFleetUnit
        if ready_uavs:
            assigned = ready_uavs[0]
        else:
            # Fallback to any UAV
            assigned = list(self.fleet.values())[0]

        assigned.current_mission_id = mission_id
        assigned.state = FleetUavState.FLYING_TO_WAREHOUSE
        assigned.last_updated = datetime.utcnow()
        logger.info("[FleetManager] Assigned %s to Mission #%d (%s)", assigned.drone_id, mission_id, mission_type)
        return assigned

    async def signal_drone_arrived(self, drone_id: str) -> UavFleetUnit:
        """Signal that UAV has landed at Warehouse Dock N1."""
        uav = self.fleet.get(drone_id)
        if not uav:
            raise ValueError(f"UAV {drone_id} not found in fleet")

        uav.state = FleetUavState.LANDED
        uav.altitude_agl = 0.0
        uav.last_updated = datetime.utcnow()

        # Trigger PLC arrival sensor signal
        self.plc_mgr.set_drone_detected(True)
        logger.info("[FleetManager] Drone %s LANDED at Dock N1 -> PLC drone_detected = TRUE", drone_id)

        await self.broadcast_fleet_state()
        return uav

    async def signal_drone_loading(self, drone_id: str) -> UavFleetUnit:
        uav = self.fleet.get(drone_id)
        if uav:
            uav.state = FleetUavState.LOADING
            uav.last_updated = datetime.utcnow()
            await self.broadcast_fleet_state()
        return uav

    async def signal_station_unloaded(self, drone_id: str) -> UavFleetUnit:
        """Warehouse station finished unloading (pickup mission). Drone ready to return home."""
        uav = self.fleet.get(drone_id)
        if uav:
            uav.state = FleetUavState.READY_TO_DEPART_HOME
            uav.last_updated = datetime.utcnow()
            await self.broadcast_fleet_state()
        return uav

    async def signal_station_loaded(self, drone_id: str) -> UavFleetUnit:
        """Warehouse station finished loading (delivery mission). Drone ready to depart for delivery."""
        uav = self.fleet.get(drone_id)
        if uav:
            uav.state = FleetUavState.READY_TO_DEPART_DELIVERY
            uav.last_updated = datetime.utcnow()
            await self.broadcast_fleet_state()
        return uav

    async def signal_drone_depart_home(self, drone_id: str) -> UavFleetUnit:
        """Drone takes off and returns home, releasing the dock pad."""
        uav = self.fleet.get(drone_id)
        if not uav:
            raise ValueError(f"UAV {drone_id} not found in fleet")

        uav.state = FleetUavState.RETURN_HOME
        uav.altitude_agl = 15.0
        uav.last_updated = datetime.utcnow()

        # Clear PLC arrival sensor signal
        self.plc_mgr.set_drone_detected(False)
        logger.info("[FleetManager] Drone %s DEPARTED to Home -> Dock pad FREE, PLC drone_detected = FALSE", drone_id)

        # Auto transition to READY after short flight simulation
        async def _auto_reach_home():
            await asyncio.sleep(3.0)
            uav.state = FleetUavState.READY
            uav.altitude_agl = 0.0
            uav.current_mission_id = None
            uav.last_updated = datetime.utcnow()
            logger.info("[FleetManager] Drone %s arrived at Home -> Status READY", drone_id)
            await self.broadcast_fleet_state()

        asyncio.create_task(_auto_reach_home())
        await self.broadcast_fleet_state()
        return uav

    async def signal_drone_depart_delivery(self, drone_id: str) -> UavFleetUnit:
        """Drone takes off for customer delivery, releasing the dock pad."""
        uav = self.fleet.get(drone_id)
        if not uav:
            raise ValueError(f"UAV {drone_id} not found in fleet")

        uav.state = FleetUavState.FLYING_DELIVERY
        uav.altitude_agl = 20.0
        uav.last_updated = datetime.utcnow()

        # Clear PLC arrival sensor signal
        self.plc_mgr.set_drone_detected(False)
        logger.info("[FleetManager] Drone %s DEPARTED for Customer Delivery -> PLC drone_detected = FALSE", drone_id)

        # Auto transition to RETURN_HOME -> READY after simulated delivery
        async def _auto_complete_delivery():
            await asyncio.sleep(4.0)
            uav.state = FleetUavState.RETURN_HOME
            await self.broadcast_fleet_state()
            await asyncio.sleep(2.0)
            uav.state = FleetUavState.READY
            uav.altitude_agl = 0.0
            uav.current_mission_id = None
            uav.last_updated = datetime.utcnow()
            logger.info("[FleetManager] Drone %s completed delivery and back Home -> Status READY", drone_id)
            await self.broadcast_fleet_state()

        asyncio.create_task(_auto_complete_delivery())
        await self.broadcast_fleet_state()
        return uav

    async def set_flight_mode(self, drone_id: str, mode: str) -> UavFleetUnit:
        uav = self.fleet.get(drone_id)
        if not uav:
            raise ValueError(f"UAV {drone_id} not found")
        uav.flight_mode = mode.upper()
        uav.last_updated = datetime.utcnow()
        await self.broadcast_fleet_state()
        return uav


fleet_manager = FleetManager.get_instance()

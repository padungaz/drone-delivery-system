import asyncio
import logging
import math
from datetime import datetime
from typing import Optional, Dict, Any

from app.models.schemas import TelemetryPayload, DroneState, LandingLocation
from app.services.drone_service import drone_service
from app.services.fleet_manager import fleet_manager
from app.services.plc_manager import PLCManager
from app.websocket.handler import manager as drone_ws_manager
from app.websocket.manager import system_ws_manager

logger = logging.getLogger(__name__)


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate compass heading (0-360 degrees) from point 1 to point 2."""
    if lat1 == lat2 and lon1 == lon2:
        return 0.0
    d_lon = math.radians(lon2 - lon1)
    y = math.sin(d_lon) * math.cos(math.radians(lat2))
    x = math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(d_lon)
    brng = math.degrees(math.atan2(y, x))
    return (brng + 360.0) % 360.0


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate Haversine ground distance in meters."""
    R = 6371000.0  # Earth radius in meters
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class UavMissionSimulator:
    """Simulates real-world autonomous UAV flight for system missions.
    
    Operates purely through software between Backend and Frontend WebSockets.
    No physical drone hardware or Raspberry Pi required.
    """

    _instance: Optional["UavMissionSimulator"] = None

    def __init__(self):
        self.is_running: bool = False
        self.is_paused: bool = False
        self.mission_id: Optional[int] = None
        self.mission_type: str = "DRONE_DELIVERY"
        self.drone_id: str = "UAV01"
        self.speed_multiplier: float = 1.0  # 1.0 = Normal (10m/s), 2.0 = Fast, 5.0 = Super

        # Default Home coordinate (Warehouse Pad N1)
        self.home_lat: float = 16.054400
        self.home_lon: float = 108.202200
        
        # Target coordinate
        self.target_lat: float = 16.059200
        self.target_lon: float = 108.208500

        # Live Flight Telemetry State
        self.current_lat: float = self.home_lat
        self.current_lon: float = self.home_lon
        self.current_alt: float = 0.0
        self.current_speed: float = 0.0
        self.current_heading: float = 0.0
        self.current_battery: float = 98.0
        self.flight_phase: str = "IDLE"  # IDLE | TAKEOFF | EN_ROUTE_OUTBOUND | HOVER_ACTION | EN_ROUTE_RETURN | PRECISION_LANDING | COMPLETED
        self.progress_percent: float = 0.0
        self.step_message: str = "UAV Simulator sẵn sàng."

        self._task: Optional[asyncio.Task] = None
        self._rtl_requested: bool = False

    @classmethod
    def get_instance(cls) -> "UavMissionSimulator":
        if cls._instance is None:
            cls._instance = UavMissionSimulator()
        return cls._instance

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "mission_id": self.mission_id,
            "mission_type": self.mission_type,
            "drone_id": self.drone_id,
            "speed_multiplier": self.speed_multiplier,
            "home": {"lat": self.home_lat, "lon": self.home_lon},
            "target": {"lat": self.target_lat, "lon": self.target_lon},
            "current": {
                "lat": self.current_lat,
                "lon": self.current_lon,
                "altitude": round(self.current_alt, 2),
                "speed": round(self.current_speed, 1),
                "heading": round(self.current_heading, 1),
                "battery": round(self.current_battery, 1),
            },
            "flight_phase": self.flight_phase,
            "progress_percent": round(self.progress_percent, 1),
            "step_message": self.step_message,
        }

    async def start_flight(
        self,
        mission_id: Optional[int] = None,
        mission_type: str = "DRONE_DELIVERY",
        home_lat: Optional[float] = None,
        home_lon: Optional[float] = None,
        target_lat: Optional[float] = None,
        target_lon: Optional[float] = None,
        speed_multiplier: float = 1.0,
    ) -> Dict[str, Any]:
        """Start a new simulated mission flight."""
        if self.is_running and self._task and not self._task.done():
            self._task.cancel()

        self.mission_id = mission_id or 1
        self.mission_type = mission_type
        self.speed_multiplier = max(0.5, min(10.0, speed_multiplier))

        if home_lat and home_lon and home_lat != 0:
            self.home_lat = home_lat
            self.home_lon = home_lon
        
        if target_lat and target_lon and target_lat != 0:
            self.target_lat = target_lat
            self.target_lon = target_lon
        else:
            # Default offset destination (~800m away)
            self.target_lat = self.home_lat + 0.0048
            self.target_lon = self.home_lon + 0.0063

        self.current_lat = self.home_lat
        self.current_lon = self.home_lon
        self.current_alt = 0.0
        self.current_speed = 0.0
        self.current_battery = 98.0
        self.progress_percent = 0.0
        self.flight_phase = "TAKEOFF"
        self.is_running = True
        self.is_paused = False
        self._rtl_requested = False
        self.step_message = f"🚀 UAV {self.drone_id} bắt đầu cất cánh thực thi nhiệm vụ #{self.mission_id}..."

        self._task = asyncio.create_task(self._run_flight_loop())
        logger.info("[UavMissionSimulator] Started simulated flight for Mission #%s to (%s, %s) at %sx speed",
                    self.mission_id, self.target_lat, self.target_lon, self.speed_multiplier)
        return self.get_status()

    async def pause_flight(self) -> Dict[str, Any]:
        """Pause flight simulation (drone hovers in place)."""
        if self.is_running:
            self.is_paused = True
            self.current_speed = 0.0
            self.step_message = f"⏸️ UAV {self.drone_id} tạm dừng (Hover giữ vị trí tại {self.current_lat:.6f}, {self.current_lon:.6f})."
            await self._broadcast_telemetry()
        return self.get_status()

    async def resume_flight(self) -> Dict[str, Any]:
        """Resume flight simulation."""
        if self.is_running:
            self.is_paused = False
            self.step_message = f"▶️ UAV {self.drone_id} tiếp tục bay theo hành trình."
            await self._broadcast_telemetry()
        return self.get_status()

    async def return_to_home(self) -> Dict[str, Any]:
        """Trigger Return To Home (RTL) immediately from current position."""
        if self.is_running:
            self._rtl_requested = True
            self.is_paused = False
            self.flight_phase = "EN_ROUTE_RETURN"
            self.step_message = f"🏠 Lệnh RTL kích hoạt: UAV {self.drone_id} đang quay về Trạm kho N1..."
            await self._broadcast_telemetry()
        return self.get_status()

    async def cancel_flight(self) -> Dict[str, Any]:
        """Abort and cancel flight simulation."""
        if self._task and not self._task.done():
            self._task.cancel()
        self.is_running = False
        self.is_paused = False
        self.flight_phase = "IDLE"
        self.current_alt = 0.0
        self.current_speed = 0.0
        self.step_message = f"🛑 Chuyến bay mô phỏng đã bị hủy bỏ bởi Operator."
        await self._broadcast_telemetry(drone_state=DroneState.IDLE, armed=False)
        return self.get_status()

    def set_speed(self, multiplier: float) -> None:
        self.speed_multiplier = max(0.5, min(10.0, multiplier))

    async def _run_flight_loop(self) -> None:
        """Core flight simulation loop updating at 500ms intervals."""
        cruise_altitude = 15.0  # Cruising altitude in meters
        cruise_speed = 10.0     # Normal cruise speed 10 m/s
        
        try:
            total_leg_dist = calculate_distance(self.home_lat, self.home_lon, self.target_lat, self.target_lon)
            total_flight_dist = total_leg_dist * 2.0  # Outbound + Return

            # -----------------------------------------------------------------
            # 1. PHA CẤT CÁNH (TAKEOFF: 0m -> 15m)
            # -----------------------------------------------------------------
            self.flight_phase = "TAKEOFF"
            self.current_heading = calculate_bearing(self.home_lat, self.home_lon, self.target_lat, self.target_lon)
            takeoff_steps = max(4, int(6 / self.speed_multiplier))
            
            for i in range(1, takeoff_steps + 1):
                while self.is_paused:
                    await asyncio.sleep(0.5)
                self.current_alt = (i / takeoff_steps) * cruise_altitude
                self.current_speed = 2.5 * self.speed_multiplier
                self.progress_percent = (i / takeoff_steps) * 8.0
                self.step_message = f"🛫 Đang cất cánh: Độ cao {self.current_alt:.1f}m / {cruise_altitude}m..."
                await self._broadcast_telemetry(drone_state=DroneState.TAKEOFF, armed=True)
                await asyncio.sleep(0.5)

            # -----------------------------------------------------------------
            # 2. PHA BAY ĐẾN ĐÍCH (EN_ROUTE_OUTBOUND: Home -> Target)
            # -----------------------------------------------------------------
            self.flight_phase = "EN_ROUTE_OUTBOUND"
            self.current_alt = cruise_altitude
            self.current_speed = cruise_speed * self.speed_multiplier
            self.current_heading = calculate_bearing(self.home_lat, self.home_lon, self.target_lat, self.target_lon)

            flight_time_sec = total_leg_dist / (cruise_speed * self.speed_multiplier)
            nav_steps = max(6, int(flight_time_sec / 0.5))

            for step in range(1, nav_steps + 1):
                while self.is_paused:
                    await asyncio.sleep(0.5)
                if self._rtl_requested:
                    break

                fraction = step / nav_steps
                self.current_lat = self.home_lat + (self.target_lat - self.home_lat) * fraction
                self.current_lon = self.home_lon + (self.target_lon - self.home_lon) * fraction
                self.current_battery = max(20.0, self.current_battery - (0.04 * self.speed_multiplier))
                
                dist_remaining = calculate_distance(self.current_lat, self.current_lon, self.target_lat, self.target_lon)
                self.progress_percent = 8.0 + fraction * 42.0  # 8% to 50%
                self.step_message = (
                    f"🚁 Đang bay đến điểm giao: Cách đích {dist_remaining:.0f}m "
                    f"| Vận tốc: {self.current_speed:.1f} m/s | Pin: {self.current_battery:.0f}%"
                )
                
                state = DroneState.FLY_TO_DROP if self.mission_type == "DRONE_DELIVERY" else DroneState.FLY_TO_PICKUP
                await self._broadcast_telemetry(drone_state=state, armed=True)
                await asyncio.sleep(0.5)

            # -----------------------------------------------------------------
            # 3. PHA THAO TÁC TẠI ĐÍCH (HOVER_ACTION: Hạ 2m -> Xác nhận -> Lên 15m)
            # -----------------------------------------------------------------
            if not self._rtl_requested:
                self.flight_phase = "HOVER_ACTION"
                self.current_lat = self.target_lat
                self.current_lon = self.target_lon
                self.current_speed = 0.0
                self.progress_percent = 50.0

                # Hạ độ cao giao/nhận hàng
                self.step_message = "🛬 Đang tiếp cận điểm giao/nhận hàng, hạ độ cao an toàn (2.0m)..."
                self.current_alt = 2.0
                await self._broadcast_telemetry(drone_state=DroneState.WAIT_DROP_CONFIRM, armed=True)
                await asyncio.sleep(max(1.0, 3.0 / self.speed_multiplier))

                self.step_message = "📦 Đã hoàn tất giao/nhận kiện hàng! Lấy lại độ cao hành trình..."
                self.current_alt = cruise_altitude
                await self._broadcast_telemetry(drone_state=DroneState.TAKEOFF, armed=True)
                await asyncio.sleep(max(0.5, 1.5 / self.speed_multiplier))

            # -----------------------------------------------------------------
            # 4. PHA BAY VỀ TRẠM (EN_ROUTE_RETURN: Target -> Home)
            # -----------------------------------------------------------------
            self.flight_phase = "EN_ROUTE_RETURN"
            self.current_speed = cruise_speed * self.speed_multiplier
            self.current_heading = calculate_bearing(self.current_lat, self.current_lon, self.home_lat, self.home_lon)

            start_return_lat = self.current_lat
            start_return_lon = self.current_lon
            return_dist = calculate_distance(start_return_lat, start_return_lon, self.home_lat, self.home_lon)
            return_time_sec = return_dist / (cruise_speed * self.speed_multiplier)
            return_steps = max(6, int(return_time_sec / 0.5))

            for step in range(1, return_steps + 1):
                while self.is_paused:
                    await asyncio.sleep(0.5)

                fraction = step / return_steps
                self.current_lat = start_return_lat + (self.home_lat - start_return_lat) * fraction
                self.current_lon = start_return_lon + (self.home_lon - start_return_lon) * fraction
                self.current_battery = max(15.0, self.current_battery - (0.04 * self.speed_multiplier))
                
                dist_to_home = calculate_distance(self.current_lat, self.current_lon, self.home_lat, self.home_lon)
                self.progress_percent = 52.0 + fraction * 40.0  # 52% to 92%
                self.step_message = (
                    f"🏠 Đang quay về Trạm kho N1: Còn {dist_to_home:.0f}m "
                    f"| Vận tốc: {self.current_speed:.1f} m/s | Pin: {self.current_battery:.0f}%"
                )
                await self._broadcast_telemetry(drone_state=DroneState.RETURN_HOME, armed=True)
                await asyncio.sleep(0.5)

            # -----------------------------------------------------------------
            # 5. PHA HẠ CÁNH CHÍNH XÁC (PRECISION_LANDING: 15m -> 0m tại Bãi N1)
            # -----------------------------------------------------------------
            self.flight_phase = "PRECISION_LANDING"
            self.current_lat = self.home_lat
            self.current_lon = self.home_lon
            self.current_speed = 1.2
            land_steps = max(4, int(6 / self.speed_multiplier))

            for i in range(1, land_steps + 1):
                self.current_alt = cruise_altitude * (1.0 - (i / land_steps))
                self.progress_percent = 92.0 + (i / land_steps) * 8.0
                self.step_message = f"🎯 Đang hạ cánh chính xác xuống Bãi Trạm N1: Độ cao {self.current_alt:.1f}m (Camera Aruco Detected)..."
                await self._broadcast_telemetry(drone_state=DroneState.PRECISION_LANDING, armed=True, aruco=True)
                await asyncio.sleep(0.5)

            # -----------------------------------------------------------------
            # 6. HOÀN THÀNH (COMPLETED: Báo PLC & Trạm sẵn sàng)
            # -----------------------------------------------------------------
            self.flight_phase = "COMPLETED"
            self.current_alt = 0.0
            self.current_speed = 0.0
            self.progress_percent = 100.0
            self.is_running = False
            self.step_message = f"🏁 UAV {self.drone_id} đã hạ cánh an toàn tại Bãi N1. Chu trình hoàn tất 100%!"
            await self._broadcast_telemetry(drone_state=DroneState.LANDED, armed=False, aruco=True)

            # Signal hardware/simulation arrival
            try:
                await fleet_manager.signal_drone_arrived(self.drone_id)
            except Exception as err:
                logger.warning("Signal drone arrived warning: %s", err)

            logger.info("[UavMissionSimulator] ✅ Simulated flight completed successfully.")

        except asyncio.CancelledError:
            logger.info("[UavMissionSimulator] Flight loop cancelled.")
        except Exception as exc:
            logger.error("[UavMissionSimulator] Error in flight simulation loop: %s", exc)
            self.flight_phase = "ERROR"
            self.is_running = False
            self.step_message = f"❌ Lỗi mô phỏng chuyến bay: {exc}"
            await self._broadcast_telemetry(drone_state=DroneState.ERROR, armed=False)

    async def _broadcast_telemetry(
        self,
        drone_state: DroneState = DroneState.FLY_TO_DROP,
        armed: bool = True,
        aruco: bool = False
    ) -> None:
        """Broadcast live telemetry to Leaflet Map and HMI panels via WebSockets."""
        payload = TelemetryPayload(
            timestamp=datetime.utcnow(),
            drone_id=self.drone_id,
            drone_state=drone_state,
            latitude=self.current_lat,
            longitude=self.current_lon,
            altitude_relative=self.current_alt,
            altitude_agl=self.current_alt,
            battery=self.current_battery,
            ground_speed=self.current_speed,
            heading=self.current_heading,
            gps_satellite=14,
            flight_mode="AUTO",
            aruco_detected=aruco,
            landing_status="ON_PAD" if self.current_alt == 0.0 else "IN_FLIGHT",
            landing_location=LandingLocation.WAREHOUSE_PAD if self.flight_phase in ("PRECISION_LANDING", "COMPLETED") else LandingLocation.CUSTOMER_DROP,
            armed=armed,
        )

        # 1. Update in-memory drone service & broadcast to client WebSocket (MapPanel / TelemetryPanel)
        drone_service.update_telemetry(payload)
        await drone_ws_manager.broadcast_to_clients({
            "type": "telemetry",
            "payload": payload.model_dump(mode="json"),
        })

        # 2. Broadcast high-level mission flight HUD update
        await system_ws_manager.broadcast("UAV_MISSION_FLIGHT_UPDATE", self.get_status())


uav_mission_simulator = UavMissionSimulator.get_instance()

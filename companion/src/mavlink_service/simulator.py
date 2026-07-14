"""
MAVLink mock controller — mô phỏng PX4 trên PC khi không có SITL/hardware.

Dùng khi config.MAVLINK_BACKEND == "mock"
"""

import logging
import math
import time
from dataclasses import dataclass, field

import config
from src.mavlink_service.controller import TelemetryData

logger = logging.getLogger(__name__)


@dataclass
class _SimPose:
    lat: float = config.SIM_HOME_LAT
    lon: float = config.SIM_HOME_LON
    alt: float = 0.0
    heading: float = 0.0
    speed: float = 0.0
    armed: bool = False
    mode: str = "MANUAL"
    target_lat: float = 0.0
    target_lon: float = 0.0
    target_alt: float = 0.0
    has_target: bool = False
    landing: bool = False
    last_tick: float = field(default_factory=time.time)


class MavlinkSimulator:
    """Mô phỏng MAVLink/PX4 cho dev trên PC."""

    def __init__(self):
        self.telemetry = TelemetryData(
            latitude=config.SIM_HOME_LAT,
            longitude=config.SIM_HOME_LON,
            gps_satellite=12,
            gps_fix_type=3,
            battery=95.0,
            flight_mode="MANUAL",
        )
        self._pose = _SimPose()
        self._connected = False
        self._last_command_time: dict[str, float] = {}

    def connect(self) -> bool:
        self._connected = True
        self._sync_telemetry()
        logger.info("MAVLink MOCK connected (sim mode — no real PX4)")
        return True

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _sync_telemetry(self) -> None:
        t = self.telemetry
        t.latitude = self._pose.lat
        t.longitude = self._pose.lon
        t.altitude_relative = self._pose.alt
        t.altitude_agl = max(0.0, self._pose.alt)
        t.ground_speed = self._pose.speed
        t.heading = self._pose.heading
        t.armed = self._pose.armed
        t.flight_mode = self._pose.mode
        t.gps_satellite = 12
        t.last_update = time.time()

    def poll_messages(self) -> None:
        if not self._connected:
            return

        now = time.time()
        dt = min(now - self._pose.last_tick, 0.1)
        self._pose.last_tick = now
        self._simulate_physics(dt)
        self._sync_telemetry()

    def _simulate_physics(self, dt: float) -> None:
        p = self._pose

        if p.landing and p.alt > 0:
            p.alt = max(0.0, p.alt - 1.0 * dt)
            p.speed = max(0.0, p.speed - 0.5 * dt)
            if p.alt <= 0.05:
                p.alt = 0.0
                p.speed = 0.0
                p.armed = False
                p.mode = "MANUAL"
                p.landing = False
            return

        if p.has_target:
            dist = self._haversine_m(p.lat, p.lon, p.target_lat, p.target_lon)
            if dist > 1.0:
                bearing = self._bearing(p.lat, p.lon, p.target_lat, p.target_lon)
                p.heading = bearing
                step = min(8.0 * dt, dist)
                p.lat, p.lon = self._move_toward(p.lat, p.lon, bearing, step)
                p.speed = 4.0
            else:
                p.speed = max(0.0, p.speed - 2.0 * dt)

            alt_diff = p.target_alt - p.alt
            if abs(alt_diff) > 0.2:
                p.alt += math.copysign(min(2.0 * dt, abs(alt_diff)), alt_diff)
            else:
                p.alt = p.target_alt
                if dist <= config.NAV_ACCEPTANCE_RADIUS_M:
                    p.has_target = False
                    p.speed = 0.0

    def _can_send(self, cmd_type: str) -> bool:
        now = time.time()
        last = self._last_command_time.get(cmd_type, 0)
        if now - last < 1.0:
            return False
        self._last_command_time[cmd_type] = now
        return True

    def set_mode(self, mode: str) -> bool:
        if not self._can_send("mode"):
            return False
        self._pose.mode = mode
        if mode == "AUTO.LAND":
            self._pose.landing = True
        logger.info("[MOCK] Mode → %s", mode)
        return True

    def arm(self) -> bool:
        if not self._can_send("arm"):
            return False
        self._pose.armed = True
        self._pose.mode = "AUTO.MISSION"
        logger.info("[MOCK] Armed")
        return True

    def disarm(self) -> bool:
        if not self._can_send("disarm"):
            return False
        self._pose.armed = False
        logger.info("[MOCK] Disarmed")
        return True

    def takeoff(self, altitude_m: float) -> bool:
        if not self._can_send("takeoff"):
            return False
        self._pose.target_alt = altitude_m
        self._pose.has_target = False
        self._pose.mode = "AUTO.TAKEOFF"
        logger.info("[MOCK] Takeoff → %.1f m", altitude_m)
        return True

    def goto_location(self, lat: float, lon: float, alt_m: float) -> bool:
        if not self._can_send("goto"):
            return False
        self._pose.target_lat = lat
        self._pose.target_lon = lon
        self._pose.target_alt = alt_m
        self._pose.has_target = True
        self._pose.landing = False
        self._pose.mode = "AUTO.MISSION"
        logger.info("[MOCK] Goto lat=%.7f lon=%.7f alt=%.1f", lat, lon, alt_m)
        return True

    def land(self) -> bool:
        return self.set_mode("AUTO.LAND")

    def rtl(self) -> bool:
        if not self._can_send("rtl"):
            return False
        self.goto_location(config.SIM_HOME_LAT, config.SIM_HOME_LON, config.RTL_ALTITUDE_M)
        self._pose.mode = "AUTO.RTL"
        logger.info("[MOCK] RTL")
        return True

    def send_landing_target(self, angle_x: float, angle_y: float, distance: float, **_) -> None:
        if distance < 2.0 and self._pose.alt > 0:
            self._pose.landing = True
            self._pose.mode = "AUTO.PRECLAND"

    def distance_to(self, lat: float, lon: float) -> float:
        return self._haversine_m(self._pose.lat, self._pose.lon, lat, lon)

    def is_at_location(self, lat: float, lon: float, radius_m: float) -> bool:
        return self.distance_to(lat, lon) <= radius_m

    def is_landed(self) -> bool:
        return not self._pose.armed and self._pose.alt < 0.5 and self._pose.speed < 0.3

    @staticmethod
    def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        rlat1, rlon1 = math.radians(lat1), math.radians(lon1)
        rlat2, rlon2 = math.radians(lat2), math.radians(lon2)
        dlat, dlon = rlat2 - rlat1, rlon2 - rlon1
        a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
        return 6371000 * 2 * math.asin(math.sqrt(a))

    @staticmethod
    def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        rlat1, rlon1 = math.radians(lat1), math.radians(lon1)
        rlat2, rlon2 = math.radians(lat2), math.radians(lon2)
        dlon = rlon2 - rlon1
        x = math.sin(dlon) * math.cos(rlat2)
        y = math.cos(rlat1) * math.sin(rlat2) - math.sin(rlat1) * math.cos(rlat2) * math.cos(dlon)
        return (math.degrees(math.atan2(x, y)) + 360) % 360

    @staticmethod
    def _move_toward(lat: float, lon: float, bearing_deg: float, dist_m: float) -> tuple[float, float]:
        r = 6371000
        brng = math.radians(bearing_deg)
        rlat = math.radians(lat)
        rlon = math.radians(lon)
        new_lat = math.asin(
            math.sin(rlat) * math.cos(dist_m / r)
            + math.cos(rlat) * math.sin(dist_m / r) * math.cos(brng)
        )
        new_lon = rlon + math.atan2(
            math.sin(brng) * math.sin(dist_m / r) * math.cos(rlat),
            math.cos(dist_m / r) - math.sin(rlat) * math.sin(new_lat),
        )
        return math.degrees(new_lat), math.degrees(new_lon)

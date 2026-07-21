"""
MAVLink controller — Raspberry Pi 5 ↔ Pixhawk 6C (PX4).

Connection: /dev/ttyAMA0 (GPIO UART) hoặc /dev/ttyUSB0 (USB-Serial)
Baudrate:   57600 hoặc 921600 (cấu hình trong .env)
"""

import logging
import math
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from pymavlink import mavutil

import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Command rate limiting
# ---------------------------------------------------------------------------

COMMAND_COOLDOWN = {
    "arm":    2.0,
    "takeoff": 3.0,
    "goto":   2.0,
    "land":   3.0,
    "rtl":    2.0,
    "mode":   1.0,
    "disarm": 2.0,
}


# ---------------------------------------------------------------------------
# Telemetry dataclass
# ---------------------------------------------------------------------------

@dataclass
class TelemetryData:
    latitude:  float = 0.0
    longitude: float = 0.0

    # PX4 HOME-relative altitude (GLOBAL_POSITION_INT.relative_alt)
    altitude_relative: float = 0.0

    # MTF-02P rangefinder AGL (DISTANCE_SENSOR.current_distance)
    altitude_agl:      float = 0.0
    rangefinder_valid: bool  = False

    ground_speed: float = 0.0
    heading:      float = 0.0
    battery:      float = 100.0

    gps_satellite: int = 0
    gps_fix_type:  int = 0

    flight_mode: str  = "UNKNOWN"
    armed:       bool = False

    roll:  float = 0.0
    pitch: float = 0.0
    yaw:   float = 0.0

    last_update: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# MavlinkController
# ---------------------------------------------------------------------------

class MavlinkController:
    """
    MAVLink interface for PX4 on Pixhawk 6C via UART.

    Reads telemetry from:
      - GLOBAL_POSITION_INT  (GPS position + relative altitude)
      - DISTANCE_SENSOR      (MTF-02P rangefinder AGL)
      - VFR_HUD              (groundspeed, heading)
      - SYS_STATUS           (battery)
      - ATTITUDE             (roll, pitch, yaw)
      - GPS_RAW_INT          (satellite count, fix type)
      - HEARTBEAT            (flight mode, armed state)

    Sends commands:
      - arm / disarm
      - set_mode / set_mode_offboard
      - takeoff
      - goto_location
      - land / rtl
      - send_landing_target  (ArUco precision landing)
    """

    def __init__(self):
        self.connection: Optional[mavutil.mavlink_connection] = None
        self.telemetry = TelemetryData()
        self._last_command_time: dict[str, float] = {}
        self._connected = False
        self.connection_uri = config.MAVLINK_DEVICE
        self.use_baud = True

        # OFFBOARD keepalive: PX4 requires continuous setpoint stream
        # to stay in OFFBOARD mode (COM_OF_LOSS_T timeout ~1-2 s).
        self._offboard_keepalive_running = False
        self._offboard_keepalive_thread: Optional[threading.Thread] = None

    # ===================================================================
    # Connection
    # ===================================================================

    def connect(self) -> bool:
        try:
            logger.info(
                "Connecting to MAVLink: %s @ %d baud",
                self.connection_uri,
                config.MAVLINK_BAUD,
            )

            if self.use_baud:
                self.connection = mavutil.mavlink_connection(
                    self.connection_uri,
                    baud=config.MAVLINK_BAUD,
                )
            else:
                self.connection = mavutil.mavlink_connection(self.connection_uri)

            logger.info(
                "Waiting for PX4 heartbeat (timeout=%ds)...",
                config.MAVLINK_HEARTBEAT_TIMEOUT,
            )
            
            start_time = time.time()
            while True:
                if time.time() - start_time > config.MAVLINK_HEARTBEAT_TIMEOUT:
                    raise TimeoutError("Heartbeat timeout - No valid PX4 heartbeat received")
                
                msg = self.connection.wait_heartbeat(blocking=True, timeout=1.0)
                if msg is not None:
                    src_sys = msg.get_srcSystem()
                    if src_sys != 0 and src_sys != 255:
                        self.connection.target_system = src_sys
                        self.connection.target_component = msg.get_srcComponent()
                        break
                    else:
                        logger.debug("Bỏ qua heartbeat từ system=%s", src_sys)
            
            self._connected = True

            logger.info(
                "[INFO] PX4 heartbeat received — system=%s component=%s",
                self.connection.target_system,
                self.connection.target_component,
            )
            return True

        except Exception as exc:
            logger.error("MAVLink connection failed: %s", exc)
            self._connected = False
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected and self.connection is not None

    # ===================================================================
    # MAVLink receive
    # ===================================================================

    def poll_messages(self) -> None:
        """Read all available MAVLink messages (non-blocking). Call in main loop."""
        if not self.is_connected:
            return

        while True:
            msg = self.connection.recv_match(blocking=False)
            if msg is None:
                break
            self._process_message(msg)

    def _process_message(self, msg) -> None:
        msg_type = msg.get_type()
        self.telemetry.last_update = time.time()

        # ---- GPS position ----
        if msg_type == "GLOBAL_POSITION_INT":
            self.telemetry.latitude          = msg.lat / 1e7
            self.telemetry.longitude         = msg.lon / 1e7
            self.telemetry.altitude_relative = msg.relative_alt / 1000.0

        # ---- MTF-02P rangefinder AGL ----
        elif msg_type == "DISTANCE_SENSOR":
            distance_cm = msg.current_distance
            if distance_cm > 0:
                self.telemetry.altitude_agl     = distance_cm / 100.0
                self.telemetry.rangefinder_valid = True
                logger.debug("MTF-02P AGL %.2f m", self.telemetry.altitude_agl)

        # ---- Speed / Heading ----
        elif msg_type == "VFR_HUD":
            self.telemetry.ground_speed = msg.groundspeed
            self.telemetry.heading      = msg.heading

        # ---- Battery ----
        elif msg_type == "SYS_STATUS":
            if msg.battery_remaining >= 0:
                self.telemetry.battery = float(msg.battery_remaining)

        # ---- Attitude ----
        elif msg_type == "ATTITUDE":
            self.telemetry.roll  = math.degrees(msg.roll)
            self.telemetry.pitch = math.degrees(msg.pitch)
            self.telemetry.yaw   = math.degrees(msg.yaw)

        # ---- GPS status ----
        elif msg_type == "GPS_RAW_INT":
            self.telemetry.gps_satellite = msg.satellites_visible
            self.telemetry.gps_fix_type  = msg.fix_type

        # ---- Flight mode + armed state ----
        elif msg_type == "HEARTBEAT":
            self.telemetry.armed = bool(
                msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
            )
            self.telemetry.flight_mode = mavutil.mode_string_v10(msg)

    # ===================================================================
    # Command control
    # ===================================================================

    def _can_send(self, cmd_type: str) -> bool:
        now      = time.time()
        last     = self._last_command_time.get(cmd_type, 0)
        cooldown = COMMAND_COOLDOWN.get(cmd_type, 1.0)
        if now - last < cooldown:
            logger.debug("Command %s throttled (cooldown)", cmd_type)
            return False
        self._last_command_time[cmd_type] = now
        return True

    def _resolve_mode_id(self, mode: str):
        """Resolve PX4 mode string to (custom_mode, custom_sub_mode) tuple."""
        mode_id = self.connection.mode_mapping().get(mode)
        if mode_id is None:
            return None, None
        if isinstance(mode_id, tuple):
            custom_mode = float(mode_id[0])
            custom_sub_mode = float(mode_id[1]) if len(mode_id) > 1 else 0.0
        else:
            custom_mode = float(mode_id)
            custom_sub_mode = 0.0
        return custom_mode, custom_sub_mode

    def _send_set_mode_command(self, custom_mode: float, custom_sub_mode: float) -> None:
        """Send MAV_CMD_DO_SET_MODE to PX4."""
        self.connection.mav.command_long_send(
            self.connection.target_system,
            self.connection.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_MODE,
            0,  # confirmation
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,  # param1
            custom_mode,      # param2: custom mode
            custom_sub_mode,  # param3: custom sub_mode
            0.0, 0.0, 0.0, 0.0,
        )

    def wait_command_ack(self, command_id: int, timeout: float = 3.0) -> bool:
        """Wait for COMMAND_ACK from PX4. Returns True if ACCEPTED."""
        start = time.time()
        while time.time() - start < timeout:
            msg = self.connection.recv_match(
                type="COMMAND_ACK", blocking=True, timeout=0.5,
            )
            if msg and msg.command == command_id:
                if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                    return True
                else:
                    logger.warning(
                        "COMMAND_ACK rejected: cmd=%d result=%d",
                        command_id, msg.result,
                    )
                    return False
        logger.warning("COMMAND_ACK timeout for cmd=%d", command_id)
        return False

    def set_mode(self, mode: str, retries: int = 3) -> bool:
        """Set PX4 flight mode with ACK verification and retry."""
        if not self._can_send("mode"):
            return False
        try:
            custom_mode, custom_sub_mode = self._resolve_mode_id(mode)
            if custom_mode is None:
                logger.error("Unknown flight mode: %s", mode)
                return False

            # Switching away from OFFBOARD → stop keepalive
            self._stop_offboard_keepalive()

            for attempt in range(1, retries + 1):
                self._send_set_mode_command(custom_mode, custom_sub_mode)
                logger.info(
                    "Mode set → %s (custom_mode=%.0f, sub_mode=%.0f) [attempt %d/%d]",
                    mode, custom_mode, custom_sub_mode, attempt, retries,
                )

                if self.wait_command_ack(
                    mavutil.mavlink.MAV_CMD_DO_SET_MODE, timeout=2.0,
                ):
                    logger.info("Mode %s confirmed by PX4", mode)
                    return True

                logger.warning("Mode %s not confirmed, retrying...", mode)
                self._last_command_time.pop("mode", None)
                time.sleep(0.3)

            logger.error("Failed to set mode %s after %d attempts", mode, retries)
            return False
        except Exception as exc:
            logger.error("set_mode failed: %s", exc)
            return False

    # ===================================================================
    # OFFBOARD control & keepalive (Đã tối ưu dứt điểm Race Condition)
    # ===================================================================

    def set_mode_offboard(self, retries: int = 3) -> bool:
        """
        Switch to OFFBOARD mode for PX4 safely without stream disconnection.

        This method:
          1. Starts the background keepalive thread IMMEDIATELY at 20 Hz
          2. Waits 2.0 seconds while the thread streams velocity setpoints
          3. Sends MAV_CMD_DO_SET_MODE and verifies ACK (stream never drops!)
        """
        if not self.is_connected:
            logger.error("set_mode_offboard: not connected")
            return False

        try:
            custom_mode, custom_sub_mode = self._resolve_mode_id("OFFBOARD")
            if custom_mode is None:
                logger.error("OFFBOARD not found in mode_mapping")
                return False

            # ── Phase 1: Bật luồng Keepalive thread phát setpoint 20Hz NGAY TỪ ĐẦU ──
            logger.info("OFFBOARD: Starting continuous setpoint keepalive thread...")
            self._start_offboard_keepalive()

            # ── Phase 2: Đợi 2.0s cho luồng setpoint đi vào quỹ đạo mượt mà ──
            logger.info("OFFBOARD: Streaming setpoints for 2 s before switching mode...")
            time.sleep(2.0)

            # ── Phase 3: Bắn lệnh chuyển mode (Setpoint vẫn đang chảy liên tục 20Hz) ──
            for attempt in range(1, retries + 1):
                self._send_set_mode_command(custom_mode, custom_sub_mode)
                logger.info(
                    "OFFBOARD mode command sent [attempt %d/%d]",
                    attempt, retries,
                )

                if self.wait_command_ack(
                    mavutil.mavlink.MAV_CMD_DO_SET_MODE, timeout=2.0,
                ):
                    logger.info("OFFBOARD mode confirmed by PX4 ✓")
                    return True

                logger.warning("OFFBOARD not confirmed, retrying...")
                self._last_command_time.pop("mode", None)
                time.sleep(0.3)

            logger.error("Failed to enter OFFBOARD after %d attempts", retries)
            self._stop_offboard_keepalive()
            return False

        except Exception as exc:
            logger.error("set_mode_offboard failed: %s", exc)
            self._stop_offboard_keepalive()
            return False

    def _send_offboard_position_hold(self) -> None:
        """Send a single velocity setpoint (0 m/s) to hold current position."""
        self.connection.mav.set_position_target_local_ned_send(
            0,
            self.connection.target_system,
            self.connection.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            0b0000_1111_1100_0111,  # Ignore pos, accel, yaw. Use only velocity (Vx=0, Vy=0, Vz=0).
            0, 0, 0,       # Position (ignored)
            0, 0, 0,       # Velocity (m/s) -> hold
            0, 0, 0,       # Acceleration (ignored)
            0, 0,          # Yaw, yaw_rate (ignored)
        )

    def _start_offboard_keepalive(self) -> None:
        """Start background thread that streams setpoints at 20Hz to keep OFFBOARD alive."""
        if self._offboard_keepalive_running:
            return  # Đã chạy rồi thì giữ nguyên
        
        self._offboard_keepalive_running = True
        self._offboard_keepalive_thread = threading.Thread(
            target=self._offboard_keepalive_loop, daemon=True,
        )
        self._offboard_keepalive_thread.start()
        logger.info("OFFBOARD keepalive thread started")

    def _stop_offboard_keepalive(self) -> None:
        """Stop the OFFBOARD keepalive thread."""
        if self._offboard_keepalive_running:
            self._offboard_keepalive_running = False
            if self._offboard_keepalive_thread and self._offboard_keepalive_thread.is_alive():
                self._offboard_keepalive_thread.join(timeout=1.0)
            self._offboard_keepalive_thread = None
            logger.info("OFFBOARD keepalive thread stopped")

    def _offboard_keepalive_loop(self) -> None:
        """
        Background loop: send position-hold setpoints at 20 Hz (0.05s).
        """
        STARTUP_GRACE_SEC = 3.0   # Bỏ qua kiểm tra flight_mode trong 3s đầu khi vừa bật
        logger.info("OFFBOARD keepalive loop running (grace period %.1f s)", STARTUP_GRACE_SEC)

        t_start = time.time()

        while self._offboard_keepalive_running and self.is_connected:
            try:
                # 1. Luôn bắn gói tin setpoint ngay đầu vòng lặp
                self._send_offboard_position_hold()

                # 2. Sau thời gian Grace period mới kiểm tra xem PX4 có bị ai đổi sang mode khác không
                elapsed = time.time() - t_start
                if elapsed >= STARTUP_GRACE_SEC:
                    if self.telemetry.flight_mode != "OFFBOARD":
                        logger.info(
                            "OFFBOARD keepalive: PX4 mode is %s (not OFFBOARD), stopping thread",
                            self.telemetry.flight_mode,
                        )
                        break

            except Exception as exc:
                logger.error("OFFBOARD keepalive error: %s", exc)
                break

            time.sleep(0.05)  # 20 Hz chuẩn PX4 Offboard

        self._offboard_keepalive_running = False
        logger.info("OFFBOARD keepalive loop exited")

    # ===================================================================
    # Flight commands
    # ===================================================================

    def arm(self) -> bool:
        if not self._can_send("arm"):
            return False
        self.connection.mav.command_long_send(
            self.connection.target_system,
            self.connection.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1, 0, 0, 0, 0, 0, 0,  # param1=1 → ARM
        )
        logger.info("ARM command sent")
        return True

    def disarm(self, force: bool = False) -> bool:
        if not self._can_send("disarm"):
            return False
        self.connection.mav.command_long_send(
            self.connection.target_system,
            self.connection.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            0,                        # param1=0 → DISARM
            21196 if force else 0,     # param2=21196 → force disarm
            0, 0, 0, 0, 0,
        )
        logger.info("DISARM command sent (force=%s)", force)
        return True

    def takeoff(self, altitude_m: float) -> bool:
        if not self._can_send("takeoff"):
            return False
        self.connection.mav.command_long_send(
            self.connection.target_system,
            self.connection.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0,
            0, 0, 0, 0,
            0, 0,
            altitude_m,
        )
        logger.info("TAKEOFF command sent: %.1f m", altitude_m)
        return True

    def goto_location(self, lat: float, lon: float, alt_m: float) -> bool:
        if not self._can_send("goto"):
            return False
        self.connection.mav.set_position_target_global_int_send(
            0,
            self.connection.target_system,
            self.connection.target_component,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            0b0000111111111000,
            int(lat * 1e7),
            int(lon * 1e7),
            alt_m,
            0, 0, 0,
            0, 0, 0,
            0, 0,
        )
        logger.info("GOTO: lat=%.7f lon=%.7f alt=%.1f m", lat, lon, alt_m)
        return True

    def land(self) -> bool:
        if not self._can_send("land"):
            return False
        return self.set_mode("AUTO.LAND")

    def rtl(self) -> bool:
        if not self._can_send("rtl"):
            return False
        return self.set_mode("AUTO.RTL")

    # ===================================================================
    # Precision landing
    # ===================================================================

    def send_landing_target(
        self,
        angle_x: float,
        angle_y: float,
        distance: float,
        size_x: float = 0.15,
        size_y: float = 0.15,
    ) -> None:
        """Send LANDING_TARGET message for ArUco precision landing."""
        if not self.is_connected:
            return
        try:
            self.connection.mav.landing_target_send(
                0,
                0,
                mavutil.mavlink.MAV_FRAME_BODY_FRD,
                0,
                angle_x,
                angle_y,
                distance,
                size_x,
                size_y,
            )
        except Exception as exc:
            logger.error("send_landing_target failed: %s", exc)

    # ===================================================================
    # Navigation helpers
    # ===================================================================

    def distance_to(self, lat: float, lon: float) -> float:
        """Haversine distance in metres from current GPS position."""
        if self.telemetry.gps_fix_type < 3:
            return float("inf")
        lat1 = math.radians(self.telemetry.latitude)
        lon1 = math.radians(self.telemetry.longitude)
        lat2 = math.radians(lat)
        lon2 = math.radians(lon)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        return 6371000 * 2 * math.asin(math.sqrt(a))

    def is_at_location(self, lat: float, lon: float, radius_m: float) -> bool:
        return self.distance_to(lat, lon) <= radius_m

    def is_landed(self) -> bool:
        return (
            not self.telemetry.armed
            and self.telemetry.rangefinder_valid
            and self.telemetry.altitude_agl < 0.15
            and self.telemetry.ground_speed < 0.3
        )

    def move_relative(self, dx: float, dy: float, dz: float) -> bool:
        """
        Move drone relative to current position (in meters).
        Uses SET_POSITION_TARGET_LOCAL_NED.
        """
        if not self._can_send("goto") or not self.connection:
            return False

        self.connection.mav.set_position_target_local_ned_send(
            0, # time_boot_ms
            self.connection.target_system,
            self.connection.target_component,
            mavutil.mavlink.MAV_FRAME_BODY_OFFSET_NED,
            0b110111111000,
            dx, dy, dz,
            0, 0, 0,
            0, 0, 0,
            0, 0
        )
        self._last_command_time["goto"] = time.time()
        logger.info("Move relative: dx=%.1f, dy=%.1f, dz=%.1f", dx, dy, dz)
        return True
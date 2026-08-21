"""
MAVLink controller — Raspberry Pi 5 ↔ Pixhawk 6C (PX4).

Connection: /dev/ttyAMA0 (GPIO UART) hoặc /dev/ttyUSB0 (USB-Serial)
Baudrate:   57600 hoặc 921600 (cấu hình trong .env / config.py)
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
    "arm":     2.0,
    "takeoff": 3.0,
    "goto":    1.0,
    "land":    3.0,
    "rtl":     2.0,
    "mode":    1.0,
    "disarm":  2.0,
}


# ---------------------------------------------------------------------------
# Telemetry dataclass
# ---------------------------------------------------------------------------

@dataclass
class TelemetryData:
    latitude:  float = 0.0
    longitude: float = 0.0

    # Độ cao tương đối mốc cất cánh chuẩn EKF2 (LOCAL_POSITION_NED / ALTITUDE)
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
    """

    def __init__(self):
        self.connection: Optional[mavutil.mavlink_connection] = None
        self.telemetry = TelemetryData()
        self._last_command_time: dict[str, float] = {}
        self._connected = False
        self.connection_uri = config.MAVLINK_DEVICE
        self.use_baud = True
        self._send_lock = threading.Lock()
        self._recv_lock = threading.Lock()
        
        # Async COMMAND_ACK tracking
        self._ack_lock = threading.Lock()
        self._pending_acks: dict[int, threading.Event] = {}
        self._ack_results: dict[int, int] = {}

        # Background MAVLink reader thread (~100Hz)
        self._reader_running = False
        self._reader_thread: Optional[threading.Thread] = None

        # OFFBOARD keepalive
        self._offboard_keepalive_running = False
        self._offboard_keepalive_thread: Optional[threading.Thread] = None

        # OFFBOARD takeoff state
        self._offboard_takeoff_active = False
        self._offboard_takeoff_target_alt = getattr(config, "TAKEOFF_ALTITUDE_M", 1.75)
        self._offboard_takeoff_complete = False

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
                    if src_sys not in (0, 255):
                        self.connection.target_system = src_sys
                        self.connection.target_component = msg.get_srcComponent()
                        break
                    else:
                        logger.debug("Bỏ qua heartbeat từ system=%s", src_sys)
            
            self._connected = True
            self.telemetry.last_update = time.time()

            logger.info(
                "[INFO] PX4 heartbeat received — system=%s component=%s",
                self.connection.target_system,
                self.connection.target_component,
            )
            self.request_data_streams()
            self._start_reader_thread()
            return True

        except Exception as exc:
            logger.error("MAVLink connection failed: %s", exc)
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Close connection and stop all background threads."""
        self._stop_reader_thread()
        self._stop_offboard_keepalive()
        self._connected = False
        if self.connection is not None:
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None
        logger.info("[INFO] MavlinkController disconnected")

    def close(self) -> None:
        self.disconnect()

    def _start_reader_thread(self) -> None:
        """Start high-rate background reader thread to poll MAVLink messages continuously (~100Hz)."""
        if self._reader_running:
            return
        self._reader_running = True
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name="MavlinkReaderThread",
            daemon=True,
        )
        self._reader_thread.start()
        logger.info("[INFO] Background MAVLink reader thread started @ 100Hz")

    def _stop_reader_thread(self) -> None:
        """Stop background reader thread safely."""
        if self._reader_running:
            self._reader_running = False
            if self._reader_thread and self._reader_thread.is_alive():
                self._reader_thread.join(timeout=1.0)
            self._reader_thread = None
            logger.info("[INFO] Background MAVLink reader thread stopped")

    def _reader_loop(self) -> None:
        """High-frequency background reader loop (~100Hz) to ensure zero message lag and instant ACK dispatch."""
        logger.info("[INFO] MavlinkReader loop running")
        while self._reader_running and self._connected and self.connection is not None:
            try:
                self.poll_messages()
            except Exception as exc:
                logger.error("[ERROR] MavlinkReader loop error: %s", exc)
            time.sleep(0.01)  # 100Hz poll rate
        self._reader_running = False

    def request_data_streams(self) -> None:
        """Request PX4 to stream telemetry data at regular rate (10Hz)."""
        if not self.connection:
            return
        try:
            stream_rate = getattr(config, "MAVLINK_STREAM_RATE_HZ", 10)
            with self._send_lock:
                self.connection.mav.request_data_stream_send(
                    self.connection.target_system,
                    self.connection.target_component,
                    mavutil.mavlink.MAV_DATA_STREAM_ALL,
                    stream_rate,
                    1,  # start streaming
                )
            logger.info("[INFO] Requested MAVLink data streams (%dHz)", stream_rate)
        except Exception as exc:
            logger.warning("[WARNING] Failed to request data streams: %s", exc)

    def send_heartbeat(self) -> None:
        """Send companion computer HEARTBEAT to PX4 to maintain connection."""
        if not self.is_connected or self.connection is None:
            return
        try:
            with self._send_lock:
                self.connection.mav.heartbeat_send(
                    mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
                    mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                    0, 0, 0,
                )
        except Exception as exc:
            logger.warning("[WARNING] Failed to send companion heartbeat: %s", exc)

    @property
    def is_connected(self) -> bool:
        if not self._connected or self.connection is None:
            return False
        if time.time() - self.telemetry.last_update > config.MAVLINK_HEARTBEAT_TIMEOUT:
            if self._connected:
                logger.warning(
                    "[WARNING] MAVLink heartbeat timeout (>%ds) — connection lost",
                    config.MAVLINK_HEARTBEAT_TIMEOUT,
                )
                self._connected = False
            return False
        return True

    # ===================================================================
    # MAVLink receive
    # ===================================================================

    def poll_messages(self) -> None:
        """Read all available MAVLink messages (non-blocking)."""
        if not self.is_connected or self.connection is None:
            return

        with self._recv_lock:
            try:
                while True:
                    msg = self.connection.recv_match(blocking=False)
                    if msg is None:
                        break
                    self._process_message(msg)
            except Exception as exc:
                logger.error("[ERROR] MAVLink poll_messages error: %s", exc)

    def _process_message(self, msg) -> None:
        msg_type = msg.get_type()
        self.telemetry.last_update = time.time()

        # ---- GPS position (Chỉ lấy Lat, Lon; không lấy relative_alt của GPS) ----
        if msg_type == "GLOBAL_POSITION_INT":
            self.telemetry.latitude  = msg.lat / 1e7
            self.telemetry.longitude = msg.lon / 1e7

        # ---- Tọa độ EKF2 Cục bộ (Trục Z NED: -z là độ cao thực tế mốc cất cánh) ----
        elif msg_type == "LOCAL_POSITION_NED":
            self.telemetry.altitude_relative = -msg.z

        # ---- Độ cao PX4 EKF2 Tổng hợp ----
        elif msg_type == "ALTITUDE":
            if not math.isnan(msg.altitude_relative):
                self.telemetry.altitude_relative = msg.altitude_relative

        # ---- MTF-02P rangefinder AGL ----
        elif msg_type == "DISTANCE_SENSOR":
            distance_cm = msg.current_distance
            if distance_cm > 0:
                self.telemetry.altitude_agl      = distance_cm / 100.0
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
            if msg.fix_type >= 2 and msg.lat != 0 and msg.lon != 0:
                self.telemetry.latitude  = msg.lat / 1e7
                self.telemetry.longitude = msg.lon / 1e7

        # ---- Flight mode + armed state ----
        elif msg_type == "HEARTBEAT":
            if self.connection and msg.get_srcSystem() != self.connection.target_system:
                return
            if msg.get_srcComponent() not in (1, mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1):
                return

            self.telemetry.armed = bool(
                msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
            )

            main_mode = (msg.custom_mode >> 16) & 0xFF
            sub_mode = (msg.custom_mode >> 24) & 0xFF

            px4_main_modes = {
                1: "MANUAL",
                2: "ALTCTL",
                3: "POSCTL",
                4: "AUTO",
                5: "ACRO",
                6: "OFFBOARD",
                7: "STABILIZED",
                8: "RATTITUDE",
            }
            px4_auto_submodes = {
                1: "READY",
                2: "TAKEOFF",
                3: "LOITER",
                4: "MISSION",
                5: "RTL",
                6: "LAND",
                7: "RTGS",
                8: "FOLLOW",
                9: "PRECLAND",
            }

            if main_mode in px4_main_modes:
                if main_mode == 4 and sub_mode in px4_auto_submodes:
                    mode_str = f"AUTO.{px4_auto_submodes[sub_mode]}"
                else:
                    mode_str = px4_main_modes[main_mode]
            else:
                mode_str = mavutil.mode_string_v10(msg)

            self.telemetry.flight_mode = mode_str

        # ---- PX4 Status Text & Warnings ----
        elif msg_type == "STATUSTEXT":
            text = msg.text
            if isinstance(text, bytes):
                text = text.decode("utf-8", errors="ignore")
            logger.warning("[PX4 STATUSTEXT] %s", text)

        # ---- Command ACK (Xử lý bất đồng bộ không nghẽn luồng) ----
        elif msg_type == "COMMAND_ACK":
            cmd = getattr(msg, "command", None)
            result = getattr(msg, "result", None)
            if cmd is not None and result is not None:
                with self._ack_lock:
                    self._ack_results[cmd] = result
                    if cmd in self._pending_acks:
                        self._pending_acks[cmd].set()

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
        px4_modes = {
            "MANUAL": (1.0, 0.0),
            "ALTCTL": (2.0, 0.0),
            "POSCTL": (3.0, 0.0),
            "AUTO": (4.0, 0.0),
            "MISSION": (4.0, 4.0),
            "AUTO.MISSION": (4.0, 4.0),
            "TAKEOFF": (4.0, 2.0),
            "AUTO.TAKEOFF": (4.0, 2.0),
            "LOITER": (4.0, 3.0),
            "HOLD": (4.0, 3.0),
            "AUTO.LOITER": (4.0, 3.0),
            "AUTO.HOLD": (4.0, 3.0),
            "RTL": (4.0, 5.0),
            "AUTO.RTL": (4.0, 5.0),
            "LAND": (4.0, 6.0),
            "AUTO.LAND": (4.0, 6.0),
            "PRECLAND": (4.0, 9.0),
            "ACRO": (5.0, 0.0),
            "OFFBOARD": (6.0, 0.0),
            "STABILIZED": (7.0, 0.0),
        }
        upper_mode = mode.upper()
        if upper_mode in px4_modes:
            return px4_modes[upper_mode]

        mapping = self.connection.mode_mapping() if self.connection else {}
        mode_id = mapping.get(mode) or mapping.get(upper_mode.replace("AUTO.", ""))
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
        with self._send_lock:
            self.connection.mav.command_long_send(
                self.connection.target_system,
                self.connection.target_component,
                mavutil.mavlink.MAV_CMD_DO_SET_MODE,
                0,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                custom_mode,
                custom_sub_mode,
                0.0, 0.0, 0.0, 0.0,
            )

    def wait_command_ack(self, command_id: int, timeout: float = 3.5) -> bool:
        """Wait for COMMAND_ACK from PX4 asynchronously."""
        ack_event = threading.Event()
        with self._ack_lock:
            self._pending_acks[command_id] = ack_event
            self._ack_results.pop(command_id, None)

        try:
            signaled = ack_event.wait(timeout=timeout)
            if not signaled:
                logger.warning("COMMAND_ACK timeout for cmd=%d", command_id)
                return False

            with self._ack_lock:
                result = self._ack_results.get(command_id)

            if result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                return True
            else:
                logger.warning("COMMAND_ACK rejected: cmd=%d result=%s", command_id, result)
                return False
        finally:
            with self._ack_lock:
                self._pending_acks.pop(command_id, None)

    def set_mode(self, mode: str, retries: int = 3, force_send: bool = False) -> bool:
        """Set PX4 flight mode with ACK verification."""
        if not force_send and not self._can_send("mode"):
            return False
        if force_send:
            self._last_command_time["mode"] = time.time()
        try:
            custom_mode, custom_sub_mode = self._resolve_mode_id(mode)
            if custom_mode is None:
                logger.error("Unknown flight mode: %s", mode)
                return False

            self._stop_offboard_keepalive()

            for attempt in range(1, retries + 1):
                self._send_set_mode_command(custom_mode, custom_sub_mode)
                logger.info(
                    "Mode set → %s (custom_mode=%.0f, sub_mode=%.0f) [attempt %d/%d]",
                    mode, custom_mode, custom_sub_mode, attempt, retries,
                )

                if self.wait_command_ack(mavutil.mavlink.MAV_CMD_DO_SET_MODE, timeout=2.5):
                    logger.info("Mode %s confirmed by PX4", mode)
                    return True

                # Check if telemetry already updated to desired mode
                if mode.upper() in self.telemetry.flight_mode.upper():
                    logger.info("Mode %s confirmed via telemetry update ✓", mode)
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
    # OFFBOARD control & keepalive
    # ===================================================================

    def set_mode_offboard(self, retries: int = 3) -> bool:
        """Switch to OFFBOARD mode safely with streaming setpoints."""
        if not self.is_connected:
            logger.error("set_mode_offboard: not connected")
            return False

        try:
            custom_mode, custom_sub_mode = self._resolve_mode_id("OFFBOARD")
            if custom_mode is None:
                logger.error("OFFBOARD not found in mode_mapping")
                return False

            if self._offboard_keepalive_running and self.telemetry.flight_mode == "OFFBOARD":
                logger.info("PX4 is already in OFFBOARD mode with keepalive running")
                return True

            logger.info("OFFBOARD: Starting continuous setpoint keepalive thread...")
            self._start_offboard_keepalive()
            time.sleep(0.6)

            for attempt in range(1, retries + 1):
                self._send_set_mode_command(custom_mode, custom_sub_mode)
                logger.info("OFFBOARD mode command sent [attempt %d/%d]", attempt, retries)

                if self.wait_command_ack(mavutil.mavlink.MAV_CMD_DO_SET_MODE, timeout=2.5):
                    logger.info("OFFBOARD mode confirmed by PX4 ✓")
                    return True

                if self.telemetry.flight_mode == "OFFBOARD":
                    logger.info("OFFBOARD mode confirmed via telemetry update ✓")
                    return True

                logger.warning("OFFBOARD not confirmed, retrying...")
                self._last_command_time.pop("mode", None)
                time.sleep(0.4)

            logger.error("Failed to enter OFFBOARD after %d attempts", retries)
            if not self._offboard_takeoff_active:
                self._stop_offboard_keepalive()
            return False

        except Exception as exc:
            logger.error("set_mode_offboard failed: %s", exc)
            if not self._offboard_takeoff_active:
                self._stop_offboard_keepalive()
            return False

    def _send_offboard_position_hold(self) -> None:
        """Send Offboard setpoint: velocity 0 m/s to hold current position."""
        if not self.is_connected or self.connection is None:
            return

        with self._send_lock:
            self.connection.mav.set_position_target_local_ned_send(
                0,
                self.connection.target_system,
                self.connection.target_component,
                mavutil.mavlink.MAV_FRAME_LOCAL_NED,
                0b0000_1111_1100_0111,
                0, 0, 0,
                0.0, 0.0, 0.0,
                0, 0, 0,
                0, 0,
            )

    def _send_offboard_takeoff_setpoint(self, target_alt_m: float) -> None:
        """Send Offboard setpoint: climb to target_alt_m (NED: z = -alt)."""
        if not self.is_connected or self.connection is None:
            return

        # Typemask: enable position only (x, y, z)
        # Bits: ignore vx,vy,vz,ax,ay,az,yaw,yaw_rate → 0b0000_1111_1111_1000
        with self._send_lock:
            self.connection.mav.set_position_target_local_ned_send(
                0,
                self.connection.target_system,
                self.connection.target_component,
                mavutil.mavlink.MAV_FRAME_BODY_NED,
                0b0000_1111_1111_1000,
                0.0, 0.0, -target_alt_m,   # Body frame Z=-alt (climb upward)
                0, 0, 0,
                0, 0, 0,
                0, 0,
            )

    def _start_offboard_keepalive(self) -> None:
        self._keepalive_start_time = time.time()
        if self._offboard_keepalive_running:
            return

        self._offboard_keepalive_running = True
        self._offboard_keepalive_thread = threading.Thread(
            target=self._offboard_keepalive_loop, daemon=True,
        )
        self._offboard_keepalive_thread.start()
        logger.info("OFFBOARD keepalive thread started")

    def _stop_offboard_keepalive(self) -> None:
        if self._offboard_keepalive_running:
            self._offboard_keepalive_running = False
            if self._offboard_keepalive_thread and self._offboard_keepalive_thread.is_alive():
                self._offboard_keepalive_thread.join(timeout=1.0)
            self._offboard_keepalive_thread = None
            logger.info("OFFBOARD keepalive thread stopped")

    def _offboard_keepalive_loop(self) -> None:
        STARTUP_GRACE_SEC = 15.0
        logger.info("OFFBOARD keepalive loop running (grace period %.1f s)", STARTUP_GRACE_SEC)

        while self._offboard_keepalive_running and self.is_connected:
            try:
                # ── OFFBOARD Takeoff mode: stream climb setpoint + monitor AGL ──
                if self._offboard_takeoff_active:
                    target_alt = self._offboard_takeoff_target_alt
                    self._send_offboard_takeoff_setpoint(target_alt)

                    # Read current AGL from MTF-02P rangefinder (primary)
                    # Fallback to EKF2 altitude_relative if rangefinder unavailable
                    if self.telemetry.rangefinder_valid and self.telemetry.altitude_agl > 0.05:
                        cur_agl = self.telemetry.altitude_agl
                        alt_source = "MTF-02P"
                    else:
                        cur_agl = self.telemetry.altitude_relative
                        alt_source = "EKF2"

                    threshold = target_alt * 0.92  # 92% of target (e.g. 1.38m for 1.5m)

                    if cur_agl >= threshold:
                        logger.info(
                            "OFFBOARD takeoff: AGL reached %.2fm (threshold=%.2fm, source=%s) "
                            "— stopping keepalive and switching to LOITER",
                            cur_agl, threshold, alt_source,
                        )
                        self._offboard_takeoff_active = False
                        self._offboard_takeoff_complete = True
                        # Stop keepalive BEFORE switching mode to avoid race
                        self._offboard_keepalive_running = False
                        # Switch to LOITER for stable hover
                        self._send_set_mode_command(
                            *self._resolve_mode_id("LOITER")
                        )
                        break
                else:
                    # ── Normal OFFBOARD hold mode ──
                    self._send_offboard_position_hold()

                elapsed = time.time() - getattr(self, "_keepalive_start_time", time.time())
                # Only terminate if NOT in active takeoff sequence and past grace period
                if not self._offboard_takeoff_active and elapsed >= STARTUP_GRACE_SEC:
                    if self.telemetry.flight_mode not in ("OFFBOARD", "LOITER", "HOLD", "UNKNOWN"):
                        logger.info(
                            "OFFBOARD keepalive: PX4 mode is %s, stopping thread",
                            self.telemetry.flight_mode,
                        )
                        break
            except Exception as exc:
                logger.error("OFFBOARD keepalive error: %s", exc)
                break

            time.sleep(0.05)  # 20 Hz

        self._offboard_keepalive_running = False
        logger.info("OFFBOARD keepalive loop exited")

    # ===================================================================
    # Flight commands
    # ===================================================================

    def arm(self, force: bool = False) -> bool:
        if not self._can_send("arm"):
            return False

        if self.telemetry.armed:
            logger.info("ARM: Drone is already armed ✓")
            return True

        with self._send_lock:
            self.connection.mav.command_long_send(
                self.connection.target_system,
                self.connection.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,
                1,
                21196 if force else 0,
                0, 0, 0, 0, 0,
            )
        logger.info("ARM command sent (force=%s)", force)
        ack = self.wait_command_ack(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, timeout=3.5)
        
        # Dual-check: acknowledge via ACK packet OR immediate telemetry status
        if ack or self.telemetry.armed:
            logger.info("ARM command ACCEPTED / CONFIRMED by PX4 ✓ (ack=%s, armed=%s)", ack, self.telemetry.armed)
            return True
        else:
            time.sleep(0.5)
            if self.telemetry.armed:
                logger.info("ARM confirmed via late telemetry update ✓")
                return True
            logger.warning("ARM command REJECTED/TIMEOUT by PX4 ❌")
            return False

    def disarm(self, force: bool = False) -> bool:
        if not self._can_send("disarm"):
            return False
        with self._send_lock:
            self.connection.mav.command_long_send(
                self.connection.target_system,
                self.connection.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,
                0,
                21196 if force else 0,
                0, 0, 0, 0, 0,
            )
        logger.info("DISARM command sent (force=%s)", force)
        return True

    def takeoff_nav_cmd(self, altitude_m: float = 1.75) -> bool:
        """
        Native PX4 Takeoff using MAV_CMD_NAV_TAKEOFF (cmd=22) or AUTO.TAKEOFF.
        Safe, reliable, handles motor spool-up, climb, and auto-transition to LOITER/HOLD.
        """
        if not self._can_send("takeoff") or not self.connection:
            return False

        logger.info("Sending MAV_CMD_NAV_TAKEOFF (cmd=22) to altitude %.2fm...", altitude_m)
        with self._send_lock:
            self.connection.mav.command_long_send(
                self.connection.target_system,
                self.connection.target_component,
                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                0,
                0.0, 0.0, 0.0,
                float("nan"),  # yaw
                float("nan"), float("nan"),  # lat, lon (current position)
                float(altitude_m),  # target altitude
            )
        ack = self.wait_command_ack(mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, timeout=3.5)
        if ack:
            logger.info("MAV_CMD_NAV_TAKEOFF accepted by PX4 ✓")
            return True

        logger.warning("MAV_CMD_NAV_TAKEOFF unconfirmed, attempting mode transition to TAKEOFF...")
        return self.set_mode("TAKEOFF", force_send=True)

    def takeoff_offboard(self, altitude_m: float = 1.75) -> bool:
        """
        OFFBOARD takeoff: stream position setpoint Z=-altitude_m to PX4.
        """
        if not self._can_send("takeoff"):
            return False
        if not self.is_connected:
            logger.error("takeoff_offboard: not connected")
            return False

        logger.info(
            "Initiating OFFBOARD takeoff to %.2fm (setpoint Z=%.2fm NED)...",
            altitude_m, -altitude_m,
        )

        # Reset takeoff state
        self._offboard_takeoff_target_alt = altitude_m
        self._offboard_takeoff_active = True
        self._offboard_takeoff_complete = False

        # Enter OFFBOARD mode (starts keepalive thread internally)
        ok = self.set_mode_offboard()
        if not ok:
            logger.error("Failed to enter OFFBOARD mode for takeoff")
            self._offboard_takeoff_active = False
            return False

        logger.info("OFFBOARD takeoff streaming active — monitoring AGL for %.2fm threshold",
                    altitude_m * 0.92)
        return True

    def takeoff(self, altitude_m: float = 1.75) -> bool:
        """
        Robust Multi-Tier Takeoff Pipeline:
        1. First try native PX4 MAV_CMD_NAV_TAKEOFF / AUTO.TAKEOFF (PX4 native auto takeoff).
        2. If unconfirmed, seamlessly fallback to OFFBOARD takeoff streaming.
        """
        logger.info("Initiating UAV Takeoff pipeline to %.2fm...", altitude_m)
        ok = self.takeoff_nav_cmd(altitude_m)
        if ok:
            return True

        logger.warning("Native TAKEOFF unconfirmed, falling back to OFFBOARD Takeoff...")
        return self.takeoff_offboard(altitude_m)

    def goto_location(self, lat: float, lon: float, alt_m: float = 1.75) -> bool:
        """
        Bay vị trí GPS ở mode LOITER/HOLD chuẩn xác bằng MAV_CMD_DO_REPOSITION.
        """
        if not self._can_send("goto") or not self.connection:
            return False

        # Đảm bảo drone đang ở LOITER để nhận lệnh DO_REPOSITION
        if self.telemetry.flight_mode not in ("LOITER", "HOLD", "AUTO.LOITER", "AUTO.HOLD"):
            logger.info("Chuyển mode sang LOITER trước khi gửi lệnh DO_REPOSITION...")
            self.set_mode("LOITER", force_send=True)
            time.sleep(0.2)

        with self._send_lock:
            self.connection.mav.command_long_send(
                self.connection.target_system,
                self.connection.target_component,
                mavutil.mavlink.MAV_CMD_DO_REPOSITION,
                0,
                -1.0,                             # param1: ground speed (-1 = mặc định PX4)
                mavutil.mavlink.MAV_DO_REPOSITION_FLAGS_CHANGE_MODE,  # param2: cờ đổi sang LOITER reposition
                0.0,                              # param3: reserved
                float("nan"),                     # param4: yaw angle (NaN = giữ nguyên hướng hiện tại)
                float(lat),                       # param5: latitude (deg)
                float(lon),                       # param6: longitude (deg)
                float(alt_m),                     # param7: altitude relative to home (m)
            )
        logger.info("GOTO (DO_REPOSITION): lat=%.7f lon=%.7f alt=%.1f m", lat, lon, alt_m)
        return True

    def land(self) -> bool:
        if not self._can_send("land"):
            return False
        return self.set_mode("LAND")

    def rtl(self) -> bool:
        if not self._can_send("rtl"):
            return False
        return self.set_mode("RTL")

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
        if not self.is_connected or self.connection is None:
            return
        try:
            with self._send_lock:
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

    def is_at_location(self, lat: float, lon: float, radius_m: float = 1.0) -> bool:
        return self.distance_to(lat, lon) <= radius_m

    def is_landed(self) -> bool:
        """Kiểm tra drone đã tiếp đất an toàn chưa (tránh deadlock armed state)."""
        # Nếu tốc độ di chuyển còn lớn -> Chưa tiếp đất
        if self.telemetry.ground_speed > 0.3:
            return False

        # Ưu tiên kiểm tra độ cao Laser MTF-02P
        if self.telemetry.rangefinder_valid:
            return self.telemetry.altitude_agl < 0.28

        # Fallback theo EKF2 Relative Altitude
        return abs(self.telemetry.altitude_relative) < 0.3

    def move_relative(self, dx: float, dy: float, dz: float) -> bool:
        """
        Move drone relative to current position (in meters).
        Uses SET_POSITION_TARGET_LOCAL_NED.
        """
        if not self._can_send("goto") or not self.connection:
            return False

        with self._send_lock:
            self.connection.mav.set_position_target_local_ned_send(
                0,
                self.connection.target_system,
                self.connection.target_component,
                mavutil.mavlink.MAV_FRAME_BODY_OFFSET_NED,
                0b110111111000,
                dx, dy, dz,
                0, 0, 0,
                0, 0, 0,
                0, 0,
            )
        self._last_command_time["goto"] = time.time()
        logger.info("Move relative: dx=%.1f, dy=%.1f, dz=%.1f", dx, dy, dz)
        return True
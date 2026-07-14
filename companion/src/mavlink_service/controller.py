# import logging
# import math
# import time
# from dataclasses import dataclass, field
# from typing import Optional

# from pymavlink import mavutil

# import config

# logger = logging.getLogger(__name__)

# # Rate limiting: minimum interval between duplicate command types (seconds)
# COMMAND_COOLDOWN = {
#     "arm": 2.0,
#     "takeoff": 3.0,
#     "goto": 2.0,
#     "land": 3.0,
#     "rtl": 2.0,
#     "mode": 1.0,
#     "disarm": 2.0,
# }


# @dataclass
# class TelemetryData:
#     latitude: float = 0.0
#     longitude: float = 0.0
#     altitude_relative: float = 0.0
#     altitude_agl: float = 0.0
#     ground_speed: float = 0.0
#     heading: float = 0.0
#     battery: float = 100.0
#     gps_satellite: int = 0
#     gps_fix_type: int = 0
#     flight_mode: str = "UNKNOWN"
#     armed: bool = False
#     roll: float = 0.0
#     pitch: float = 0.0
#     yaw: float = 0.0
#     last_update: float = field(default_factory=time.time)


# class MavlinkController:
#     """MAVLink interface to PX4 on Pixhawk 6C or PX4 SITL."""

#     def __init__(self):
#         self.connection: Optional[mavutil.mavlink_connection] = None
#         self.telemetry = TelemetryData()
#         self._last_command_time: dict[str, float] = {}
#         self._connected = False
#         self.connection_uri: str = getattr(config, "MAVLINK_DEVICE", "/dev/ttyAMA0")
#         self.use_baud: bool = True

#     def connect(self) -> bool:
#         try:
#             if self.use_baud:
#                 self.connection = mavutil.mavlink_connection(
#                     self.connection_uri,
#                     baud=config.MAVLINK_BAUD,
#                 )
#             else:
#                 self.connection = mavutil.mavlink_connection(self.connection_uri)
#             logger.info("Waiting for heartbeat from PX4...")
#             self.connection.wait_heartbeat(timeout=30)
#             self._connected = True
#             logger.info(
#                 "MAVLink connected. System %s, Component %s",
#                 self.connection.target_system,
#                 self.connection.target_component,
#             )
#             return True
#         except Exception as exc:
#             logger.error("MAVLink connection failed: %s", exc)
#             self._connected = False
#             return False

#     @property
#     def is_connected(self) -> bool:
#         return self._connected and self.connection is not None

#     def _can_send(self, cmd_type: str) -> bool:
#         now = time.time()
#         last = self._last_command_time.get(cmd_type, 0)
#         cooldown = COMMAND_COOLDOWN.get(cmd_type, 1.0)
#         if now - last < cooldown:
#             logger.debug("Command %s throttled (cooldown)", cmd_type)
#             return False
#         self._last_command_time[cmd_type] = now
#         return True

#     def poll_messages(self) -> None:
#         """Read MAVLink messages at ~20Hz. Call in main loop."""
#         if not self.is_connected:
#             return

#         poll_interval = 1.0 / config.MAVLINK_POLL_RATE_HZ
#         deadline = time.time() + poll_interval

#         while time.time() < deadline:
#             msg = self.connection.recv_match(blocking=False)
#             if msg is None:
#                 time.sleep(0.001)
#                 continue
#             self._process_message(msg)

#     def _process_message(self, msg) -> None:
#         msg_type = msg.get_type()

#         if msg_type == "GLOBAL_POSITION_INT":
#             self.telemetry.latitude = msg.lat / 1e7
#             self.telemetry.longitude = msg.lon / 1e7
#             self.telemetry.altitude_relative = msg.relative_alt / 1000.0
#             self.telemetry.last_update = time.time()

#         elif msg_type == "VFR_HUD":
#             self.telemetry.ground_speed = msg.groundspeed
#             self.telemetry.heading = msg.heading

#         elif msg_type == "SYS_STATUS":
#             if msg.battery_remaining >= 0:
#                 self.telemetry.battery = float(msg.battery_remaining)

#         elif msg_type == "ATTITUDE":
#             self.telemetry.roll = math.degrees(msg.roll)
#             self.telemetry.pitch = math.degrees(msg.pitch)
#             self.telemetry.yaw = math.degrees(msg.yaw)

#         elif msg_type == "GPS_RAW_INT":
#             self.telemetry.gps_satellite = msg.satellites_visible
#             self.telemetry.gps_fix_type = msg.fix_type

#         elif msg_type == "HEARTBEAT":
#             self.telemetry.armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
#             self.telemetry.flight_mode = mavutil.mode_string_v10(msg)

#     def set_mode(self, mode: str) -> bool:
#         if not self._can_send("mode"):
#             return False
#         try:
#             mode_id = self.connection.mode_mapping().get(mode)
#             if mode_id is None:
#                 logger.error("Unknown flight mode: %s", mode)
#                 return False
#             self.connection.set_mode(mode_id)
#             logger.info("Mode set to %s", mode)
#             return True
#         except Exception as exc:
#             logger.error("set_mode failed: %s", exc)
#             return False

#     def arm(self) -> bool:
#         if not self._can_send("arm"):
#             return False
#         try:
#             self.connection.arducopter_arm()
#             logger.info("Arm command sent")
#             return True
#         except Exception as exc:
#             logger.error("arm failed: %s", exc)
#             return False

#     def disarm(self) -> bool:
#         if not self._can_send("disarm"):
#             return False
#         try:
#             self.connection.arducopter_disarm()
#             logger.info("Disarm command sent")
#             return True
#         except Exception as exc:
#             logger.error("disarm failed: %s", exc)
#             return False

#     def takeoff(self, altitude_m: float) -> bool:
#         if not self._can_send("takeoff"):
#             return False
#         try:
#             self.connection.mav.command_long_send(
#                 config.MAVLINK_TARGET_SYSTEM,
#                 config.MAVLINK_TARGET_COMPONENT,
#                 mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
#                 0,
#                 0, 0, 0, 0,
#                 0, 0,
#                 altitude_m,
#             )
#             logger.info("Takeoff command sent: %.1f m", altitude_m)
#             return True
#         except Exception as exc:
#             logger.error("takeoff failed: %s", exc)
#             return False

#     def goto_location(self, lat: float, lon: float, alt_m: float) -> bool:
#         if not self._can_send("goto"):
#             return False
#         try:
#             self.connection.mav.set_position_target_global_int_send(
#                 0,
#                 config.MAVLINK_TARGET_SYSTEM,
#                 config.MAVLINK_TARGET_COMPONENT,
#                 mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
#                 0b0000111111111000,
#                 int(lat * 1e7),
#                 int(lon * 1e7),
#                 alt_m,
#                 0, 0, 0,
#                 0, 0, 0,
#                 0, 0,
#             )
#             logger.info("Goto: lat=%.7f lon=%.7f alt=%.1f", lat, lon, alt_m)
#             return True
#         except Exception as exc:
#             logger.error("goto failed: %s", exc)
#             return False

#     def land(self) -> bool:
#         if not self._can_send("land"):
#             return False
#         try:
#             self.set_mode("AUTO.LAND")
#             logger.info("Land command sent")
#             return True
#         except Exception as exc:
#             logger.error("land failed: %s", exc)
#             return False

#     def rtl(self) -> bool:
#         if not self._can_send("rtl"):
#             return False
#         try:
#             self.set_mode("AUTO.RTL")
#             logger.info("RTL command sent")
#             return True
#         except Exception as exc:
#             logger.error("rtl failed: %s", exc)
#             return False

#     def send_landing_target(
#         self,
#         angle_x: float,
#         angle_y: float,
#         distance: float,
#         size_x: float = 0.15,
#         size_y: float = 0.15,
#     ) -> None:
#         """Send LANDING_TARGET message for precision landing."""
#         if not self.is_connected:
#             return
#         try:
#             self.connection.mav.landing_target_send(
#                 0,
#                 0,
#                 mavutil.mavlink.MAV_FRAME_BODY_FRD,
#                 0,
#                 angle_x,
#                 angle_y,
#                 distance,
#                 size_x,
#                 size_y,
#             )
#         except Exception as exc:
#             logger.error("landing_target send failed: %s", exc)

#     def distance_to(self, lat: float, lon: float) -> float:
#         """Haversine distance in meters."""
#         lat1, lon1 = math.radians(self.telemetry.latitude), math.radians(self.telemetry.longitude)
#         lat2, lon2 = math.radians(lat), math.radians(lon)
#         dlat = lat2 - lat1
#         dlon = lon2 - lon1
#         a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
#         return 6371000 * 2 * math.asin(math.sqrt(a))

#     def is_at_location(self, lat: float, lon: float, radius_m: float) -> bool:
#         return self.distance_to(lat, lon) <= radius_m

#     def is_landed(self) -> bool:
#         return (
#             not self.telemetry.armed
#             and self.telemetry.altitude_relative < 0.5
#             and self.telemetry.ground_speed < 0.3
#         )

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Optional

from pymavlink import mavutil

import config

logger = logging.getLogger(__name__)


COMMAND_COOLDOWN = {
    "arm": 2.0,
    "takeoff": 3.0,
    "goto": 2.0,
    "land": 3.0,
    "rtl": 2.0,
    "mode": 1.0,
    "disarm": 2.0,
}


@dataclass
class TelemetryData:

    latitude: float = 0.0
    longitude: float = 0.0

    # PX4 HOME relative altitude
    altitude_relative: float = 0.0

    # MTF-02P ground distance
    altitude_agl: float = 0.0
    rangefinder_valid: bool = False

    ground_speed: float = 0.0
    heading: float = 0.0

    battery: float = 100.0

    gps_satellite: int = 0
    gps_fix_type: int = 0

    flight_mode: str = "UNKNOWN"

    armed: bool = False

    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0

    last_update: float = field(
        default_factory=time.time
    )



class MavlinkController:
    """
    MAVLink interface for PX4
    Pixhawk 6C + MTF-02P
    """


    def __init__(self):

        self.connection: Optional[
            mavutil.mavlink_connection
        ] = None


        self.telemetry = TelemetryData()


        self._last_command_time: dict[
            str,
            float
        ] = {}


        self._connected = False


        self.connection_uri = getattr(
            config,
            "MAVLINK_DEVICE",
            "/dev/ttyAMA0"
        )


        self.use_baud = True



    # ===============================
    # Connection
    # ===============================


    def connect(self) -> bool:

        try:

            if self.use_baud:

                self.connection = (
                    mavutil.mavlink_connection(
                        self.connection_uri,
                        baud=config.MAVLINK_BAUD
                    )
                )

            else:

                self.connection = (
                    mavutil.mavlink_connection(
                        self.connection_uri
                    )
                )


            logger.info(
                "Waiting for heartbeat from PX4..."
            )


            self.connection.wait_heartbeat(
                timeout=30
            )


            self._connected = True


            logger.info(
                "MAVLink connected. System %s Component %s",
                self.connection.target_system,
                self.connection.target_component,
            )


            return True


        except Exception as exc:

            logger.error(
                "MAVLink connection failed: %s",
                exc
            )

            self._connected = False

            return False



    @property
    def is_connected(self):

        return (
            self._connected
            and self.connection is not None
        )



    # ===============================
    # MAVLink Receive
    # ===============================


    def poll_messages(self):

        """
        Read all available MAVLink messages.
        """

        if not self.is_connected:
            return


        while True:

            msg = (
                self.connection.recv_match(
                    blocking=False
                )
            )


            if msg is None:
                break


            self._process_message(msg)




    def _process_message(self, msg):

        msg_type = msg.get_type()


        self.telemetry.last_update = (
            time.time()
        )


        # -----------------------------
        # GPS POSITION
        # -----------------------------

        if msg_type == "GLOBAL_POSITION_INT":


            self.telemetry.latitude = (
                msg.lat / 1e7
            )


            self.telemetry.longitude = (
                msg.lon / 1e7
            )


            self.telemetry.altitude_relative = (
                msg.relative_alt / 1000.0
            )



        # -----------------------------
        # MTF-02P RANGEFINDER
        # -----------------------------

        elif msg_type == "DISTANCE_SENSOR":


            distance_cm = (
                msg.current_distance
            )


            if distance_cm > 0:


                self.telemetry.altitude_agl = (
                    distance_cm / 100.0
                )


                self.telemetry.rangefinder_valid = True



                logger.debug(
                    "MTF-02P AGL %.2fm",
                    self.telemetry.altitude_agl
                )



        # -----------------------------
        # SPEED / HEADING
        # -----------------------------

        elif msg_type == "VFR_HUD":


            self.telemetry.ground_speed = (
                msg.groundspeed
            )


            self.telemetry.heading = (
                msg.heading
            )



        # -----------------------------
        # BATTERY
        # -----------------------------

        elif msg_type == "SYS_STATUS":


            if msg.battery_remaining >= 0:

                self.telemetry.battery = (
                    float(
                        msg.battery_remaining
                    )
                )



        # -----------------------------
        # ATTITUDE
        # -----------------------------

        elif msg_type == "ATTITUDE":


            self.telemetry.roll = (
                math.degrees(msg.roll)
            )


            self.telemetry.pitch = (
                math.degrees(msg.pitch)
            )


            self.telemetry.yaw = (
                math.degrees(msg.yaw)
            )



        # -----------------------------
        # GPS STATUS
        # -----------------------------

        elif msg_type == "GPS_RAW_INT":


            self.telemetry.gps_satellite = (
                msg.satellites_visible
            )


            self.telemetry.gps_fix_type = (
                msg.fix_type
            )



        # -----------------------------
        # MODE + ARM
        # -----------------------------

        elif msg_type == "HEARTBEAT":


            self.telemetry.armed = bool(

                msg.base_mode
                &
                mavutil.mavlink
                .MAV_MODE_FLAG_SAFETY_ARMED

            )


            self.telemetry.flight_mode = (
                mavutil.mode_string_v10(msg)
            )



    # ===============================
    # Command control
    # ===============================


    def _can_send(self, cmd_type):

        now = time.time()


        last = (
            self._last_command_time
            .get(cmd_type,0)
        )


        cooldown = (
            COMMAND_COOLDOWN
            .get(cmd_type,1)
        )


        if now-last < cooldown:

            return False


        self._last_command_time[
            cmd_type
        ] = now


        return True



    def set_mode(self, mode):

        if not self._can_send("mode"):
            return False


        try:

            mode_id = (
                self.connection
                .mode_mapping()
                .get(mode)
            )


            if mode_id is None:

                logger.error(
                    "Unknown mode %s",
                    mode
                )

                return False



            self.connection.set_mode(
                mode_id
            )


            logger.info(
                "Mode set %s",
                mode
            )


            return True


        except Exception as exc:

            logger.error(
                "set_mode failed %s",
                exc
            )

            return False



    def arm(self):

        if not self._can_send("arm"):
            return False


        self.connection.arducopter_arm()

        logger.info(
            "Arm command sent"
        )

        return True



    def disarm(self):

        if not self._can_send("disarm"):
            return False


        self.connection.arducopter_disarm()

        logger.info(
            "Disarm command sent"
        )

        return True



    def takeoff(self, altitude_m):

        if not self._can_send("takeoff"):
            return False


        self.connection.mav.command_long_send(

            config.MAVLINK_TARGET_SYSTEM,

            config.MAVLINK_TARGET_COMPONENT,

            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,

            0,

            0,0,0,0,

            0,0,

            altitude_m
        )


        logger.info(
            "Takeoff %.1fm",
            altitude_m
        )


        return True



    def land(self):

        if not self._can_send("land"):
            return False


        return self.set_mode(
            "AUTO.LAND"
        )



    def rtl(self):

        if not self._can_send("rtl"):
            return False


        return self.set_mode(
            "AUTO.RTL"
        )



    # ===============================
    # Precision Landing
    # ===============================


    def send_landing_target(
        self,
        angle_x,
        angle_y,
        distance,
        size_x=0.15,
        size_y=0.15
    ):


        if not self.is_connected:
            return


        self.connection.mav.landing_target_send(

            0,

            0,

            mavutil.mavlink
            .MAV_FRAME_BODY_FRD,

            0,

            angle_x,

            angle_y,

            distance,

            size_x,

            size_y

        )



    # ===============================
    # Navigation helpers
    # ===============================


    def distance_to(self, lat, lon):

        if self.telemetry.gps_fix_type < 3:

            return float("inf")


        lat1 = math.radians(
            self.telemetry.latitude
        )

        lon1 = math.radians(
            self.telemetry.longitude
        )


        lat2 = math.radians(lat)

        lon2 = math.radians(lon)


        dlat = lat2-lat1

        dlon = lon2-lon1


        a = (
            math.sin(dlat/2)**2
            +
            math.cos(lat1)
            *
            math.cos(lat2)
            *
            math.sin(dlon/2)**2
        )


        return (
            6371000
            *
            2
            *
            math.asin(
                math.sqrt(a)
            )
        )



    def is_at_location(
        self,
        lat,
        lon,
        radius_m
    ):

        return (
            self.distance_to(
                lat,
                lon
            )
            <= radius_m
        )



    def is_landed(self):

        return (

            not self.telemetry.armed

            and

            self.telemetry.rangefinder_valid

            and

            self.telemetry.altitude_agl < 0.15

            and

            self.telemetry.ground_speed < 0.3

        )
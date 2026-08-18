"""
MissionManager — orchestrates the full delivery FSM.

Design principles:
  - All mission logic lives HERE (not on the backend).
  - Backend is pure relay (telemetry → clients, commands → Pi).
  - PX4 auto-disarms after every landing; we wait for armed=False before
    transitioning out of PRECISION_LANDING / RETURN_HOME.
  - ARM command is sent EXACTLY ONCE per phase; we wait for armed=True
    confirmation from the heartbeat before transitioning to TAKEOFF.
  - User confirm gates (WAIT_PICKUP_CONFIRM, WAIT_DROP_CONFIRM) have no
    automatic timeout — they wait indefinitely for an operator command.
  - FORCE_RTL is always accepted and immediately overrides the FSM.

Mission phases (landing_phase internal flag):
  "pickup"        → ARM → TAKEOFF → FLY_TO_PICKUP → DESCEND → SEARCH → LAND
  "enroute_drop"  → ARM → TAKEOFF → FLY_TO_DROP
  "drop"          → DESCEND → SEARCH → LAND
  "rtl"           → ARM → TAKEOFF → RETURN_HOME
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

import config
from src.mavlink_service.controller import MavlinkController
from src.network_service.websocket_client import WebSocketClient
from src.state_machine.machine import StateMachine
from src.state_machine.states import DroneState
from src.vision_service.aruco_landing import ArucoLandingService
from src.vision_service.camera_service import CameraService

logger = logging.getLogger(__name__)

# How long to wait for ARM confirmation before giving up
ARM_TIMEOUT_SEC = 30.0
# How long to wait for TAKEOFF altitude before giving up
TAKEOFF_TIMEOUT_SEC = 30.0
# Enroute & Descend timeouts
FLY_TO_PICKUP_TIMEOUT_SEC = 120.0
FLY_TO_DROP_TIMEOUT_SEC = 120.0
DESCEND_TIMEOUT_SEC = 60.0
# ArUco search timeout
ARUCO_SEARCH_TIMEOUT_SEC = config.LANDING_SEARCH_TIMEOUT_SEC


@dataclass
class MissionLocations:
    home_lat: float = 0.0
    home_lon: float = 0.0
    pickup_lat: float = 0.0
    pickup_lon: float = 0.0
    drop_lat: float = 0.0
    drop_lon: float = 0.0


class MissionManager:
    """Orchestrates the full delivery mission state machine."""

    def __init__(
        self,
        mavlink: MavlinkController,
        vision: ArucoLandingService,
        ws_client: WebSocketClient,
    ):
        self.mavlink = mavlink
        self.vision = vision
        self.ws = ws_client
        self.state_machine = StateMachine(on_transition=self._on_state_transition)
        self.locations = MissionLocations()
        self._mission_active = False
        self._force_rtl = False
        self._stop_requested = False
        self._landing_status = "NONE"
        self._aruco_detected = False
        self._state_enter_time = time.time()
        self._goto_sent = False

        # landing_phase controls which destination we fly to after ARM/TAKEOFF
        #   "pickup"       → go to pickup location
        #   "enroute_drop" → go to drop location
        #   "drop"         → descend/search at drop (set when entering DESCEND from FLY_TO_DROP)
        #   "rtl"          → execute RTL / RETURN_HOME
        self._landing_phase = "pickup"

        # ARM safety: send command only once per ARMING entry
        self._arm_sent = False

        # Camera test service — controlled from frontend (uses shared vision_service)
        self._camera_service = CameraService(
            on_camera_status=self._on_camera_status_sync,
            on_aruco_detection=self._on_aruco_detection_sync,
            vision_service=self.vision,
        )
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None

        # Threading/Timer support for high-rate MAVLink landing target publisher
        self._landing_target_thread_running = True
        self._landing_target_thread = threading.Thread(target=self._run_landing_target_publisher, daemon=True)
        self._landing_target_thread.start()

    # -----------------------------------------------------------------------
    # Command handler (called from WebSocket receive loop)
    # -----------------------------------------------------------------------

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Store event loop reference for scheduling async callbacks from threads."""
        self._event_loop = loop

    def handle_command(self, payload: dict) -> None:
        action = payload.get("action", "")
        logger.info("Received command: %s", action)

        if action == "PICKUP_COMPLETE":
            self._handle_pickup_complete()

        elif action == "DROP_COMPLETE":
            self._handle_drop_complete()

        elif action == "FORCE_RTL":
            self._handle_force_rtl()

        elif action == "STOP":
            self._handle_stop()

        elif action == "CAMERA_START":
            self._handle_camera_start()

        elif action == "CAMERA_STOP":
            self._handle_camera_stop()
            
        elif action == "SET_MODE":
            self._handle_set_mode(payload)

        elif action == "ARM":
            self._handle_arm()

        elif action == "DISARM":
            self._handle_disarm(payload)

        elif action == "STEP_COMMAND":
            self._handle_step_command(payload)

    def _handle_step_command(self, payload: dict) -> None:
        """Handle individual manual step commands (Step-by-Step Flight Pipeline)."""
        step = payload.get("step_action", "")
        logger.info("Executing manual step command: %s", step)

        # Any manual step command IMMEDIATELY disables automatic mission loop
        self._mission_active = False

        if step == "RESET_IDLE":
            self.state_machine.reset()
            logger.info("FSM state manually reset to IDLE")

        elif step == "ARM":
            self._handle_arm()

        elif step == "DISARM":
            self._handle_disarm(payload)

        elif step == "TAKEOFF":
            if not self.mavlink.telemetry.armed:
                logger.warning("STEP TAKEOFF rejected: drone is DISARMED. Arm first.")
                return
            alt = payload.get("alt", config.TAKEOFF_ALTITUDE_M)
            logger.info("STEP TAKEOFF to %.1fm via PX4 TAKEOFF mode", alt)
            self.mavlink._target_takeoff_alt = alt
            self.mavlink.takeoff(alt)
            self.state_machine.force_state(DroneState.TAKEOFF)

        elif step == "NAV_GPS":
            if not self.mavlink.telemetry.armed:
                logger.warning("STEP NAV_GPS rejected: drone is DISARMED.")
                return
            lat = payload.get("lat")
            lon = payload.get("lon")
            alt = payload.get("alt", config.TAKEOFF_ALTITUDE_M)
            target_lat = lat or (self.locations.pickup_lat if self.locations.pickup_lat != 0.0 else self.mavlink.telemetry.latitude)
            target_lon = lon or (self.locations.pickup_lon if self.locations.pickup_lon != 0.0 else self.mavlink.telemetry.longitude)
            
            if not target_lat or not target_lon or target_lat == 0.0 or target_lon == 0.0:
                logger.error("STEP NAV_GPS rejected: invalid coordinates (lat=%.6f, lon=%.6f)", target_lat or 0.0, target_lon or 0.0)
                return

            self.locations.pickup_lat = target_lat
            self.locations.pickup_lon = target_lon

            logger.info("STEP NAV_GPS to lat=%.6f, lon=%.6f, alt=%.1fm", target_lat, target_lon, alt)
            if self.mavlink.telemetry.flight_mode not in ("LOITER", "HOLD", "AUTO.LOITER"):
                self.mavlink.set_mode("LOITER")
            self.mavlink.goto_location(target_lat, target_lon, alt)
            self.state_machine.force_state(DroneState.FLY_TO_PICKUP)

        elif step == "DESCEND":
            if not self.mavlink.telemetry.armed:
                logger.warning("STEP DESCEND rejected: drone is DISARMED.")
                return
            search_alt = payload.get("alt", config.DESCEND_ALTITUDE_M)
            cur_lat = self.mavlink.telemetry.latitude or payload.get("lat", 0.0)
            cur_lon = self.mavlink.telemetry.longitude or payload.get("lon", 0.0)
            if not cur_lat or not cur_lon or cur_lat == 0.0 or cur_lon == 0.0:
                logger.error("STEP DESCEND rejected: no valid position fix")
                return
            logger.info("STEP DESCEND to search altitude %.1fm at lat=%.6f, lon=%.6f", search_alt, cur_lat, cur_lon)
            self.mavlink.goto_location(cur_lat, cur_lon, search_alt)
            self.state_machine.force_state(DroneState.DESCEND)

        elif step == "SEARCH_ARUCO":
            logger.info("STEP SEARCH_ARUCO initiated")
            self._handle_camera_start()
            self.state_machine.force_state(DroneState.SEARCH_ARUCO)

        elif step == "PRECISION_LANDING":
            logger.info("STEP PRECISION_LANDING initiated")
            self._handle_camera_start()
            self.state_machine.force_state(DroneState.PRECISION_LANDING)

        elif step == "NORMAL_LANDING":
            logger.info("STEP NORMAL_LANDING (Auto Land) initiated")
            self.mavlink.land()

    def _handle_set_mode(self, payload: dict) -> None:
        mode = payload.get("mode")
        if not mode:
            return
        # Manual mode selection cancels active automated mission to prevent control race conditions
        self._mission_active = False
        logger.info("Setting flight mode to: %s (manual override)", mode)
        if mode == "TAKEOFF":
            if not self.mavlink.telemetry.armed:
                logger.warning(
                    "Manual TAKEOFF requested while DISARMED. "
                    "Arm the drone first."
                )
                return
            logger.info("Manual TAKEOFF command initiated (altitude=%.1fm)", config.TAKEOFF_ALTITUDE_M)
            self.mavlink.takeoff(config.TAKEOFF_ALTITUDE_M)
            self.state_machine.force_state(DroneState.TAKEOFF)
        elif mode == "OFFBOARD":
            if not self.mavlink.telemetry.armed:
                logger.warning(
                    "Manual OFFBOARD requested while DISARMED. "
                    "PX4 will not maintain OFFBOARD without armed motors. "
                    "Arm the drone first."
                )
            self.mavlink.set_mode_offboard()
        else:
            self.mavlink.set_mode(mode)
            
    def _handle_arm(self) -> None:
        """Manual ARM command from dashboard (outside mission FSM)."""
        # Manual ARM cancels active automated mission to prevent control race conditions
        self._mission_active = False
        if self.state_machine.state != DroneState.IDLE:
            logger.warning(
                "Manual ARM warning: drone is in state %s (resetting to IDLE for manual operation)",
                self.state_machine.state.name,
            )
            self.state_machine.reset()
        if self.mavlink.telemetry.armed:
            logger.warning("Manual ARM rejected: already armed")
            return
        logger.info("Manual ARM command sent")
        self.mavlink.arm()

    def _handle_disarm(self, payload: dict) -> None:
        """Manual DISARM command from dashboard."""
        force = payload.get("force", False)
        if self.state_machine.is_flying() and not force:
            logger.warning(
                "Manual DISARM rejected: drone is flying (state=%s). Use force=True to override.",
                self.state_machine.state.name,
            )
            return
        self._mission_active = False
        logger.info("Manual DISARM command sent (force=%s)", force)
        self.mavlink.disarm(force=force)

    def _handle_pickup_complete(self) -> None:
        if self.state_machine.state != DroneState.WAIT_PICKUP_CONFIRM:
            logger.warning(
                "PICKUP_COMPLETE ignored: not in WAIT_PICKUP_CONFIRM (current: %s)",
                self.state_machine.state.name,
            )
            return
        logger.info("PICKUP_COMPLETE received — arming for drop phase")
        self._landing_phase = "enroute_drop"
        self._aruco_detected = False
        self._arm_sent = False
        self.state_machine.transition_to(DroneState.ARMING)

    def _handle_drop_complete(self) -> None:
        if self.state_machine.state != DroneState.WAIT_DROP_CONFIRM:
            logger.warning(
                "DROP_COMPLETE ignored: not in WAIT_DROP_CONFIRM (current: %s)",
                self.state_machine.state.name,
            )
            return
        logger.info("DROP_COMPLETE received — arming for return home")
        self._landing_phase = "rtl"
        self._aruco_detected = False
        self._arm_sent = False
        self.state_machine.transition_to(DroneState.ARMING)

    def _handle_force_rtl(self) -> None:
        self._force_rtl = True
        self._mission_active = False
        self.mavlink.rtl()
        self.state_machine.force_state(DroneState.RETURN_HOME)
        logger.warning("FORCE_RTL activated")

    def _handle_stop(self) -> None:
        if self.mavlink.telemetry.armed:
            logger.warning("STOP rejected: motors are armed. Use FORCE_RTL or DISARM first.")
            return
        self._mission_active = False
        self._stop_requested = True
        self.state_machine.reset()
        logger.info("Mission stopped, reset to IDLE")

    def _handle_camera_start(self) -> None:
        logger.info("CAMERA_START received")
        self._camera_service.start()

    def _handle_camera_stop(self) -> None:
        logger.info("CAMERA_STOP received")
        self._camera_service.stop()
        self.vision.stop()

    # -----------------------------------------------------------------------
    # Camera callbacks (called from CameraService background thread)
    # -----------------------------------------------------------------------

    def _on_camera_status_sync(self, status: str, device: str) -> None:
        """Thread-safe: schedule async WS send on the event loop."""
        if self._event_loop and self._event_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.ws.send_camera_status(status, device),
                self._event_loop,
            )

    def _on_aruco_detection_sync(self, payload: dict) -> None:
        """Thread-safe: schedule async WS send on the event loop."""
        if self._event_loop and self._event_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.ws.send_aruco_detection(payload),
                self._event_loop,
            )

    # -----------------------------------------------------------------------
    # State entry actions (called once when entering a new state)
    # -----------------------------------------------------------------------

    def _enter_state(self, state: DroneState) -> None:
        self._state_enter_time = time.time()
        self._goto_sent = False

        if state == DroneState.ARMING:
            # ARM only — no OFFBOARD here.
            # Sequence: ARM → wait armed=True → transition to TAKEOFF
            # TAKEOFF is handled by OFFBOARD mode (stream Z setpoint).
            self._arm_sent = False
            self.mavlink.arm()
            self._arm_sent = True

        elif state == DroneState.TAKEOFF:
            # OFFBOARD takeoff: stream position setpoint Z=-alt.
            # Keepalive thread monitors MTF-02P AGL and auto-switches to LOITER.
            target_alt = getattr(self.mavlink, "_target_takeoff_alt", config.TAKEOFF_ALTITUDE_M)
            self.mavlink.takeoff_offboard(target_alt)

        elif state == DroneState.FLY_TO_PICKUP:
            # Transition from PX4 TAKEOFF → LOITER mode + DO_REPOSITION command
            if self.mavlink.telemetry.flight_mode not in ("LOITER", "HOLD", "AUTO.LOITER"):
                logger.info("FLY_TO_PICKUP: ensuring mode is LOITER for DO_REPOSITION navigation")
                self.mavlink.set_mode("LOITER")
            self.mavlink.goto_location(
                self.locations.pickup_lat,
                self.locations.pickup_lon,
                config.TAKEOFF_ALTITUDE_M,
            )
            self._goto_sent = True
            self._last_goto_retry = time.time()

        elif state == DroneState.DESCEND:
            # Descend altitude depends on current phase
            if self._landing_phase in ("pickup", "drop"):
                target_lat = (
                    self.locations.pickup_lat
                    if self._landing_phase == "pickup"
                    else self.locations.drop_lat
                )
                target_lon = (
                    self.locations.pickup_lon
                    if self._landing_phase == "pickup"
                    else self.locations.drop_lon
                )
            else:
                # Fallback
                target_lat = self.locations.pickup_lat
                target_lon = self.locations.pickup_lon

            self.mavlink.goto_location(
                target_lat,
                target_lon,
                config.DESCEND_ALTITUDE_M,
            )
            self._goto_sent = True
            self._landing_status = "DESCENDING"

        elif state == DroneState.SEARCH_ARUCO:
            self._landing_status = "SEARCHING"
            self._handle_camera_start()

        elif state == DroneState.PRECISION_LANDING:
            self._landing_status = "PRECISION_LANDING"
            self._touchdown_handled = False
            self.mavlink.set_mode("PRECLAND")

        elif state == DroneState.WAIT_PICKUP_CONFIRM:
            self._landing_status = "WAIT_PICKUP"
            logger.info("Landed at pickup — waiting for PICKUP_COMPLETE command")
            if self._event_loop and self._event_loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.ws.send_error("mission", "waiting_pickup_confirm"),
                    self._event_loop,
                )

        elif state == DroneState.FLY_TO_DROP:
            # Transition to LOITER mode + DO_REPOSITION command for drop navigation
            if self.mavlink.telemetry.flight_mode not in ("LOITER", "HOLD", "AUTO.LOITER"):
                logger.info("FLY_TO_DROP: ensuring mode is LOITER for DO_REPOSITION navigation")
                self.mavlink.set_mode("LOITER")
            self.mavlink.goto_location(
                self.locations.drop_lat,
                self.locations.drop_lon,
                config.TAKEOFF_ALTITUDE_M,
            )
            self._goto_sent = True
            self._last_goto_retry = time.time()

        elif state == DroneState.WAIT_DROP_CONFIRM:
            self._landing_status = "WAIT_DROP"
            logger.info("Landed at drop — waiting for DROP_COMPLETE command")
            if self._event_loop and self._event_loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.ws.send_error("mission", "waiting_drop_confirm"),
                    self._event_loop,
                )

        elif state == DroneState.RETURN_HOME:
            self._landing_status = "RETURNING_HOME"
            # Stop OFFBOARD keepalive before switching to RTL
            self.mavlink._stop_offboard_keepalive()
            self.mavlink.rtl()

        elif state == DroneState.IDLE:
            self._landing_status = "COMPLETE"
            self._mission_active = False

    # -----------------------------------------------------------------------
    # Transition checker (called every tick)
    # -----------------------------------------------------------------------

    def _check_transitions(self) -> None:
        state = self.state_machine.state
        elapsed = time.time() - self._state_enter_time

        # ── ARMING ─────────────────────────────────────────────────────────
        if state == DroneState.ARMING:
            if elapsed > ARM_TIMEOUT_SEC:
                logger.error("ARM timeout — transitioning to ERROR")
                self.state_machine.transition_to(DroneState.ERROR)
                return

            if self.mavlink.telemetry.armed:
                # Method A: ARM confirmed — go straight to TAKEOFF.
                # PX4 TAKEOFF mode handles the climb. No OFFBOARD needed here.
                logger.info("ARM confirmed — transitioning to TAKEOFF")
                self.state_machine.transition_to(DroneState.TAKEOFF)
            else:
                # Periodic retry every 3.0 seconds if PX4 hasn't armed yet
                last_retry = getattr(self, "_last_arm_retry", 0.0)
                if time.time() - last_retry >= 3.0:
                    logger.info("ARMing in progress — retrying ARM command...")
                    self._last_arm_retry = time.time()
                    self.mavlink.arm()

        # ── TAKEOFF ────────────────────────────────────────────────────────
        elif state == DroneState.TAKEOFF:
            if elapsed > TAKEOFF_TIMEOUT_SEC:
                logger.error("TAKEOFF timeout — transitioning to ERROR")
                self.mavlink._stop_offboard_keepalive()
                self.state_machine.transition_to(DroneState.ERROR)
                return

            target_alt = getattr(self.mavlink, "_target_takeoff_alt", config.TAKEOFF_ALTITUDE_M)
            cur_alt = (
                self.mavlink.telemetry.altitude_agl
                if self.mavlink.telemetry.rangefinder_valid and self.mavlink.telemetry.altitude_agl > 0.1
                else self.mavlink.telemetry.altitude_relative
            )
            current_mode = self.mavlink.telemetry.flight_mode

            # OFFBOARD takeoff complete: keepalive thread set the flag and switched to LOITER
            takeoff_done = (
                self.mavlink._offboard_takeoff_complete
                or current_mode in ("AUTO.LOITER", "HOLD", "AUTO.HOLD", "LOITER")
                or cur_alt >= target_alt
            )

            if takeoff_done:
                logger.info(
                    "✓ OFFBOARD takeoff complete! Mode=%s, Altitude=%.2fm (target=%.1fm)",
                    current_mode,
                    cur_alt,
                    target_alt,
                )
                # Reset flag for next takeoff cycle
                self.mavlink._offboard_takeoff_complete = False

                if self._mission_active:
                    if self._landing_phase == "pickup":
                        self.state_machine.transition_to(DroneState.FLY_TO_PICKUP)
                    elif self._landing_phase == "enroute_drop":
                        self.state_machine.transition_to(DroneState.FLY_TO_DROP)
                    elif self._landing_phase == "rtl":
                        self.state_machine.transition_to(DroneState.RETURN_HOME)
                else:
                    logger.info("Manual TAKEOFF complete — holding position, waiting for next command")
                    self.state_machine.transition_to(DroneState.IDLE)


        # ── FLY_TO_PICKUP ──────────────────────────────────────────────────
        elif state == DroneState.FLY_TO_PICKUP:
            if elapsed > FLY_TO_PICKUP_TIMEOUT_SEC:
                logger.error("FLY_TO_PICKUP timeout (%.0fs) — transitioning to ERROR", FLY_TO_PICKUP_TIMEOUT_SEC)
                self.state_machine.transition_to(DroneState.ERROR)
                return

            if self.locations.pickup_lat == 0.0 or self.locations.pickup_lon == 0.0:
                logger.error("Invalid pickup coordinates (0.0, 0.0) — transitioning to ERROR")
                self.state_machine.transition_to(DroneState.ERROR)
                return

            if self._mission_active and self.mavlink.is_at_location(
                self.locations.pickup_lat,
                self.locations.pickup_lon,
                config.NAV_ACCEPTANCE_RADIUS_M,
            ):
                self._landing_phase = "pickup"
                self.state_machine.transition_to(DroneState.DESCEND)
            else:
                last_retry = getattr(self, "_last_goto_retry", 0.0)
                if time.time() - last_retry >= 3.0:
                    self._last_goto_retry = time.time()
                    if self.mavlink.telemetry.flight_mode not in ("LOITER", "HOLD", "AUTO.LOITER"):
                        self.mavlink.set_mode("LOITER")
                    self.mavlink.goto_location(
                        self.locations.pickup_lat,
                        self.locations.pickup_lon,
                        config.TAKEOFF_ALTITUDE_M,
                    )

        # ── FLY_TO_DROP ────────────────────────────────────────────────────
        elif state == DroneState.FLY_TO_DROP:
            if elapsed > FLY_TO_DROP_TIMEOUT_SEC:
                logger.error("FLY_TO_DROP timeout (%.0fs) — transitioning to ERROR", FLY_TO_DROP_TIMEOUT_SEC)
                self.state_machine.transition_to(DroneState.ERROR)
                return

            if self.locations.drop_lat == 0.0 or self.locations.drop_lon == 0.0:
                logger.error("Invalid drop coordinates (0.0, 0.0) — transitioning to ERROR")
                self.state_machine.transition_to(DroneState.ERROR)
                return

            if self._mission_active and self.mavlink.is_at_location(
                self.locations.drop_lat,
                self.locations.drop_lon,
                config.NAV_ACCEPTANCE_RADIUS_M,
            ):
                self._landing_phase = "drop"
                self.state_machine.transition_to(DroneState.DESCEND)
            else:
                last_retry = getattr(self, "_last_goto_retry", 0.0)
                if time.time() - last_retry >= 3.0:
                    self._last_goto_retry = time.time()
                    if self.mavlink.telemetry.flight_mode not in ("LOITER", "HOLD", "AUTO.LOITER"):
                        self.mavlink.set_mode("LOITER")
                    self.mavlink.goto_location(
                        self.locations.drop_lat,
                        self.locations.drop_lon,
                        config.TAKEOFF_ALTITUDE_M,
                    )

        # ── DESCEND ────────────────────────────────────────────────────────
        elif state == DroneState.DESCEND:
            if elapsed > DESCEND_TIMEOUT_SEC:
                logger.error("DESCEND timeout (%.0fs) — transitioning to ERROR", DESCEND_TIMEOUT_SEC)
                self.state_machine.transition_to(DroneState.ERROR)
                return

            if self._mission_active and self.mavlink.telemetry.altitude_relative <= config.DESCEND_ALTITUDE_M + 0.3:
                self.state_machine.transition_to(DroneState.SEARCH_ARUCO)

        # ── SEARCH_ARUCO ───────────────────────────────────────────────────
        elif state == DroneState.SEARCH_ARUCO:
            if elapsed > ARUCO_SEARCH_TIMEOUT_SEC:
                logger.error("ArUco search timeout — transitioning to ERROR")
                self.state_machine.transition_to(DroneState.ERROR)
                return
            if self._mission_active and self._aruco_detected:
                self.state_machine.transition_to(DroneState.PRECISION_LANDING)
            else:
                # Auto-climb FOV expansion for narrow USB camera angle:
                # If marker not detected after 6s at 1.0m altitude, climb to 2.2m to double ground FOV coverage
                last_climb = getattr(self, "_last_search_climb", 0.0)
                if elapsed >= 6.0 and (time.time() - last_climb >= 5.0):
                    self._last_search_climb = time.time()
                    target_lat = self.locations.pickup_lat if self._landing_phase == "pickup" else self.locations.drop_lat
                    target_lon = self.locations.pickup_lon if self._landing_phase == "pickup" else self.locations.drop_lon
                    if target_lat and target_lon:
                        logger.info("ArUco not detected at 1.0m — climbing to 2.2m altitude to double camera FOV coverage...")
                        self.mavlink.goto_location(target_lat, target_lon, 2.2)

        # ── PRECISION_LANDING ──────────────────────────────────────────────
        elif state == DroneState.PRECISION_LANDING:
            # Wait for PX4 to confirm: landed=True AND armed=False (auto-disarmed)
            if self.mavlink.is_landed() and not self.mavlink.telemetry.armed:
                # Guard: only process touchdown once
                if getattr(self, "_touchdown_handled", False):
                    return
                self._touchdown_handled = True

                logger.info("[VISION] Touchdown & Disarmed confirmed — stopping camera immediately")
                self.vision.stop()
                self._camera_service.stop()
                if self._event_loop and self._event_loop.is_running():
                    loc_type_map = {
                        "pickup": "CUSTOMER_PICKUP",
                        "drop": "CUSTOMER_DROP",
                    }
                    loc_type = loc_type_map.get(self._landing_phase, "WAREHOUSE_PAD")
                    asyncio.run_coroutine_threadsafe(
                        self.ws.send_landing_result(
                            loc_type,
                            True,
                            self.vision.last_pose.dx,
                            self.vision.last_pose.dy,
                        ),
                        self._event_loop,
                    )
                if self._mission_active:
                    if self._landing_phase == "pickup":
                        self.state_machine.transition_to(DroneState.WAIT_PICKUP_CONFIRM)
                    elif self._landing_phase == "drop":
                        self.state_machine.transition_to(DroneState.WAIT_DROP_CONFIRM)
                else:
                    self.state_machine.transition_to(DroneState.IDLE)

        # ── WAIT_PICKUP_CONFIRM ────────────────────────────────────────────
        # No automatic transition — waits indefinitely for PICKUP_COMPLETE command

        # ── WAIT_DROP_CONFIRM ──────────────────────────────────────────────
        # No automatic transition — waits indefinitely for DROP_COMPLETE command

        # ── RETURN_HOME ────────────────────────────────────────────────────
        elif state == DroneState.RETURN_HOME:
            # Wait for PX4 auto-land + auto-disarm at home
            if self.mavlink.is_landed() and not self.mavlink.telemetry.armed:
                self.state_machine.transition_to(DroneState.IDLE)
                self._force_rtl = False

        # ── ERROR ──────────────────────────────────────────────────────────
        elif state == DroneState.ERROR:
            # Auto-recover to IDLE after 5 seconds (no motors running)
            if elapsed > 5.0 and not self.mavlink.telemetry.armed:
                logger.info("ERROR recovery — returning to IDLE")
                self.state_machine.transition_to(DroneState.IDLE)

    def shutdown(self) -> None:
        self._landing_target_thread_running = False
        if self._landing_target_thread:
            self._landing_target_thread.join(timeout=1.0)

    # -----------------------------------------------------------------------
    # Vision processing & MAVLink Landing Target Publisher
    # -----------------------------------------------------------------------

    def process_vision(self) -> None:
        """Called on main tick (50ms loop) to update local FSM state flags."""
        state = self.state_machine.state
        if state not in (DroneState.SEARCH_ARUCO, DroneState.PRECISION_LANDING):
            return

        pose = self.vision.last_pose
        is_blind_zone = (
            self.mavlink.telemetry.rangefinder_valid
            and self.mavlink.telemetry.altitude_agl < 0.4
        )

        if is_blind_zone:
            self._aruco_detected = True
        else:
            self._aruco_detected = pose.detected

    def _run_landing_target_publisher(self) -> None:
        """Background thread publishing MAVLink LANDING_TARGET messages at a stable 25Hz."""
        logger.info("MAVLink landing target publisher thread started")
        while self._landing_target_thread_running:
            try:
                state = self.state_machine.state
                if state in (DroneState.SEARCH_ARUCO, DroneState.PRECISION_LANDING):
                    pose = self.vision.last_pose
                    is_blind_zone = (
                        self.mavlink.telemetry.rangefinder_valid
                        and self.mavlink.telemetry.altitude_agl < 0.4
                    )

                    if is_blind_zone:
                        if pose.detected:
                            self.mavlink.send_landing_target(
                                pose.angle_x,
                                pose.angle_y,
                                pose.distance,
                            )
                        else:
                            if state == DroneState.PRECISION_LANDING:
                                last_detected = self.vision.last_detected_pose
                                if last_detected.detected:
                                    self.mavlink.send_landing_target(
                                        last_detected.angle_x,
                                        last_detected.angle_y,
                                        last_detected.distance,
                                    )
                                else:
                                    self.mavlink.send_landing_target(0.0, 0.0, self.mavlink.telemetry.altitude_agl)

                                # Force switch flight mode to LAND to ensure vertical touchdown
                                if self.mavlink.telemetry.flight_mode != "LAND":
                                    logger.info("Forcing LAND mode for final touchdown")
                                    self.mavlink.land()
                    else:
                        if pose.detected:
                            self.mavlink.send_landing_target(
                                pose.angle_x,
                                pose.angle_y,
                                pose.distance,
                            )
            except Exception as exc:
                logger.error("Error in landing target publisher thread: %s", exc)
            time.sleep(0.040)  # 25Hz frequency

    # -----------------------------------------------------------------------
    # Main loop tick (~50ms cadence)
    # -----------------------------------------------------------------------

    def _on_state_transition(self, old_state: DroneState, new_state: DroneState) -> None:
        """Invoked immediately whenever the state machine transitions."""
        self._enter_state(new_state)

    def tick(self) -> None:
        self.mavlink.poll_messages()
        self._check_transitions()
        self.process_vision()

    # -----------------------------------------------------------------------
    # Accessors (used by telemetry sender)
    # -----------------------------------------------------------------------

    def get_aruco_detected(self) -> bool:
        return self._aruco_detected

    def get_landing_status(self) -> str:
        return self._landing_status

    def get_landing_phase(self) -> str:
        return self._landing_phase

    def get_camera_service(self) -> CameraService:
        return self._camera_service

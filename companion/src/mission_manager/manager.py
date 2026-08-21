"""
MissionManager — Manual Step-by-Step Flight Pipeline & Manual Control.

Design principles:
  - 100% Manual Step Control: No automatic FSM chaining or auto-advance cascades.
  - Each flight step is triggered explicitly by the operator from Web HMI:
      * Step 1: RESET_IDLE   -> Reset system state to IDLE
      * Step 2: ARM / DISARM -> Motor arm / disarm safety
      * Step 3: TAKEOFF      -> Climb to set altitude (1.5m), switch to LOITER, and hold position
      * Step 4: NAV_GPS      -> Fly to designated coordinates (LOITER + DO_REPOSITION) and hold position
      * Step 5: DESCEND      -> Descend to approach altitude (1.0m) and hold position
      * Step 6: SEARCH_ARUCO -> Camera vision activation & realtime marker detection telemetry
      * Step 7: LANDING      -> PRECISION_LANDING (ArUco LANDING_TARGET @ 25Hz) or NORMAL_LANDING (LAND)
  - Emergency & Quick Modes: FORCE_RTL, SET_MODE (LOITER, LAND, RTL, OFFBOARD).
  - Background Telemetry & Camera services maintain realtime status broadcasting.
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


@dataclass
class MissionLocations:
    home_lat: float = 0.0
    home_lon: float = 0.0
    pickup_lat: float = 0.0
    pickup_lon: float = 0.0
    drop_lat: float = 0.0
    drop_lon: float = 0.0


class MissionManager:
    """Orchestrates manual step-by-step drone operations."""

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

        self._force_rtl = False
        self._stop_requested = False
        self._landing_status = "IDLE"
        self._aruco_detected = False
        self._state_enter_time = time.time()
        self._landing_phase = "manual"
        self._touchdown_handled = False

        # Camera test service — controlled from frontend (uses shared vision_service)
        self._camera_service = CameraService(
            on_camera_status=self._on_camera_status_sync,
            on_aruco_detection=self._on_aruco_detection_sync,
            vision_service=self.vision,
        )
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None

        # Threading support for high-rate MAVLink landing target publisher (25Hz)
        self._landing_target_thread_running = True
        self._landing_target_thread = threading.Thread(
            target=self._run_landing_target_publisher, daemon=True
        )
        self._landing_target_thread.start()

    # -----------------------------------------------------------------------
    # Event loop setter
    # -----------------------------------------------------------------------

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Store event loop reference for scheduling async callbacks from threads."""
        self._event_loop = loop

    # -----------------------------------------------------------------------
    # Command router (called from WebSocket receive loop)
    # -----------------------------------------------------------------------

    def handle_command(self, payload: dict) -> None:
        action = payload.get("action", "")
        logger.info("[COMMAND] Received command: %s", action)

        if action == "STEP_COMMAND":
            self._handle_step_command(payload)

        elif action == "ARM":
            self._handle_arm()

        elif action == "DISARM":
            self._handle_disarm(payload)

        elif action == "SET_MODE":
            self._handle_set_mode(payload)

        elif action == "FORCE_RTL":
            self._handle_force_rtl()

        elif action == "STOP":
            self._handle_stop()

        elif action == "CAMERA_START":
            self._handle_camera_start()

        elif action == "CAMERA_STOP":
            self._handle_camera_stop()

        elif action in ("PICKUP_COMPLETE", "DROP_COMPLETE"):
            logger.info("[COMMAND] %s acknowledged in manual mode", action)
            self._landing_status = "COMPLETE"

    # -----------------------------------------------------------------------
    # Manual Step-by-Step Flight Pipeline
    # -----------------------------------------------------------------------

    def _handle_step_command(self, payload: dict) -> None:
        """Execute individual manual step commands from Web HMI."""
        step = payload.get("step_action", "")
        logger.info("[MANUAL STEP] Executing: %s", step)

        if step == "RESET_IDLE":
            self.state_machine.reset()
            self._landing_status = "IDLE"
            self._touchdown_handled = False
            logger.info("[MANUAL STEP 1] FSM state manually reset to IDLE")

        elif step == "ARM":
            self._handle_arm()

        elif step == "DISARM":
            self._handle_disarm(payload)

        elif step == "TAKEOFF":
            if not self.mavlink.telemetry.armed:
                logger.warning("[MANUAL STEP 2] TAKEOFF rejected: drone is DISARMED. Arm first.")
                return
            alt = payload.get("alt", config.TAKEOFF_ALTITUDE_M)
            logger.info("[MANUAL STEP 2] TAKEOFF initiated to %.1fm (OFFBOARD -> LOITER)", alt)
            self.mavlink._target_takeoff_alt = alt
            self.mavlink.takeoff(alt)
            self.state_machine.force_state(DroneState.TAKEOFF)
            self._landing_status = "TAKEOFF"

        elif step == "NAV_GPS":
            if not self.mavlink.telemetry.armed:
                logger.warning("[MANUAL STEP 3] NAV_GPS rejected: drone is DISARMED.")
                return
            lat = payload.get("lat")
            lon = payload.get("lon")
            alt = payload.get("alt", config.TAKEOFF_ALTITUDE_M)

            target_lat = lat or (self.locations.pickup_lat if self.locations.pickup_lat != 0.0 else self.mavlink.telemetry.latitude)
            target_lon = lon or (self.locations.pickup_lon if self.locations.pickup_lon != 0.0 else self.mavlink.telemetry.longitude)

            if not target_lat or not target_lon or target_lat == 0.0 or target_lon == 0.0:
                logger.error("[MANUAL STEP 3] NAV_GPS rejected: invalid coordinates (lat=%.6f, lon=%.6f)", target_lat or 0.0, target_lon or 0.0)
                return

            self.locations.pickup_lat = target_lat
            self.locations.pickup_lon = target_lon

            logger.info("[MANUAL STEP 3] NAV_GPS navigating to lat=%.6f, lon=%.6f, alt=%.1fm", target_lat, target_lon, alt)
            if self.mavlink.telemetry.flight_mode not in ("LOITER", "HOLD", "AUTO.LOITER"):
                self.mavlink.set_mode("LOITER", force_send=True)
                time.sleep(0.2)
            self.mavlink.goto_location(target_lat, target_lon, alt)
            self.state_machine.force_state(DroneState.FLY_TO_PICKUP)
            self._landing_status = "NAVIGATING_GPS"

        elif step == "DESCEND":
            if not self.mavlink.telemetry.armed:
                logger.warning("[MANUAL STEP 4] DESCEND rejected: drone is DISARMED.")
                return
            search_alt = payload.get("alt", config.DESCEND_ALTITUDE_M)
            cur_lat = self.mavlink.telemetry.latitude or payload.get("lat", 0.0)
            cur_lon = self.mavlink.telemetry.longitude or payload.get("lon", 0.0)

            if not cur_lat or not cur_lon or cur_lat == 0.0 or cur_lon == 0.0:
                logger.error("[MANUAL STEP 4] DESCEND rejected: no valid position fix")
                return

            logger.info("[MANUAL STEP 4] DESCEND to approach altitude %.1fm at lat=%.6f, lon=%.6f", search_alt, cur_lat, cur_lon)
            if self.mavlink.telemetry.flight_mode not in ("LOITER", "HOLD", "AUTO.LOITER"):
                self.mavlink.set_mode("LOITER", force_send=True)
                time.sleep(0.2)
            self.mavlink.goto_location(cur_lat, cur_lon, search_alt)
            self.state_machine.force_state(DroneState.DESCEND)
            self._landing_status = "DESCENDING"

        elif step == "SEARCH_ARUCO":
            logger.info("[MANUAL STEP 5] SEARCH_ARUCO initiated — starting camera vision")
            self._handle_camera_start()
            self.state_machine.force_state(DroneState.SEARCH_ARUCO)
            self._landing_status = "SEARCHING_ARUCO"

        elif step == "PRECISION_LANDING":
            logger.info("[MANUAL STEP 6] PRECISION_LANDING initiated — starting PRECLAND & target publisher")
            self._handle_camera_start()
            self._touchdown_handled = False
            self.mavlink.set_mode("PRECLAND", force_send=True)
            self.state_machine.force_state(DroneState.PRECISION_LANDING)
            self._landing_status = "PRECISION_LANDING"

        elif step == "NORMAL_LANDING":
            logger.info("[MANUAL STEP 7] NORMAL_LANDING (Auto Land) initiated")
            self.mavlink.land()
            self.state_machine.force_state(DroneState.DESCEND)
            self._landing_status = "LANDING"

    # -----------------------------------------------------------------------
    # Direct Control Actions
    # -----------------------------------------------------------------------

    def _handle_set_mode(self, payload: dict) -> None:
        mode = payload.get("mode")
        if not mode:
            return
        logger.info("[SET_MODE] Manual mode request: %s", mode)
        if mode == "TAKEOFF":
            if not self.mavlink.telemetry.armed:
                logger.warning("[SET_MODE] TAKEOFF requested while DISARMED. Arm first.")
                return
            logger.info("[SET_MODE] TAKEOFF initiated (alt=%.1fm)", config.TAKEOFF_ALTITUDE_M)
            self.mavlink.takeoff(config.TAKEOFF_ALTITUDE_M)
            self.state_machine.force_state(DroneState.TAKEOFF)
        elif mode == "OFFBOARD":
            if not self.mavlink.telemetry.armed:
                logger.warning("[SET_MODE] OFFBOARD requested while DISARMED. Arm first.")
            self.mavlink.set_mode_offboard()
        else:
            self.mavlink.set_mode(mode)

    def _handle_arm(self) -> None:
        """Manual ARM command from dashboard."""
        if self.mavlink.telemetry.armed:
            logger.warning("[ARM] Rejected: already armed")
            return

        # Automatically save current GPS position as Home upon arming
        cur_lat = self.mavlink.telemetry.latitude
        cur_lon = self.mavlink.telemetry.longitude
        if cur_lat != 0.0 and cur_lon != 0.0:
            self.locations.home_lat = cur_lat
            self.locations.home_lon = cur_lon
            logger.info("[ARM] Locked Home GPS location: lat=%.6f, lon=%.6f", cur_lat, cur_lon)

        logger.info("[ARM] Sending ARM command to PX4...")
        self.mavlink.arm()
        self.state_machine.force_state(DroneState.ARMING)

    def _handle_disarm(self, payload: dict) -> None:
        """Manual DISARM command from dashboard."""
        force = payload.get("force", False)
        if self.state_machine.is_flying() and not force:
            logger.warning("[DISARM] Rejected: drone is airborne (state=%s). Use force=True if emergency.", self.state_machine.state.name)
            return
        logger.info("[DISARM] Sending DISARM command (force=%s)", force)
        self.mavlink.disarm(force=force)
        self.state_machine.force_state(DroneState.IDLE)
        self._landing_status = "IDLE"

    def _handle_force_rtl(self) -> None:
        logger.warning("[FORCE_RTL] Emergency Return To Land triggered!")
        self._force_rtl = True
        self.mavlink._stop_offboard_keepalive()
        self.mavlink.rtl()
        self.state_machine.force_state(DroneState.RETURN_HOME)
        self._landing_status = "RETURNING_HOME"

    def _handle_stop(self) -> None:
        if self.mavlink.telemetry.armed:
            logger.warning("[STOP] Rejected: motors are armed. Disarm or FORCE_RTL first.")
            return
        self._stop_requested = True
        self.state_machine.reset()
        self._landing_status = "IDLE"
        logger.info("[STOP] Manual reset to IDLE")

    def _handle_camera_start(self) -> None:
        logger.info("[CAMERA] Starting CameraService...")
        self._camera_service.start()

    def _handle_camera_stop(self) -> None:
        logger.info("[CAMERA] Stopping CameraService...")
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
    # State entry actions
    # -----------------------------------------------------------------------

    def _enter_state(self, state: DroneState) -> None:
        self._state_enter_time = time.time()
        logger.info("[STATE ENTER] Entered state: %s", state.name)

    def _on_state_transition(self, old_state: DroneState, new_state: DroneState) -> None:
        self._enter_state(new_state)

    # -----------------------------------------------------------------------
    # Periodic Non-intrusive Status Verification (Called every tick)
    # -----------------------------------------------------------------------

    def _check_status(self) -> None:
        """
        Pure passive status monitor:
        - Detects when takeoff altitude is reached -> switches to LOITER hold and marks IDLE.
        - Detects when landing touchdown + disarm occurs -> stops camera and marks IDLE.
        - NEVER automatically advances to next flight phase.
        """
        state = self.state_machine.state

        # Check TAKEOFF completion
        if state == DroneState.TAKEOFF:
            target_alt = getattr(self.mavlink, "_target_takeoff_alt", config.TAKEOFF_ALTITUDE_M)
            cur_alt = (
                self.mavlink.telemetry.altitude_agl
                if self.mavlink.telemetry.rangefinder_valid and self.mavlink.telemetry.altitude_agl > 0.1
                else self.mavlink.telemetry.altitude_relative
            )
            current_mode = self.mavlink.telemetry.flight_mode

            takeoff_done = (
                self.mavlink._offboard_takeoff_complete
                or current_mode in ("AUTO.LOITER", "HOLD", "AUTO.HOLD", "LOITER")
                or cur_alt >= (target_alt * 0.95)
            )

            if takeoff_done:
                logger.info(
                    "✓ [TAKEOFF COMPLETE] Altitude=%.2fm (target=%.1fm, mode=%s) — Holding LOITER position, waiting for next manual step.",
                    cur_alt, target_alt, current_mode,
                )
                self.mavlink._offboard_takeoff_complete = False
                self.state_machine.force_state(DroneState.IDLE)
                self._landing_status = "HOVERING_LOITER"

        # Check Touchdown in PRECISION_LANDING or RETURN_HOME
        elif state in (DroneState.PRECISION_LANDING, DroneState.RETURN_HOME):
            if self.mavlink.is_landed() and not self.mavlink.telemetry.armed:
                if getattr(self, "_touchdown_handled", False):
                    return
                self._touchdown_handled = True

                logger.info("✓ [TOUCHDOWN CONFIRMED] Drone landed and disarmed. Stopping camera...")
                self.vision.stop()
                self._camera_service.stop()

                if self._event_loop and self._event_loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        self.ws.send_landing_result(
                            "MANUAL_PAD",
                            True,
                            self.vision.last_pose.dx,
                            self.vision.last_pose.dy,
                        ),
                        self._event_loop,
                    )

                self.state_machine.force_state(DroneState.IDLE)
                self._landing_status = "LANDED"
                self._force_rtl = False

    # -----------------------------------------------------------------------
    # Vision processing & High-rate LANDING_TARGET Publisher (25Hz)
    # -----------------------------------------------------------------------

    def process_vision(self) -> None:
        """Update local ArUco detection status on main tick."""
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
        logger.info("[LANDING TARGET] Publisher thread started @ 25Hz")
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

                                # Force switch flight mode to LAND for final vertical touchdown
                                if self.mavlink.telemetry.flight_mode != "LAND":
                                    logger.info("[PRECISION LANDING] Final touchdown blind zone — forcing LAND mode")
                                    self.mavlink.land()
                    else:
                        if pose.detected:
                            self.mavlink.send_landing_target(
                                pose.angle_x,
                                pose.angle_y,
                                pose.distance,
                            )
            except Exception as exc:
                logger.error("[LANDING TARGET] Error in publisher thread: %s", exc)
            time.sleep(0.040)  # 25Hz frequency

    # -----------------------------------------------------------------------
    # Main tick loop
    # -----------------------------------------------------------------------

    def tick(self) -> None:
        self.mavlink.poll_messages()
        self._check_status()
        self.process_vision()

    def shutdown(self) -> None:
        self._landing_target_thread_running = False
        if self._landing_target_thread:
            self._landing_target_thread.join(timeout=1.0)
        self._camera_service.stop()
        self.vision.stop()

    # -----------------------------------------------------------------------
    # Accessors
    # -----------------------------------------------------------------------

    def get_aruco_detected(self) -> bool:
        return self._aruco_detected

    def get_landing_status(self) -> str:
        return self._landing_status

    def get_landing_phase(self) -> str:
        return self._landing_phase

    def get_camera_service(self) -> CameraService:
        return self._camera_service

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
        self.state_machine = StateMachine()
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

        # Continuous Delivery: a new START arrived while drone is RETURN_HOME
        self._pending_mission: Optional[MissionLocations] = None

        # Camera test service — controlled from frontend
        self._camera_service = CameraService(
            on_camera_status=self._on_camera_status_sync,
            on_aruco_detection=self._on_aruco_detection_sync,
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

        if action in ("START", "START_MISSION"):
            self._handle_start(payload)

        elif action == "PICKUP_COMPLETE":
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

        elif action == "MOVE_RELATIVE":
            self._handle_move_relative(payload)

        elif action == "ARM":
            self._handle_arm()

        elif action == "DISARM":
            self._handle_disarm(payload)

    def _handle_set_mode(self, payload: dict) -> None:
        mode = payload.get("mode")
        if mode:
            logger.info("Setting flight mode to: %s", mode)
            if mode == "OFFBOARD":
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
        if self.state_machine.state != DroneState.IDLE:
            logger.warning(
                "Manual ARM rejected: drone is in state %s (must be IDLE)",
                self.state_machine.state.name,
            )
            return
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
        logger.info("Manual DISARM command sent (force=%s)", force)
        self.mavlink.disarm(force=force)

    def _handle_move_relative(self, payload: dict) -> None:
        dx = payload.get("dx", 0.0)
        dy = payload.get("dy", 0.0)
        dz = payload.get("dz", 0.0)
        logger.info("Moving relative: dx=%.1f, dy=%.1f, dz=%.1f", dx, dy, dz)
        self.mavlink.move_relative(dx, dy, dz)

    def _handle_start(self, payload: dict) -> None:
        new_locations = MissionLocations(
            home_lat=payload["home_lat"],
            home_lon=payload["home_lon"],
            pickup_lat=payload["pickup_lat"],
            pickup_lon=payload["pickup_lon"],
            drop_lat=payload["drop_lat"],
            drop_lon=payload["drop_lon"],
        )
        current = self.state_machine.state

        if current == DroneState.IDLE:
            # Normal start
            self.locations = new_locations
            self._mission_active = True
            self._force_rtl = False
            self._stop_requested = False
            self._landing_phase = "pickup"
            self._arm_sent = False
            self.state_machine.transition_to(DroneState.ARMING)

        elif current == DroneState.RETURN_HOME:
            # ── Continuous Delivery Mode ──────────────────────────────────
            # Drone is flying home; intercept and head to next pickup.
            # We arm-if-not-armed is not needed since RETURN_HOME always
            # ends with PX4 auto-land + auto-disarm before we reach IDLE.
            # However, if we're still in the air during RETURN_HOME, PX4
            # is handling the flight — we cannot simply redirect.
            # Strategy: store pending mission; when RETURN_HOME → IDLE
            # transition fires, immediately arm for the pending mission.
            logger.info("Continuous Delivery: queuing next mission during RETURN_HOME")
            self._pending_mission = new_locations

        else:
            logger.warning(
                "START rejected: drone is in state %s (must be IDLE or RETURN_HOME)",
                current.name,
            )

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
        self._pending_mission = None
        self.mavlink.rtl()
        self.state_machine.force_state(DroneState.RETURN_HOME)
        logger.warning("FORCE_RTL activated")

    def _handle_stop(self) -> None:
        if self.mavlink.telemetry.armed:
            logger.warning("STOP rejected: motors are armed. Use FORCE_RTL or DISARM first.")
            return
        self._mission_active = False
        self._stop_requested = True
        self._pending_mission = None
        self.state_machine.reset()
        logger.info("Mission stopped, reset to IDLE")

    def _handle_camera_start(self) -> None:
        logger.info("CAMERA_START received")
        self._camera_service.start()

    def _handle_camera_stop(self) -> None:
        logger.info("CAMERA_STOP received")
        self._camera_service.stop()

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
            # Safety: send ARM only once.
            # PX4 OFFBOARD mode requires the drone to be ARMED first.
            # Correct sequence:
            #   1. ARM in current mode (LOITER / POSCTL / STABILIZED)
            #   2. Wait for armed=True (confirmed from heartbeat)
            #   3. Switch to OFFBOARD  ← done in _check_transitions after arm
            #   4. Send TAKEOFF command ← done in _enter_state(TAKEOFF)
            self._arm_sent = False
            self._offboard_after_arm_done = False
            self.mavlink.arm()
            self._arm_sent = True

        elif state == DroneState.TAKEOFF:
            # Switch to OFFBOARD and send TAKEOFF setpoint.
            # set_mode_offboard() was already called after arm was confirmed,
            # but we call it here too as a safety guard.
            if self.mavlink.telemetry.flight_mode != "OFFBOARD":
                logger.info("TAKEOFF: entering OFFBOARD before takeoff command")
                ok = self.mavlink.set_mode_offboard()
                if not ok:
                    logger.error("Failed to enter OFFBOARD before TAKEOFF")
                    self.state_machine.transition_to(DroneState.ERROR)
                    return
            self.mavlink.takeoff(config.TAKEOFF_ALTITUDE_M)

        elif state == DroneState.FLY_TO_PICKUP:
            self.mavlink.goto_location(
                self.locations.pickup_lat,
                self.locations.pickup_lon,
                config.TAKEOFF_ALTITUDE_M,
            )
            self._goto_sent = True

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
            self.vision.init_camera()

        elif state == DroneState.PRECISION_LANDING:
            self._landing_status = "PRECISION_LANDING"
            self.mavlink.set_mode("PRECLAND")

        elif state == DroneState.WAIT_PICKUP_CONFIRM:
            self._landing_status = "WAIT_PICKUP"
            self.vision.stop()
            logger.info("Landed at pickup — waiting for PICKUP_COMPLETE command")
            asyncio.create_task(
                self.ws.send_status_event("waiting_pickup_confirm")
            )

        elif state == DroneState.FLY_TO_DROP:
            self.mavlink.goto_location(
                self.locations.drop_lat,
                self.locations.drop_lon,
                config.TAKEOFF_ALTITUDE_M,
            )
            self._goto_sent = True

        elif state == DroneState.WAIT_DROP_CONFIRM:
            self._landing_status = "WAIT_DROP"
            self.vision.stop()
            logger.info("Landed at drop — waiting for DROP_COMPLETE command")
            asyncio.create_task(
                self.ws.send_status_event("waiting_drop_confirm")
            )

        elif state == DroneState.RETURN_HOME:
            self._landing_status = "RETURNING_HOME"
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
                # ARM confirmed — now switch to OFFBOARD while motors are live
                if not getattr(self, "_offboard_after_arm_done", False):
                    logger.info("ARM confirmed — switching to OFFBOARD mode")
                    ok = self.mavlink.set_mode_offboard()
                    if not ok:
                        logger.error("Failed to enter OFFBOARD after arm — ERROR")
                        self.state_machine.transition_to(DroneState.ERROR)
                        return
                    self._offboard_after_arm_done = True
                    return  # wait one more tick to confirm mode before transitioning

                self.state_machine.transition_to(DroneState.TAKEOFF)

        # ── TAKEOFF ────────────────────────────────────────────────────────
        elif state == DroneState.TAKEOFF:
            if elapsed > TAKEOFF_TIMEOUT_SEC:
                logger.error("TAKEOFF timeout — transitioning to ERROR")
                self.state_machine.transition_to(DroneState.ERROR)
                return
            if self.mavlink.telemetry.altitude_relative >= config.TAKEOFF_ALTITUDE_M * 0.9:
                if self._landing_phase == "pickup":
                    self.state_machine.transition_to(DroneState.FLY_TO_PICKUP)
                elif self._landing_phase == "enroute_drop":
                    self.state_machine.transition_to(DroneState.FLY_TO_DROP)
                elif self._landing_phase == "rtl":
                    self.state_machine.transition_to(DroneState.RETURN_HOME)

        # ── FLY_TO_PICKUP ──────────────────────────────────────────────────
        elif state == DroneState.FLY_TO_PICKUP:
            if self.mavlink.is_at_location(
                self.locations.pickup_lat,
                self.locations.pickup_lon,
                config.NAV_ACCEPTANCE_RADIUS_M,
            ):
                self._landing_phase = "pickup"
                self.state_machine.transition_to(DroneState.DESCEND)

        # ── FLY_TO_DROP ────────────────────────────────────────────────────
        elif state == DroneState.FLY_TO_DROP:
            if self.mavlink.is_at_location(
                self.locations.drop_lat,
                self.locations.drop_lon,
                config.NAV_ACCEPTANCE_RADIUS_M,
            ):
                self._landing_phase = "drop"
                self.state_machine.transition_to(DroneState.DESCEND)

        # ── DESCEND ────────────────────────────────────────────────────────
        elif state == DroneState.DESCEND:
            if self.mavlink.telemetry.altitude_relative <= config.DESCEND_ALTITUDE_M + 1:
                self.state_machine.transition_to(DroneState.SEARCH_ARUCO)

        # ── SEARCH_ARUCO ───────────────────────────────────────────────────
        elif state == DroneState.SEARCH_ARUCO:
            if elapsed > ARUCO_SEARCH_TIMEOUT_SEC:
                logger.error("ArUco search timeout — transitioning to ERROR")
                self.state_machine.transition_to(DroneState.ERROR)
                return
            if self._aruco_detected:
                self.state_machine.transition_to(DroneState.PRECISION_LANDING)

        # ── PRECISION_LANDING ──────────────────────────────────────────────
        elif state == DroneState.PRECISION_LANDING:
            # Wait for PX4 to confirm: landed=True AND armed=False (auto-disarmed)
            if self.mavlink.is_landed() and not self.mavlink.telemetry.armed:
                asyncio.create_task(
                    self.ws.send_landing_result(
                        self._landing_phase,
                        True,
                        self.vision.last_pose.dx,
                        self.vision.last_pose.dy,
                    )
                )
                if self._landing_phase == "pickup":
                    self.state_machine.transition_to(DroneState.WAIT_PICKUP_CONFIRM)
                elif self._landing_phase == "drop":
                    self.state_machine.transition_to(DroneState.WAIT_DROP_CONFIRM)

        # ── WAIT_PICKUP_CONFIRM ────────────────────────────────────────────
        # No automatic transition — waits indefinitely for PICKUP_COMPLETE command

        # ── WAIT_DROP_CONFIRM ──────────────────────────────────────────────
        # No automatic transition — waits indefinitely for DROP_COMPLETE command

        # ── RETURN_HOME ────────────────────────────────────────────────────
        elif state == DroneState.RETURN_HOME:
            # Wait for PX4 auto-land + auto-disarm at home
            if self.mavlink.is_landed() and not self.mavlink.telemetry.armed:
                if self._pending_mission is not None:
                    # Continuous Delivery: immediately start next mission
                    logger.info("Continuous Delivery: starting pending mission")
                    self.locations = self._pending_mission
                    self._pending_mission = None
                    self._landing_phase = "pickup"
                    self._aruco_detected = False
                    self._arm_sent = False
                    self._mission_active = True
                    self.state_machine.transition_to(DroneState.ARMING)
                else:
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

    def tick(self) -> None:
        prev_state = self.state_machine.state
        self.mavlink.poll_messages()
        self._check_transitions()

        if self.state_machine.state != prev_state:
            self._enter_state(self.state_machine.state)

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

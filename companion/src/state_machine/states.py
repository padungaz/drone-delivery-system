from enum import Enum, auto


class DroneState(Enum):
    IDLE = auto()
    ARMING = auto()
    TAKEOFF = auto()
    FLY_TO_PICKUP = auto()
    DESCEND = auto()
    SEARCH_ARUCO = auto()
    PRECISION_LANDING = auto()
    WAIT_PICKUP_CONFIRM = auto()   # Landed at pickup — waiting user PICKUP_COMPLETE
    FLY_TO_DROP = auto()
    WAIT_DROP_CONFIRM = auto()     # Landed at drop — waiting user DROP_COMPLETE
    RETURN_HOME = auto()           # ARM → TAKEOFF → RTL → auto-land → auto-disarm → IDLE
    ERROR = auto()


# ---------------------------------------------------------------------------
# Valid state transitions — Open for manual step pipeline operations
# ---------------------------------------------------------------------------
ALL_STATES = list(DroneState)

TRANSITIONS: dict[DroneState, list[DroneState]] = {
    state: ALL_STATES for state in DroneState
}

# ---------------------------------------------------------------------------
# Flying states — used to block STOP commands while airborne
# NOTE: WAIT_PICKUP_CONFIRM and WAIT_DROP_CONFIRM are NOT flying states
#       because the drone is on the ground (landed, disarmed)
# ---------------------------------------------------------------------------
FLYING_STATES = {
    DroneState.ARMING,
    DroneState.TAKEOFF,
    DroneState.FLY_TO_PICKUP,
    DroneState.DESCEND,
    DroneState.SEARCH_ARUCO,
    DroneState.PRECISION_LANDING,
    DroneState.FLY_TO_DROP,
    DroneState.RETURN_HOME,
}

# ---------------------------------------------------------------------------
# States where START button should be ENABLED on the frontend
# ---------------------------------------------------------------------------
START_ALLOWED_STATES = {
    DroneState.IDLE,
    DroneState.RETURN_HOME,   # Continuous Delivery Mode
}

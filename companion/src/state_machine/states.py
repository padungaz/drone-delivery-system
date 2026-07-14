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
# Valid state transitions
# ---------------------------------------------------------------------------
TRANSITIONS: dict[DroneState, list[DroneState]] = {
    DroneState.IDLE: [
        DroneState.ARMING,
        DroneState.ERROR,
    ],
    DroneState.ARMING: [
        DroneState.TAKEOFF,
        DroneState.IDLE,
        DroneState.ERROR,
    ],
    DroneState.TAKEOFF: [
        DroneState.FLY_TO_PICKUP,
        DroneState.FLY_TO_DROP,
        DroneState.RETURN_HOME,
        DroneState.ERROR,
    ],
    DroneState.FLY_TO_PICKUP: [
        DroneState.DESCEND,
        DroneState.ERROR,
    ],
    DroneState.DESCEND: [
        DroneState.SEARCH_ARUCO,
        DroneState.ERROR,
    ],
    DroneState.SEARCH_ARUCO: [
        DroneState.PRECISION_LANDING,
        DroneState.ERROR,
    ],
    DroneState.PRECISION_LANDING: [
        DroneState.WAIT_PICKUP_CONFIRM,
        DroneState.WAIT_DROP_CONFIRM,
        DroneState.ERROR,
    ],
    # -- Pickup gate --
    DroneState.WAIT_PICKUP_CONFIRM: [
        DroneState.ARMING,   # triggered by PICKUP_COMPLETE command
        DroneState.ERROR,
    ],
    DroneState.FLY_TO_DROP: [
        DroneState.DESCEND,
        DroneState.ERROR,
    ],
    # -- Drop gate --
    DroneState.WAIT_DROP_CONFIRM: [
        DroneState.ARMING,   # triggered by DROP_COMPLETE command
        DroneState.ERROR,
    ],
    DroneState.RETURN_HOME: [
        DroneState.IDLE,     # after PX4 auto-lands & auto-disarms at home
        DroneState.ARMING,   # Continuous Delivery: intercept mid-flight
        DroneState.ERROR,
    ],
    DroneState.ERROR: [
        DroneState.IDLE,
    ],
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

import logging
from typing import Callable, Optional

from src.state_machine.states import TRANSITIONS, DroneState

logger = logging.getLogger(__name__)


class StateMachine:
    """Explicit state machine for drone delivery mission flow."""

    def __init__(self, on_transition: Optional[Callable[[DroneState, DroneState], None]] = None):
        self._state = DroneState.IDLE
        self._on_transition = on_transition

    @property
    def state(self) -> DroneState:
        return self._state

    @property
    def state_name(self) -> str:
        return self._state.name

    def can_transition_to(self, target: DroneState) -> bool:
        return target in TRANSITIONS.get(self._state, [])

    def transition_to(self, target: DroneState) -> bool:
        if not self.can_transition_to(target):
            logger.warning(
                "Invalid transition: %s -> %s",
                self._state.name,
                target.name,
            )
            return False

        old = self._state
        self._state = target
        logger.info("State transition: %s -> %s", old.name, target.name)

        if self._on_transition:
            self._on_transition(old, target)
        return True

    def force_state(self, state: DroneState) -> None:
        """Emergency override — use only for RTL/STOP/ERROR recovery."""
        old = self._state
        self._state = state
        logger.warning("Force state: %s -> %s", old.name, state.name)
        if self._on_transition:
            self._on_transition(old, state)

    def is_flying(self) -> bool:
        from src.state_machine.states import FLYING_STATES
        return self._state in FLYING_STATES

    def reset(self) -> None:
        self._state = DroneState.IDLE
        logger.info("State machine reset to IDLE")

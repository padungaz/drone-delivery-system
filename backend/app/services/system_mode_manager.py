import logging
from typing import Optional
from app.websocket.manager import system_ws_manager

logger = logging.getLogger(__name__)


class SystemModeManager:
    """Centralized System Mode Controller (AUTO vs MANUAL) with Station Start FSM.
    
    Modes & States:
    - Mode: "AUTO" | "MANUAL"
    - Auto State: "STANDBY" (Waiting for Start) | "RUNNING" (Active dispatching) | "PAUSED" (Operator paused) | "ERROR"
    """

    _instance: Optional["SystemModeManager"] = None

    def __init__(self):
        self.mode: str = "AUTO"  # "AUTO" | "MANUAL"
        self.auto_state: str = "STANDBY"  # "STANDBY" | "RUNNING" | "PAUSED" | "ERROR"
        self.is_scheduler_active: bool = False  # False until Operator presses START KHO TRAM

    @classmethod
    def get_instance(cls) -> "SystemModeManager":
        if cls._instance is None:
            cls._instance = SystemModeManager()
        return cls._instance

    def is_auto(self) -> bool:
        return self.mode.upper() == "AUTO"

    def is_manual(self) -> bool:
        return self.mode.upper() == "MANUAL"

    def is_auto_running(self) -> bool:
        return self.is_auto() and self.auto_state == "RUNNING" and self.is_scheduler_active

    def can_auto_dispatch(self) -> bool:
        return self.is_auto_running()

    async def set_mode(self, new_mode: str) -> str:
        validated_mode = new_mode.upper().strip()
        if validated_mode not in ("AUTO", "MANUAL"):
            raise ValueError("System mode must be 'AUTO' or 'MANUAL'")

        old_mode = self.mode
        self.mode = validated_mode
        if self.mode == "AUTO":
            # Entering AUTO mode defaults to STANDBY (requires Operator to press START)
            self.auto_state = "STANDBY"
            self.is_scheduler_active = False
        else:
            # Entering MANUAL mode stops auto scheduler
            self.auto_state = "PAUSED"
            self.is_scheduler_active = False

        logger.info("[SystemModeManager] System Mode changed: %s -> %s (State: %s, Scheduler Active: %s)",
                    old_mode, self.mode, self.auto_state, self.is_scheduler_active)

        # Broadcast mode change to all connected WebSocket clients
        await system_ws_manager.broadcast("SYSTEM_MODE_UPDATE", {
            "mode": self.mode,
            "auto_state": self.auto_state,
            "is_scheduler_active": self.is_scheduler_active,
            "message": f"Chế độ hệ thống đã chuyển sang: {self.mode} ({self.auto_state})",
        })
        return self.mode

    async def set_auto_running(self) -> None:
        """Activate full AUTO RUNNING mode and enable FIFO Scheduler."""
        if not self.is_auto():
            self.mode = "AUTO"
        self.auto_state = "RUNNING"
        self.is_scheduler_active = True
        logger.info("[SystemModeManager] ⚡ AUTO STATE -> RUNNING (Scheduler Active: True)")

        await system_ws_manager.broadcast("SYSTEM_MODE_UPDATE", {
            "mode": self.mode,
            "auto_state": self.auto_state,
            "is_scheduler_active": self.is_scheduler_active,
            "message": "⚡ Hệ thống kho trạm đã KHỞI ĐỘNG TỰ ĐỘNG (RUNNING)!",
        })

    async def set_auto_paused(self) -> None:
        """Pause AUTO mode without switching to MANUAL."""
        self.auto_state = "PAUSED"
        self.is_scheduler_active = False
        logger.info("[SystemModeManager] ⏸️ AUTO STATE -> PAUSED (Scheduler Active: False)")

        await system_ws_manager.broadcast("SYSTEM_MODE_UPDATE", {
            "mode": self.mode,
            "auto_state": self.auto_state,
            "is_scheduler_active": self.is_scheduler_active,
            "message": "⏸️ Hệ thống kho trạm đã TẠM DỪNG TỰ ĐỘNG (PAUSED).",
        })

    def get_status(self) -> dict:
        return {
            "mode": self.mode,
            "auto_state": self.auto_state,
            "is_auto": self.is_auto(),
            "is_manual": self.is_manual(),
            "is_auto_running": self.is_auto_running(),
            "is_scheduler_active": self.is_scheduler_active,
        }


system_mode_manager = SystemModeManager.get_instance()



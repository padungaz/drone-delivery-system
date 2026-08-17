import logging
from typing import Optional
from app.websocket.manager import system_ws_manager

logger = logging.getLogger(__name__)


class SystemModeManager:
    """Centralized System Mode Controller (AUTO vs MANUAL).
    
    Modes:
    - AUTO: Full automation. Mission Queue auto-dispatches and coordinates all devices.
    - MANUAL: Maintenance & manual testing. Auto-dispatch is locked; devices accept independent manual commands.
    """

    _instance: Optional["SystemModeManager"] = None

    def __init__(self):
        self.mode: str = "AUTO"  # "AUTO" | "MANUAL"

    @classmethod
    def get_instance(cls) -> "SystemModeManager":
        if cls._instance is None:
            cls._instance = SystemModeManager()
        return cls._instance

    def is_auto(self) -> bool:
        return self.mode.upper() == "AUTO"

    def is_manual(self) -> bool:
        return self.mode.upper() == "MANUAL"

    async def set_mode(self, new_mode: str) -> str:
        validated_mode = new_mode.upper()
        if validated_mode not in ("AUTO", "MANUAL"):
            raise ValueError("System mode must be 'AUTO' or 'MANUAL'")

        old_mode = self.mode
        self.mode = validated_mode
        logger.info("[SystemModeManager] System Mode changed: %s -> %s", old_mode, self.mode)

        # Broadcast mode change to all connected WebSocket clients
        await system_ws_manager.broadcast("SYSTEM_MODE_UPDATE", {
            "mode": self.mode,
            "message": f"Chế độ hệ thống đã chuyển sang: {self.mode}",
        })
        return self.mode

    def get_status(self) -> dict:
        return {
            "mode": self.mode,
            "is_auto": self.is_auto(),
            "is_manual": self.is_manual(),
        }


system_mode_manager = SystemModeManager.get_instance()

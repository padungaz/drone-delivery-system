import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class DeviceLockManager:
    """Central Safety Interlock Manager.
    
    Prevents manual commands from overriding hardware devices (PLC, Robot, Station)
    while an automated mission (AUTO) is actively executing hardware sequences.
    """

    _instance: Optional["DeviceLockManager"] = None

    def __init__(self):
        # Maps device_name -> { "locked": bool, "locked_by": str, "mission_id": Optional[int], "locked_at": Optional[datetime], "reason": str }
        self._locks: Dict[str, Dict[str, Any]] = {
            "PLC01": {"locked": False, "locked_by": None, "mission_id": None, "locked_at": None, "reason": None},
            "ROBOT01": {"locked": False, "locked_by": None, "mission_id": None, "locked_at": None, "reason": None},
            "CAM01": {"locked": False, "locked_by": None, "mission_id": None, "locked_at": None, "reason": None},
            "STATION": {"locked": False, "locked_by": None, "mission_id": None, "locked_at": None, "reason": None},
        }

    @classmethod
    def get_instance(cls) -> "DeviceLockManager":
        if cls._instance is None:
            cls._instance = DeviceLockManager()
        return cls._instance

    def lock_device(self, device_name: str, locked_by: str = "AUTO_MISSION", mission_id: Optional[int] = None, reason: str = "Automated execution in progress") -> bool:
        """Acquires lock on a specific device or the entire STATION."""
        dev = device_name.upper().strip()
        if dev not in self._locks:
            self._locks[dev] = {"locked": False, "locked_by": None, "mission_id": None, "locked_at": None, "reason": None}

        self._locks[dev] = {
            "locked": True,
            "locked_by": locked_by,
            "mission_id": mission_id,
            "locked_at": datetime.utcnow().isoformat(),
            "reason": reason,
        }
        logger.info("[DeviceLockManager] 🔒 LOCKED %s by %s (Mission #%s: %s)", dev, locked_by, mission_id, reason)
        return True

    def unlock_device(self, device_name: str) -> bool:
        """Releases lock on a specific device or STATION."""
        dev = device_name.upper().strip()
        if dev in self._locks:
            old_lock = self._locks[dev]
            self._locks[dev] = {
                "locked": False,
                "locked_by": None,
                "mission_id": None,
                "locked_at": None,
                "reason": None,
            }
            logger.info("[DeviceLockManager] 🔓 UNLOCKED %s (was locked by %s)", dev, old_lock.get("locked_by"))
        return True

    def lock_station(self, mission_id: int, reason: str = "Station processing 11-step hardware sequence") -> None:
        """Convenience helper to lock PLC, Robot, and Station simultaneously for a running AUTO mission."""
        self.lock_device("STATION", locked_by="AUTO_MISSION", mission_id=mission_id, reason=reason)
        self.lock_device("PLC01", locked_by="AUTO_MISSION", mission_id=mission_id, reason=reason)
        self.lock_device("ROBOT01", locked_by="AUTO_MISSION", mission_id=mission_id, reason=reason)

    def unlock_station(self) -> None:
        """Convenience helper to release locks on PLC, Robot, and Station when mission finishes/aborts."""
        self.unlock_device("STATION")
        self.unlock_device("PLC01")
        self.unlock_device("ROBOT01")

    def is_device_locked(self, device_name: str) -> bool:
        dev = device_name.upper().strip()
        # If the whole station is locked, any component device is also considered locked
        if self._locks.get("STATION", {}).get("locked"):
            return True
        return self._locks.get(dev, {}).get("locked", False)

    def is_station_busy(self) -> bool:
        return self._locks.get("STATION", {}).get("locked", False)

    def get_locking_mission_id(self, device_name: str = "STATION") -> Optional[int]:
        dev = device_name.upper().strip()
        st_lock = self._locks.get("STATION", {})
        if st_lock.get("locked") and st_lock.get("mission_id"):
            return st_lock.get("mission_id")
        return self._locks.get(dev, {}).get("mission_id")

    def get_lock_description(self, device_name: str = "STATION") -> str:
        dev = device_name.upper().strip()
        lock = self._locks.get("STATION") if self._locks.get("STATION", {}).get("locked") else self._locks.get(dev, {})
        if not lock or not lock.get("locked"):
            return ""
        locked_by = lock.get("locked_by") or "Hệ thống"
        mission_id = lock.get("mission_id")
        reason = lock.get("reason")
        if mission_id:
            return f"{locked_by} (Nhiệm vụ #{mission_id})"
        return f"{locked_by} ({reason})" if reason else str(locked_by)

    def get_lock_status(self) -> Dict[str, Any]:
        return {
            "station_locked": self.is_station_busy(),
            "station_locking_mission_id": self.get_locking_mission_id("STATION"),
            "station_lock_description": self.get_lock_description("STATION"),
            "devices": self._locks,
        }


device_lock_manager = DeviceLockManager.get_instance()

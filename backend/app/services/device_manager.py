import logging
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import DeviceCommandLogRecord, DeviceRecord, SystemLogRecord
from app.models.schemas import DeviceHeartbeatRequest, DeviceRegisterRequest, DeviceStatus, DeviceType

logger = logging.getLogger(__name__)

# Timeout threshold for offline status (e.g. 15 seconds)
HEARTBEAT_TIMEOUT_SECONDS = 15


class DeviceManager:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_command(
        self,
        device: str,
        command: str,
        target: Optional[str] = None,
        result: str = "SUCCESS",
        message: str = "",
    ) -> DeviceCommandLogRecord:
        """Create a DeviceCommandLog record for tracking manual device actions."""
        log_entry = DeviceCommandLogRecord(
            device=device,
            command=command,
            target=target,
            timestamp=datetime.utcnow(),
            result=result,
            message=message,
        )
        self.session.add(log_entry)
        await self.session.commit()
        await self.session.refresh(log_entry)
        return log_entry

    async def get_command_logs(self, limit: int = 50) -> List[DeviceCommandLogRecord]:
        """Fetch latest device command execution logs."""
        stmt = select(DeviceCommandLogRecord).order_by(DeviceCommandLogRecord.id.desc()).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def register_device(self, req: DeviceRegisterRequest) -> DeviceRecord:
        """Register a device in the LAN network or update its IP/Status if it exists."""
        stmt = select(DeviceRecord).where(DeviceRecord.device_name == req.name)
        res = await self.session.execute(stmt)
        device = res.scalar_one_or_none()

        now = datetime.utcnow()
        if device:
            device.ip_address = req.ip
            device.device_type = req.type.value
            device.status = DeviceStatus.ONLINE.value
            device.last_heartbeat = now
            if req.port is not None:
                device.port = req.port
            if req.simulator_mode is not None:
                device.simulator_mode = req.simulator_mode
            if req.rack is not None:
                device.rack = req.rack
            if req.slot is not None:
                device.slot = req.slot
            if req.db_number is not None:
                device.db_number = req.db_number
            logger.info("Device re-registered: %s (%s) at IP %s:%d", req.name, req.type.value, req.ip, device.port)
        else:
            default_port = 14550 if req.type == DeviceType.UAV else (102 if req.type == DeviceType.PLC else (8090 if req.type == DeviceType.ROBOT else 80))
            device = DeviceRecord(
                device_name=req.name,
                device_type=req.type.value,
                ip_address=req.ip,
                port=req.port or default_port,
                simulator_mode=req.simulator_mode if req.simulator_mode is not None else False,
                rack=req.rack or 0,
                slot=req.slot or 1,
                db_number=req.db_number or 15,
                status=DeviceStatus.ONLINE.value,
                last_heartbeat=now,
                created_at=now,
            )
            self.session.add(device)
            logger.info("New device registered: %s (%s) at IP %s:%d", req.name, req.type.value, req.ip, device.port)

        log_entry = SystemLogRecord(
            log_type="DEVICE_LOG",
            source="SERVER",
            message=f"Device registered: {req.name} ({req.type.value}) at IP {req.ip}:{device.port}",
            created_at=now,
        )
        self.session.add(log_entry)
        await self.session.commit()
        await self.session.refresh(device)
        return device

    async def update_device_config(
        self,
        name: str,
        ip_address: Optional[str] = None,
        port: Optional[int] = None,
        simulator_mode: Optional[bool] = None,
        rack: Optional[int] = None,
        slot: Optional[int] = None,
        db_number: Optional[int] = None,
    ) -> Optional[DeviceRecord]:
        """Update hardware connection settings for a device and propagate to live managers."""
        stmt = select(DeviceRecord).where(DeviceRecord.device_name == name)
        res = await self.session.execute(stmt)
        device = res.scalar_one_or_none()

        if not device:
            return None

        if ip_address is not None:
            device.ip_address = ip_address
        if port is not None:
            device.port = port
        if simulator_mode is not None:
            device.simulator_mode = simulator_mode
        if rack is not None:
            device.rack = rack
        if slot is not None:
            device.slot = slot
        if db_number is not None:
            device.db_number = db_number

        # Propagate changes to singleton services
        dev_type = device.device_type.upper()
        if dev_type == "ROBOT":
            from app.services.robot_manager import RobotManager
            RobotManager.get_instance().update_config(
                robot_ip=device.ip_address,
                robot_port=device.port,
                simulator_mode=device.simulator_mode,
            )
        elif dev_type == "PLC":
            from app.services.plc_manager import PLCManager
            PLCManager.get_instance().update_config(
                plc_ip=device.ip_address,
                rack=device.rack,
                slot=device.slot,
                db_number=device.db_number,
                simulator_mode=device.simulator_mode,
            )
        elif dev_type == "CAMERA":
            from app.services.camera_manager import CameraManager
            CameraManager.get_instance().update_config(
                simulator_mode=device.simulator_mode,
            )
        elif dev_type == "UAV":
            from app.services.fleet_manager import fleet_manager
            uav_unit = fleet_manager.get_uav(device.device_name)
            if uav_unit:
                uav_unit.is_real = not device.simulator_mode


        now = datetime.utcnow()
        self.session.add(
            SystemLogRecord(
                log_type="DEVICE_LOG",
                source="SERVER",
                message=f"Device config updated: {name} -> IP {device.ip_address}:{device.port} (Sim: {device.simulator_mode})",
                created_at=now,
            )
        )
        await self.session.commit()
        await self.session.refresh(device)
        return device


    async def update_heartbeat(self, req: DeviceHeartbeatRequest) -> Optional[DeviceRecord]:
        """Update device heartbeat and set status."""
        stmt = select(DeviceRecord).where(DeviceRecord.device_name == req.name)
        res = await self.session.execute(stmt)
        device = res.scalar_one_or_none()

        if not device:
            logger.warning("Heartbeat received for unregistered device: %s", req.name)
            return None

        device.last_heartbeat = datetime.utcnow()
        device.status = req.status.value
        await self.session.commit()
        await self.session.refresh(device)
        return device

    async def check_device_timeouts(self) -> List[str]:
        """Scan all devices and mark any device as OFFLINE if last_heartbeat > 15s ago."""
        threshold = datetime.utcnow() - timedelta(seconds=HEARTBEAT_TIMEOUT_SECONDS)
        stmt = select(DeviceRecord).where(
            DeviceRecord.status == DeviceStatus.ONLINE.value,
            DeviceRecord.last_heartbeat < threshold,
        )
        res = await self.session.execute(stmt)
        timed_out_devices = res.scalars().all()

        offline_names = []
        for dev in timed_out_devices:
            dev.status = DeviceStatus.OFFLINE.value
            offline_names.append(dev.device_name)
            logger.warning("Device heartbeat timeout: %s marked OFFLINE", dev.device_name)
            self.session.add(
                SystemLogRecord(
                    log_type="DEVICE_LOG",
                    source="SERVER",
                    message=f"Device heartbeat timeout: {dev.device_name} marked OFFLINE",
                    created_at=datetime.utcnow(),
                )
            )

        if timed_out_devices:
            await self.session.commit()

        return offline_names

    async def get_all_devices(self) -> List[DeviceRecord]:
        """Retrieve list of all registered devices."""
        stmt = select(DeviceRecord).order_by(DeviceRecord.id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def remove_device(self, name: str) -> None:
        """Remove a device record by name if it exists."""
        stmt = select(DeviceRecord).where(DeviceRecord.device_name == name)
        res = await self.session.execute(stmt)
        device = res.scalar_one_or_none()
        if device:
            await self.session.delete(device)
            await self.session.commit()
            logger.info("Removed device record: %s", name)

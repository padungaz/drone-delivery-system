import logging
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import DeviceRecord, SystemLogRecord
from app.models.schemas import DeviceHeartbeatRequest, DeviceRegisterRequest, DeviceStatus

logger = logging.getLogger(__name__)

# Timeout threshold for offline status (e.g. 15 seconds)
HEARTBEAT_TIMEOUT_SECONDS = 15


class DeviceManager:
    def __init__(self, session: AsyncSession):
        self.session = session

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
            logger.info("Device re-registered: %s (%s) at IP %s", req.name, req.type.value, req.ip)
        else:
            device = DeviceRecord(
                device_name=req.name,
                device_type=req.type.value,
                ip_address=req.ip,
                status=DeviceStatus.ONLINE.value,
                last_heartbeat=now,
                created_at=now,
            )
            self.session.add(device)
            logger.info("New device registered: %s (%s) at IP %s", req.name, req.type.value, req.ip)

        log_entry = SystemLogRecord(
            log_type="DEVICE_LOG",
            source="SERVER",
            message=f"Device registered: {req.name} ({req.type.value}) at IP {req.ip}",
            created_at=now,
        )
        self.session.add(log_entry)
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

import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.database import (
    Base,
    DroneStatusRecord,
    ErrorLogRecord,
    LandingResultRecord,
    MissionHistoryRecord,
    TelemetryLogRecord,
)
from app.models.schemas import DroneState, MissionCommand, TelemetryPayload

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized")


class Repository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_drone_status(self, telemetry: TelemetryPayload) -> None:
        result = await self.session.execute(
            select(DroneStatusRecord).where(DroneStatusRecord.drone_id == telemetry.drone_id)
        )
        record = result.scalar_one_or_none()
        if record is None:
            record = DroneStatusRecord(drone_id=telemetry.drone_id)
            self.session.add(record)

        record.connected = True
        record.drone_state = telemetry.drone_state.value
        record.latitude = telemetry.latitude
        record.longitude = telemetry.longitude
        record.altitude_relative = telemetry.altitude_relative
        record.altitude_agl = telemetry.altitude_agl
        record.battery = telemetry.battery
        record.ground_speed = telemetry.ground_speed
        record.heading = telemetry.heading
        record.gps_satellite = telemetry.gps_satellite
        record.flight_mode = telemetry.flight_mode
        record.aruco_detected = telemetry.aruco_detected
        record.landing_status = telemetry.landing_status
        record.armed = telemetry.armed
        record.updated_at = datetime.utcnow()
        await self.session.commit()

    async def log_telemetry(self, telemetry: TelemetryPayload) -> None:
        self.session.add(
            TelemetryLogRecord(
                drone_id=telemetry.drone_id,
                timestamp=telemetry.timestamp,
                payload_json=telemetry.model_dump_json(),
            )
        )
        await self.session.commit()

    async def create_mission(self, command: MissionCommand) -> MissionHistoryRecord:
        record = MissionHistoryRecord(
            drone_id=command.drone_id,
            action=command.action.value,
            home_lat=command.home_lat,
            home_lon=command.home_lon,
            pickup_lat=command.pickup_lat,
            pickup_lon=command.pickup_lon,
            drop_lat=command.drop_lat,
            drop_lon=command.drop_lon,
            status="SENT",
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def update_mission_status(self, mission_id: int, status: str) -> None:
        result = await self.session.execute(
            select(MissionHistoryRecord).where(MissionHistoryRecord.id == mission_id)
        )
        record = result.scalar_one_or_none()
        if record:
            record.status = status
            await self.session.commit()

    async def get_drone_status(self, drone_id: str) -> Optional[DroneStatusRecord]:
        result = await self.session.execute(
            select(DroneStatusRecord).where(DroneStatusRecord.drone_id == drone_id)
        )
        return result.scalar_one_or_none()

    async def get_mission_history(self, limit: int = 50) -> list[MissionHistoryRecord]:
        result = await self.session.execute(
            select(MissionHistoryRecord).order_by(MissionHistoryRecord.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def log_error(self, drone_id: str, source: str, message: str) -> None:
        self.session.add(
            ErrorLogRecord(drone_id=drone_id, source=source, message=message)
        )
        await self.session.commit()

    async def log_landing_result(
        self,
        drone_id: str,
        location_type: str,
        success: bool,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        mission_id: Optional[int] = None,
    ) -> None:
        self.session.add(
            LandingResultRecord(
                drone_id=drone_id,
                mission_id=mission_id,
                location_type=location_type,
                success=success,
                offset_x=offset_x,
                offset_y=offset_y,
            )
        )
        await self.session.commit()

    async def mark_drone_disconnected(self, drone_id: str) -> None:
        result = await self.session.execute(
            select(DroneStatusRecord).where(DroneStatusRecord.drone_id == drone_id)
        )
        record = result.scalar_one_or_none()
        if record:
            record.connected = False
            await self.session.commit()


def can_stop_drone(state: str, armed: bool) -> bool:
    return state == DroneState.LAND.value and not armed

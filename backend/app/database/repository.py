import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.database import (
    Base,
    CustomerAddressRecord,
    CustomerRecord,
    DeliveryRequestRecord,
    DroneStatusRecord,
    ErrorLogRecord,
    LandingResultRecord,
    MissionHistoryRecord,
    TelemetryLogRecord,
    WarehouseConfigRecord,
)
from app.models.schemas import DroneState, MissionCommand, TelemetryPayload

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Tune SQLite performance: WAL mode, safe sync, and lock timeout."""
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.close()
    except Exception as exc:
        logger.debug("Could not set SQLite PRAGMA: %s", exc)


async def init_db() -> None:
    # Ensure all ORM models are registered with Base.metadata
    import app.models.database  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Lightweight auto-migration: add missing columns
        await _migrate_storage_slots(conn)
        await _migrate_devices(conn)
        await _migrate_intralogistics_missions(conn)

    logger.info("Database initialized (WAL mode enabled)")


async def _migrate_intralogistics_missions(conn) -> None:
    """Add missing columns to intralogistics_missions table."""
    def _sync_migrate(sync_conn):
        raw = sync_conn.connection.dbapi_connection
        cursor = raw.cursor()
        cursor.execute("PRAGMA table_info(intralogistics_missions)")
        existing_cols = {row[1] for row in cursor.fetchall()}

        if existing_cols:
            if "order_id" not in existing_cols:
                cursor.execute("ALTER TABLE intralogistics_missions ADD COLUMN order_id INTEGER")
                logger.info("Migrated intralogistics_missions: added column 'order_id'")
            if "status" not in existing_cols:
                cursor.execute("ALTER TABLE intralogistics_missions ADD COLUMN status VARCHAR(32) DEFAULT 'WAITING'")
                logger.info("Migrated intralogistics_missions: added column 'status'")
            if "current_phase" not in existing_cols:
                cursor.execute("ALTER TABLE intralogistics_missions ADD COLUMN current_phase VARCHAR(64) DEFAULT 'WAITING'")
                logger.info("Migrated intralogistics_missions: added column 'current_phase'")
            if "priority" not in existing_cols:
                cursor.execute("ALTER TABLE intralogistics_missions ADD COLUMN priority INTEGER DEFAULT 0")
                logger.info("Migrated intralogistics_missions: added column 'priority'")
            if "error_reason" not in existing_cols:
                cursor.execute("ALTER TABLE intralogistics_missions ADD COLUMN error_reason TEXT")
                logger.info("Migrated intralogistics_missions: added column 'error_reason'")
            if "started_at" not in existing_cols:
                cursor.execute("ALTER TABLE intralogistics_missions ADD COLUMN started_at DATETIME")
                logger.info("Migrated intralogistics_missions: added column 'started_at'")
            if "completed_at" not in existing_cols:
                cursor.execute("ALTER TABLE intralogistics_missions ADD COLUMN completed_at DATETIME")
                logger.info("Migrated intralogistics_missions: added column 'completed_at'")

    await conn.run_sync(_sync_migrate)



async def _migrate_devices(conn) -> None:
    """Add missing columns to devices table."""
    def _sync_migrate(sync_conn):
        raw = sync_conn.connection.dbapi_connection
        cursor = raw.cursor()
        cursor.execute("PRAGMA table_info(devices)")
        existing_cols = {row[1] for row in cursor.fetchall()}

        if existing_cols:
            if "error_code" not in existing_cols:
                cursor.execute("ALTER TABLE devices ADD COLUMN error_code VARCHAR(64)")
                logger.info("Migrated devices: added column 'error_code'")
            if "port" not in existing_cols:
                cursor.execute("ALTER TABLE devices ADD COLUMN port INTEGER DEFAULT 8090")
                logger.info("Migrated devices: added column 'port'")
            if "simulator_mode" not in existing_cols:
                cursor.execute("ALTER TABLE devices ADD COLUMN simulator_mode BOOLEAN DEFAULT 0")
                logger.info("Migrated devices: added column 'simulator_mode'")
            if "rack" not in existing_cols:
                cursor.execute("ALTER TABLE devices ADD COLUMN rack INTEGER DEFAULT 0")
                logger.info("Migrated devices: added column 'rack'")
            if "slot" not in existing_cols:
                cursor.execute("ALTER TABLE devices ADD COLUMN slot INTEGER DEFAULT 1")
                logger.info("Migrated devices: added column 'slot'")
            if "db_number" not in existing_cols:
                cursor.execute("ALTER TABLE devices ADD COLUMN db_number INTEGER DEFAULT 15")
                logger.info("Migrated devices: added column 'db_number'")

    await conn.run_sync(_sync_migrate)




async def _migrate_storage_slots(conn) -> None:
    """Add missing columns to storage_slots (works for both old→new and new→old schemas)."""

    def _sync_migrate(sync_conn):
        raw = sync_conn.connection.dbapi_connection
        cursor = raw.cursor()
        cursor.execute("PRAGMA table_info(storage_slots)")
        existing_cols = {row[1] for row in cursor.fetchall()}

        # All columns that should exist in the unified model
        migrations = [
            # Legacy columns (may be missing if DB was created by the new-only model)
            ("is_empty", "BOOLEAN DEFAULT 1"),
            ("sender_name", "VARCHAR(128)"),
            ("sender_address", "VARCHAR(256)"),
            ("item_created_at", "DATETIME"),
            # Smart Intralogistics columns (may be missing if DB was created by old model)
            ("slot_name", "VARCHAR(16)"),
            ("status", "VARCHAR(32) DEFAULT 'EMPTY'"),
            ("product_id", "VARCHAR(64)"),
            ("updated_time", "DATETIME"),
        ]
        for col_name, col_type in migrations:
            if col_name not in existing_cols:
                cursor.execute(f"ALTER TABLE storage_slots ADD COLUMN {col_name} {col_type}")
                logger.info("Migrated storage_slots: added column '%s'", col_name)

    await conn.run_sync(_sync_migrate)


async def get_session():
    async with async_session() as session:
        yield session



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
    return not armed and state != DroneState.IDLE.value


# ---------------------------------------------------------------------------
# Customer repository — standalone functions (used in customer_routes)
# ---------------------------------------------------------------------------

class CustomerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Warehouse Config ────────────────────────────────────────────────────

    async def get_warehouse(self) -> Optional[WarehouseConfigRecord]:
        result = await self.session.execute(
            select(WarehouseConfigRecord).limit(1)
        )
        return result.scalar_one_or_none()

    async def upsert_warehouse(
        self,
        name: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        address_text: Optional[str] = None,
    ) -> WarehouseConfigRecord:
        record = await self.get_warehouse()
        if record is None:
            record = WarehouseConfigRecord()
            self.session.add(record)

        if name is not None:
            record.name = name
        if latitude is not None:
            record.latitude = latitude
        if longitude is not None:
            record.longitude = longitude
        if address_text is not None:
            record.address_text = address_text
        record.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(record)
        return record

    # ── Customer ────────────────────────────────────────────────────────────

    async def get_or_create_customer(self, name: str, phone: str) -> CustomerRecord:
        result = await self.session.execute(
            select(CustomerRecord).where(CustomerRecord.phone == phone)
        )
        record = result.scalar_one_or_none()
        if record is None:
            record = CustomerRecord(name=name, phone=phone)
            self.session.add(record)
            await self.session.commit()
            await self.session.refresh(record)
        else:
            # Update name if changed
            if record.name != name:
                record.name = name
                await self.session.commit()
        return record

    async def get_customer_by_phone(self, phone: str) -> Optional[CustomerRecord]:
        result = await self.session.execute(
            select(CustomerRecord).where(CustomerRecord.phone == phone)
        )
        return result.scalar_one_or_none()

    # ── Customer Addresses ──────────────────────────────────────────────────

    async def create_address(
        self,
        customer_id: int,
        address_type: str,
        address_name: str,
        address_text: str,
        latitude: float,
        longitude: float,
    ) -> CustomerAddressRecord:
        record = CustomerAddressRecord(
            customer_id=customer_id,
            address_type=address_type,
            address_name=address_name,
            address_text=address_text,
            latitude=latitude,
            longitude=longitude,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def get_addresses(
        self,
        customer_id: int,
        address_type: Optional[str] = None,
    ) -> list[CustomerAddressRecord]:
        q = select(CustomerAddressRecord).where(
            CustomerAddressRecord.customer_id == customer_id
        )
        if address_type:
            q = q.where(CustomerAddressRecord.address_type == address_type)
        result = await self.session.execute(q.order_by(CustomerAddressRecord.created_at.desc()))
        return list(result.scalars().all())

    async def get_address(self, address_id: int) -> Optional[CustomerAddressRecord]:
        result = await self.session.execute(
            select(CustomerAddressRecord).where(CustomerAddressRecord.id == address_id)
        )
        return result.scalar_one_or_none()

    async def update_address(
        self,
        address_id: int,
        **kwargs,
    ) -> Optional[CustomerAddressRecord]:
        record = await self.get_address(address_id)
        if record is None:
            return None
        for field, value in kwargs.items():
            if value is not None and hasattr(record, field):
                setattr(record, field, value)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def delete_address(self, address_id: int) -> bool:
        record = await self.get_address(address_id)
        if record is None:
            return False
        await self.session.delete(record)
        await self.session.commit()
        return True

    # ── Delivery Requests ───────────────────────────────────────────────────

    async def create_delivery_request(
        self,
        customer_id: int,
        customer_name: str,
        customer_phone: str,
        delivery_type: str,
        pickup_lat: float,
        pickup_lon: float,
        pickup_address: str,
        drop_lat: float,
        drop_lon: float,
        drop_address: str,
        note: str = "",
    ) -> DeliveryRequestRecord:
        record = DeliveryRequestRecord(
            customer_id=customer_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            delivery_type=delivery_type,
            pickup_lat=pickup_lat,
            pickup_lon=pickup_lon,
            pickup_address=pickup_address,
            drop_lat=drop_lat,
            drop_lon=drop_lon,
            drop_address=drop_address,
            note=note,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def get_delivery_requests(
        self,
        customer_phone: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[DeliveryRequestRecord]:
        q = select(DeliveryRequestRecord).order_by(DeliveryRequestRecord.created_at.desc())
        if customer_phone:
            q = q.where(DeliveryRequestRecord.customer_phone == customer_phone)
        if status:
            q = q.where(DeliveryRequestRecord.status == status)
        result = await self.session.execute(q.limit(limit))
        return list(result.scalars().all())

    async def get_delivery_request(self, request_id: int) -> Optional[DeliveryRequestRecord]:
        result = await self.session.execute(
            select(DeliveryRequestRecord).where(DeliveryRequestRecord.id == request_id)
        )
        return result.scalar_one_or_none()

    async def update_delivery_request_status(
        self,
        request_id: int,
        status: str,
        note: Optional[str] = None,
        mission_id: Optional[int] = None,
    ) -> Optional[DeliveryRequestRecord]:
        record = await self.get_delivery_request(request_id)
        if record is None:
            return None
        record.status = status
        record.updated_at = datetime.utcnow()
        if note is not None:
            record.note = note
        if mission_id is not None:
            record.mission_id = mission_id
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def delete_delivery_request(self, request_id: int) -> bool:
        record = await self.get_delivery_request(request_id)
        if record is None:
            return False
        await self.session.delete(record)
        await self.session.commit()
        return True


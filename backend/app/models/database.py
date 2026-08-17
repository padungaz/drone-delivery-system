from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DroneStatusRecord(Base):
    __tablename__ = "drone_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    drone_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    connected: Mapped[bool] = mapped_column(Boolean, default=False)
    drone_state: Mapped[str] = mapped_column(String(32), default="IDLE")
    latitude: Mapped[float] = mapped_column(Float, default=0.0)
    longitude: Mapped[float] = mapped_column(Float, default=0.0)
    altitude_relative: Mapped[float] = mapped_column(Float, default=0.0)
    altitude_agl: Mapped[float] = mapped_column(Float, default=0.0)
    battery: Mapped[float] = mapped_column(Float, default=100.0)
    ground_speed: Mapped[float] = mapped_column(Float, default=0.0)
    heading: Mapped[float] = mapped_column(Float, default=0.0)
    gps_satellite: Mapped[int] = mapped_column(Integer, default=0)
    flight_mode: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    aruco_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    landing_status: Mapped[str] = mapped_column(String(32), default="NONE")
    armed: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MissionHistoryRecord(Base):
    __tablename__ = "mission_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    drone_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(32))
    home_lat: Mapped[float] = mapped_column(Float)
    home_lon: Mapped[float] = mapped_column(Float)
    pickup_lat: Mapped[float] = mapped_column(Float)
    pickup_lon: Mapped[float] = mapped_column(Float)
    drop_lat: Mapped[float] = mapped_column(Float)
    drop_lon: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TelemetryLogRecord(Base):
    __tablename__ = "telemetry_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    drone_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    payload_json: Mapped[str] = mapped_column(Text)


class LandingResultRecord(Base):
    __tablename__ = "landing_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    drone_id: Mapped[str] = mapped_column(String(64), index=True)
    mission_id: Mapped[int] = mapped_column(Integer, nullable=True)
    location_type: Mapped[str] = mapped_column(String(16))
    success: Mapped[bool] = mapped_column(Boolean)
    offset_x: Mapped[float] = mapped_column(Float, default=0.0)
    offset_y: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ErrorLogRecord(Base):
    __tablename__ = "error_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    drone_id: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Customer-facing tables (new)
# ---------------------------------------------------------------------------

class WarehouseConfigRecord(Base):
    """Single-row table for warehouse location config. id is always 1."""
    __tablename__ = "warehouse_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), default="Main Warehouse")
    latitude: Mapped[float] = mapped_column(Float, default=16.0544)
    longitude: Mapped[float] = mapped_column(Float, default=108.2022)
    address_text: Mapped[str] = mapped_column(String(256), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CustomerRecord(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    phone: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CustomerAddressRecord(Base):
    __tablename__ = "customer_addresses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), index=True)
    # "RECEIVE" = địa chỉ nhận đồ, "SEND" = địa chỉ gửi đồ
    address_type: Mapped[str] = mapped_column(String(16), default="RECEIVE")
    address_name: Mapped[str] = mapped_column(String(128))   # VD: "Nhà", "Công ty"
    address_text: Mapped[str] = mapped_column(String(256))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DeliveryRequestRecord(Base):
    __tablename__ = "delivery_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), index=True)
    customer_name: Mapped[str] = mapped_column(String(128))
    customer_phone: Mapped[str] = mapped_column(String(32))
    # "RECEIVE_FROM_WAREHOUSE" or "SEND_TO_WAREHOUSE"
    delivery_type: Mapped[str] = mapped_column(String(32))
    pickup_lat: Mapped[float] = mapped_column(Float)
    pickup_lon: Mapped[float] = mapped_column(Float)
    pickup_address: Mapped[str] = mapped_column(String(256), default="")
    drop_lat: Mapped[float] = mapped_column(Float)
    drop_lon: Mapped[float] = mapped_column(Float)
    drop_address: Mapped[str] = mapped_column(String(256), default="")
    # PENDING → APPROVED → FLYING → DELIVERED / FAILED / REJECTED
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    # linked mission_history id (set when Admin starts mission)
    mission_id: Mapped[int] = mapped_column(Integer, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Smart Intralogistics System Tables (UAV + PLC + FAIRINO Robot + Storage)
# ---------------------------------------------------------------------------

class DeviceRecord(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    device_type: Mapped[str] = mapped_column(String(32))  # "UAV", "PLC", "ROBOT", "CAMERA"
    ip_address: Mapped[str] = mapped_column(String(64))
    port: Mapped[int] = mapped_column(Integer, default=8090)
    simulator_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    rack: Mapped[int] = mapped_column(Integer, default=0)
    slot: Mapped[int] = mapped_column(Integer, default=1)
    db_number: Mapped[int] = mapped_column(Integer, default=15)
    status: Mapped[str] = mapped_column(String(32), default="OFFLINE")  # "CONNECTED", "DISCONNECTED", "ONLINE", "OFFLINE", "BUSY", "ERROR"
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default=None)
    last_heartbeat: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)



class DeviceCommandLogRecord(Base):
    __tablename__ = "device_command_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device: Mapped[str] = mapped_column(String(64), index=True)  # e.g. "PLC01", "ROBOT01", "CAM01"
    command: Mapped[str] = mapped_column(String(64), index=True) # e.g. "LOCK_DRONE", "MOVE_HOME", "PICK"
    target: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default=None)  # e.g. "A1", "PAD"
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    result: Mapped[str] = mapped_column(String(32), default="SUCCESS")  # "SUCCESS", "FAILED", "DONE"
    message: Mapped[str] = mapped_column(Text, default="")




class ProductRecord(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    product_name: Mapped[str] = mapped_column(String(128))
    qr_code: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="IN_STOCK")  # "IN_STOCK", "IN_TRANSIT", "DELIVERED"
    current_slot: Mapped[str] = mapped_column(String(16), nullable=True)  # e.g. "B2"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class IntralogisticsMissionRecord(Base):
    __tablename__ = "intralogistics_missions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("delivery_requests.id"), nullable=True, index=True)
    mission_type: Mapped[str] = mapped_column(String(32))  # "DRONE_PICKUP" or "DRONE_DELIVERY"
    drone_id: Mapped[str] = mapped_column(String(64), default="UAV01")
    product_id: Mapped[str] = mapped_column(String(64))
    target_slot: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="WAITING")  # "WAITING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"
    current_phase: Mapped[str] = mapped_column(String(64), default="WAITING")
    state: Mapped[str] = mapped_column(String(64), default="WAITING")  # Backward compatibility alias for status
    priority: Mapped[int] = mapped_column(Integer, default=0)
    error_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    step_details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)




class SystemLogRecord(Base):
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    log_type: Mapped[str] = mapped_column(String(32), index=True)  # "SYSTEM_LOG", "MISSION_LOG", "DEVICE_LOG", "ERROR_LOG"
    source: Mapped[str] = mapped_column(String(32), index=True)    # "PLC", "ROBOT", "UAV", "SERVER", "CAMERA"
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StorageSlotRecord(Base):
    """Represents a physical storage slot in the warehouse (1..9)."""

    __tablename__ = "storage_slots"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    is_empty: Mapped[bool] = mapped_column(Boolean, default=True)
    qr_code: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, default=None)
    sender_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, default=None)
    sender_address: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, default=None)
    item_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)

    slot_name: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, unique=True, index=True)  # A1..C3
    status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, default="EMPTY")
    product_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    updated_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)




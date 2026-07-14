from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
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

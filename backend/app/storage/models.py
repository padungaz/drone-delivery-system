from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class StorageSlotRecord(Base):
    """Represents a physical storage slot in the warehouse (1..9)."""

    __tablename__ = "storage_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    is_empty: Mapped[bool] = mapped_column(Boolean, default=True)
    qr_code: Mapped[str] = mapped_column(String(512), nullable=True, default=None)
    sender_name: Mapped[str] = mapped_column(String(128), nullable=True, default=None)
    sender_address: Mapped[str] = mapped_column(String(256), nullable=True, default=None)
    item_created_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, default=None)

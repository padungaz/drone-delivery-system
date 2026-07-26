from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class StorageSlotRecord(Base):
    """Represents a physical storage slot in the warehouse (1..9).

    This model serves both:
    - Legacy frontend API (uses: is_empty, sender_name, sender_address, qr_code)
    - Smart Intralogistics system (uses: slot_name, status, product_id)
    """

    __tablename__ = "storage_slots"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)

    # ── Legacy columns (used by StorageRepository + frontend) ────────────
    is_empty: Mapped[bool] = mapped_column(Boolean, default=True)
    qr_code: Mapped[str] = mapped_column(String(512), nullable=True, default=None)
    sender_name: Mapped[str] = mapped_column(String(128), nullable=True, default=None)
    sender_address: Mapped[str] = mapped_column(String(256), nullable=True, default=None)
    item_created_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, default=None)

    # ── Smart Intralogistics columns (used by InventoryManager) ──────────
    slot_name: Mapped[str] = mapped_column(String(16), nullable=True, unique=True, index=True)  # A1..C3
    status: Mapped[str] = mapped_column(String(32), nullable=True, default="EMPTY")  # EMPTY, OCCUPIED, RESERVED
    product_id: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    updated_time: Mapped[datetime] = mapped_column(DateTime, nullable=True, default=None)


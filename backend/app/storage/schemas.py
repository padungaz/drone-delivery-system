from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class StorageItem(BaseModel):
    """Thông tin hàng hóa được lưu trong một ô kho."""

    qr_code: Optional[str] = Field(None, alias="qrCode")
    sender_name: Optional[str] = Field(None, alias="senderName")
    sender_address: Optional[str] = Field(None, alias="senderAddress")
    created_at: Optional[datetime] = Field(None, alias="createdAt")

    model_config = {"populate_by_name": True}


class StorageSlotResponse(BaseModel):
    """Thông tin một ô kho (phản hồi cho frontend)."""

    id: int
    is_empty: bool = Field(..., alias="isEmpty")
    item: Optional[StorageItem] = None

    model_config = {"populate_by_name": True}


class StorageStateResponse(BaseModel):
    """Trạng thái toàn bộ 9 ô kho."""

    total_slots: int = Field(9, alias="totalSlots")
    slots: list[StorageSlotResponse]

    model_config = {"populate_by_name": True}


class QRScanPayload(BaseModel):
    """Dữ liệu QR code được camera quét và gửi lên server."""

    sender_name: str = Field(..., alias="senderName", min_length=1)
    address: str = Field(..., min_length=1)
    qr_code: Optional[str] = Field(None, alias="qrCode")

    model_config = {"populate_by_name": True}

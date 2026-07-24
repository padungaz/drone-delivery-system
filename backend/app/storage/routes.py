import logging

from fastapi import APIRouter, Depends, HTTPException

from app.database.repository import async_session
from app.storage.qr_scanner import parse_qr_data
from app.storage.repository import StorageRepository
from app.storage.schemas import QRScanPayload, StorageStateResponse
from app.websocket.handler import manager

logger = logging.getLogger(__name__)
storage_router = APIRouter(prefix="/storage", tags=["Storage"])


async def get_storage_repo():
    async with async_session() as session:
        yield StorageRepository(session)


async def _broadcast_storage_state(repo: StorageRepository) -> None:
    """Build current storage state and broadcast to all WebSocket clients."""
    slots = await repo.get_all_slots()
    state = repo.build_storage_state(slots)
    await manager.broadcast_to_clients({
        "type": "storage_update",
        "payload": state.model_dump(mode="json", by_alias=True),
    })


# ── GET /storage ─────────────────────────────────────────────────────────────


@storage_router.get("", response_model=StorageStateResponse)
async def get_storage_state(repo: StorageRepository = Depends(get_storage_repo)):
    """Trả về trạng thái toàn bộ 9 ô kho."""
    slots = await repo.get_all_slots()
    return repo.build_storage_state(slots)


# ── POST /storage/scan ───────────────────────────────────────────────────────


@storage_router.post("/scan")
async def scan_qr_and_store(
    payload: QRScanPayload,
    repo: StorageRepository = Depends(get_storage_repo),
):
    """Nhận dữ liệu QR từ camera kho, tìm ô trống đầu tiên và lưu hàng.

    Trả lỗi 400 nếu kho đã đầy (9/9 ô đều có hàng).
    """
    # Validate QR data
    parsed = parse_qr_data(payload.model_dump(by_alias=True))
    if parsed is None:
        raise HTTPException(status_code=400, detail="Dữ liệu QR không hợp lệ")

    # Find first empty slot
    slot = await repo.find_first_empty_slot()
    if slot is None:
        raise HTTPException(
            status_code=400,
            detail="Kho đã đầy! Tất cả 9 ô kho đều đã có hàng.",
        )

    # Assign item to slot
    updated_slot = await repo.assign_item_to_slot(slot, parsed)

    # Broadcast realtime update to all frontend clients
    await _broadcast_storage_state(repo)

    logger.info("QR scanned → item stored in slot #%d", updated_slot.id)
    return {
        "status": "success",
        "message": f"Hàng đã được lưu vào ô kho #{updated_slot.id}",
        "slot_id": updated_slot.id,
    }


# ── DELETE /storage/{slot_id} ────────────────────────────────────────────────


@storage_router.delete("/{slot_id}")
async def remove_item_from_slot(
    slot_id: int,
    repo: StorageRepository = Depends(get_storage_repo),
):
    """Lấy hàng ra khỏi kho — reset ô kho về trạng thái trống."""
    if slot_id < 1 or slot_id > 9:
        raise HTTPException(status_code=400, detail="slot_id phải từ 1 đến 9")

    slot = await repo.get_slot(slot_id)
    if slot is None:
        raise HTTPException(status_code=404, detail=f"Ô kho #{slot_id} không tồn tại")

    if slot.is_empty:
        raise HTTPException(
            status_code=400,
            detail=f"Ô kho #{slot_id} đang trống, không có hàng để lấy ra",
        )

    await repo.clear_slot(slot_id)

    # Broadcast realtime update to all frontend clients
    await _broadcast_storage_state(repo)

    logger.info("Item removed from slot #%d", slot_id)
    return {
        "status": "success",
        "message": f"Đã lấy hàng ra khỏi ô kho #{slot_id}",
        "slot_id": slot_id,
    }

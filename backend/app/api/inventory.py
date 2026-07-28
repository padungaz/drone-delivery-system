from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repository import get_session
from app.models.schemas import (
    StorageSlotResponse,
    StorageSlotUpdateRequest,
    QRScanPayload,
)
from app.services.inventory_manager import InventoryManager
from app.websocket.manager import system_ws_manager

inventory_router = APIRouter(prefix="/api/inventory", tags=["Warehouse Inventory Management"])


@inventory_router.get("", response_model=List[StorageSlotResponse])
@inventory_router.get("/slots", response_model=List[StorageSlotResponse])
async def get_inventory(session: AsyncSession = Depends(get_session)):
    mgr = InventoryManager(session)
    await mgr.init_default_slots()
    return await mgr.get_all_slots()


@inventory_router.post("/update", response_model=StorageSlotResponse)
async def update_inventory_slot(
    slot_name: str,
    req: StorageSlotUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    mgr = InventoryManager(session)
    updated = await mgr.update_slot(
        slot_name=slot_name,
        status=req.status,
        product_id=req.product_id,
        qr_code=req.qr_code,
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Storage slot {slot_name} not found")

    await system_ws_manager.broadcast("INVENTORY_STATUS", {
        "slot_name": updated.slot_name,
        "status": updated.status,
        "product_id": updated.product_id,
    })

    return updated


@inventory_router.post("/slots/{slot_id}/clear", response_model=StorageSlotResponse)
async def clear_inventory_slot(
    slot_id: int,
    session: AsyncSession = Depends(get_session),
):
    mgr = InventoryManager(session)
    cleared = await mgr.clear_slot_by_id(slot_id)
    if not cleared:
        raise HTTPException(status_code=404, detail=f"Storage slot ID {slot_id} not found")

    await system_ws_manager.broadcast("INVENTORY_STATUS", {
        "slot_name": cleared.slot_name,
        "status": cleared.status,
        "product_id": None,
    })

    return cleared


@inventory_router.post("/qr-scan", response_model=StorageSlotResponse)
async def qr_scan_product(
    payload: QRScanPayload,
    session: AsyncSession = Depends(get_session),
):
    mgr = InventoryManager(session)
    assigned_slot = await mgr.process_qr_scan(payload)
    if not assigned_slot:
        raise HTTPException(status_code=400, detail="Failed to process QR scan. Warehouse full or invalid product.")

    await system_ws_manager.broadcast("INVENTORY_STATUS", {
        "slot_name": assigned_slot.slot_name,
        "status": assigned_slot.status,
        "product_id": assigned_slot.product_id,
    })

    return assigned_slot

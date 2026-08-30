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
from app.services.qr_scanner_service import QRScannerService
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

    all_slots = await mgr.get_all_slots()
    slots_data = [
        StorageSlotResponse.model_validate(s, from_attributes=True).model_dump(mode="json")
        for s in all_slots
    ]
    await system_ws_manager.broadcast("INVENTORY_STATUS", slots_data)

    return updated


@inventory_router.post("/slots/{slot_id}/clear", response_model=StorageSlotResponse)
@inventory_router.delete("/slots/{slot_id}", response_model=StorageSlotResponse)
@inventory_router.delete("/slots/{slot_id}/clear", response_model=StorageSlotResponse, include_in_schema=False)
async def clear_inventory_slot(
    slot_id: str,
    session: AsyncSession = Depends(get_session),
):
    mgr = InventoryManager(session)
    cleared = await mgr.clear_slot(slot_id)
    if not cleared:
        raise HTTPException(status_code=404, detail=f"Storage slot '{slot_id}' not found")

    all_slots = await mgr.get_all_slots()
    slots_data = [
        StorageSlotResponse.model_validate(s, from_attributes=True).model_dump(mode="json")
        for s in all_slots
    ]
    await system_ws_manager.broadcast("INVENTORY_STATUS", slots_data)

    return cleared


@inventory_router.post("/qr-scan")
async def qr_scan_product(
    payload: QRScanPayload,
):
    """Scan QR code manually or via API, automatically allocating an available storage slot."""
    qr_service = QRScannerService.get_instance()
    res = await qr_service.process_qr_code(payload.qr, source="API_SCAN")
    if res.get("status") == "full":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res


@inventory_router.get("/camera-scan/status")
async def get_camera_scan_status():
    """Get status and statistics of the integrated backend camera QR scanner."""
    qr_service = QRScannerService.get_instance()
    return qr_service.get_status()


@inventory_router.post("/camera-scan/start")
async def start_camera_scanner():
    """Start integrated USB camera QR code scanner loop in backend."""
    qr_service = QRScannerService.get_instance()
    qr_service.start_camera_scanner()
    status = qr_service.get_status()
    mode_text = "Real USB Camera" if not status.get("simulator_mode") else "Simulator Mode"
    return {
        "message": f"Đã khởi chạy Backend Camera QR Scanner ({mode_text})",
        "status": status,
    }


@inventory_router.post("/camera-scan/stop")
async def stop_camera_scanner():
    """Stop integrated USB camera QR code scanner loop in backend."""
    qr_service = QRScannerService.get_instance()
    qr_service.stop_camera_scanner()
    return {"message": "Đã dừng Backend Camera QR Scanner", "status": qr_service.get_status()}


@inventory_router.get("/camera-scan/video-feed")
async def get_camera_video_feed():
    """Live MJPEG video stream from USB Camera for Web UI preview."""
    import asyncio
    from fastapi.responses import StreamingResponse

    qr_service = QRScannerService.get_instance()

    async def generate_mjpeg_frames():
        try:
            while True:
                if not qr_service.is_active:
                    await asyncio.sleep(0.2)
                    continue

                frame_bytes = qr_service.get_latest_frame_bytes()
                if frame_bytes:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                    )
                await asyncio.sleep(0.05)  # ~20 FPS stream
        except (asyncio.CancelledError, GeneratorExit):
            pass

    return StreamingResponse(
        generate_mjpeg_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@inventory_router.post("/generate-qr-pdf")
async def generate_qr_pdf_endpoint(payload: QRScanPayload):
    """Generate a printable PDF label file for a product QR code."""
    import os
    from fastapi.responses import FileResponse

    try:
        from app.services.generate_qr_pdf import generate_qr_pdf

        p_id = payload.product_id or payload.qr.strip()
        pdf_file = generate_qr_pdf(
            product_id=p_id,
            sender_name=payload.sender_name or "Nguyen Van A",
            address=payload.address or "Da Nang",
        )
        return FileResponse(pdf_file, filename=os.path.basename(pdf_file), media_type="application/pdf")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate QR PDF: {exc}")

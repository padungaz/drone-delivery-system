import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.staff_operation_manager import staff_operation_manager
from app.services.system_mode_manager import system_mode_manager

logger = logging.getLogger(__name__)

staff_router = APIRouter(prefix="/api/staff", tags=["Staff Operations"])


class StaffModeRequest(BaseModel):
    operation_mode: str = Field(..., description="'STATION_AUTO' or 'STAFF_OPERATION'")


class OutboundStartRequest(BaseModel):
    slots: Optional[List[str]] = Field(default=None, description="List of storage slots to pick, e.g. ['A2', 'B1', 'C3']")
    quantity: Optional[int] = Field(default=None, ge=1, le=9, description="Target quantity of items to pick (e.g. 3)")


class InboundStartRequest(BaseModel):
    # Continuous mode: runs until full or user stops
    pass


@staff_router.get("/status")
async def get_staff_status():
    """Retrieve full realtime status of staff operations and system mode."""
    return {
        "system_mode": system_mode_manager.get_status(),
        "staff_op": staff_operation_manager.get_status(),
    }


from app.services.device_lock_manager import device_lock_manager


@staff_router.post("/mode")
async def set_staff_mode(req: StaffModeRequest):
    """Switch system operation mode between STATION_AUTO and STAFF_OPERATION."""
    val_op = req.operation_mode.upper().strip()

    # Interlock check when switching to STAFF_OPERATION
    if val_op == "STAFF_OPERATION" and device_lock_manager.is_station_busy() and device_lock_manager._locks.get("STATION", {}).get("locked_by") != "STAFF_OPERATION":
        lock_mission = device_lock_manager.get_locking_mission_id("STATION")
        raise HTTPException(
            status_code=409,
            detail=f"Trạm Drone đang bận thực thi Nhiệm vụ #{lock_mission}. Vui lòng đợi hoàn tất trước khi chuyển sang Chế độ Nhân viên!"
        )

    # Interlock check when switching back to STATION_AUTO
    if val_op == "STATION_AUTO" and staff_operation_manager.status == "RUNNING":
        raise HTTPException(
            status_code=409,
            detail="Không thể chuyển về Chế độ Kho Trạm khi Nhân viên đang lấy hoặc thêm hàng! Vui lòng dừng hoặc chờ chu trình nhân viên hoàn tất."
        )

    try:
        mode = await system_mode_manager.set_operation_mode(val_op)
        return {
            "success": True,
            "operation_mode": mode,
            "status": system_mode_manager.get_status(),
        }
    except Exception as e:
        logger.error("Failed to switch operation mode: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@staff_router.post("/outbound/start")
async def start_outbound(req: OutboundStartRequest):
    """Start Outbound picking process from specified 3x3 slots or target quantity to conveyor."""
    try:
        res = await staff_operation_manager.start_outbound(slots=req.slots, quantity=req.quantity)
        return {"success": True, "data": res}
    except Exception as e:
        logger.error("Failed to start outbound: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@staff_router.post("/outbound/cancel")
async def cancel_outbound():
    """Cancel currently running outbound picking process."""
    try:
        res = await staff_operation_manager.cancel_outbound()
        return {"success": True, "data": res}
    except Exception as e:
        logger.error("Failed to cancel outbound: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@staff_router.post("/inbound/start")
async def start_inbound(req: Optional[InboundStartRequest] = None):
    """Start continuous Inbound storing process from O1 into 3x3 storage grid."""
    try:
        res = await staff_operation_manager.start_inbound()
        return {"success": True, "data": res}
    except Exception as e:
        logger.error("Failed to start inbound: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@staff_router.post("/inbound/stop")
async def stop_inbound():
    """Stop currently running inbound storing process."""
    try:
        res = await staff_operation_manager.stop_inbound()
        return {"success": True, "data": res}
    except Exception as e:
        logger.error("Failed to stop inbound: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

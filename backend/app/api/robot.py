from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.models.schemas import RobotCommand, RobotCommandRequest, RobotStatusResponse
from app.services.robot_manager import RobotManager
from app.services.plc_manager import PLCManager, slot_to_z_level, Z_LEVEL_LABELS
from app.services.device_lock_manager import device_lock_manager
from app.websocket.manager import system_ws_manager

robot_router = APIRouter(prefix="/api/robot", tags=["FAIRINO Robot Control"])


class RobotSlotRequest(BaseModel):
    slot: Optional[str] = None


def check_z_axis_precondition(slot: Optional[str]) -> None:
    """Safety Interlock Pre-condition Check (Cách B):
    Ngăn không gửi lệnh xuống Robot nếu Trục Z chưa được nâng/hạ đúng tầng mục tiêu hoặc đang di chuyển.
    Yêu cầu người vận hành phải chủ động kích hoạt tầng Z trên cụm điều khiển PLC trước.
    """
    if not slot:
        return
    norm = slot.upper().strip()
    if norm in ("HOME", "STANDBY", "SCAN_QR", "SCAN_QR_POS"):
        return

    required_z = slot_to_z_level(norm)
    plc_mgr = PLCManager.get_instance()

    # Kiểm tra nếu trục Z chưa đúng tầng yêu cầu hoặc cờ in_position chưa bật
    if plc_mgr.current_z_level != required_z or not plc_mgr.plc_z_in_position:
        target_name = Z_LEVEL_LABELS.get(required_z, f"TẦNG {required_z}")
        curr_name = Z_LEVEL_LABELS.get(plc_mgr.current_z_level, f"TẦNG {plc_mgr.current_z_level}")
        status_text = "ĐANG DI CHUYỂN" if not plc_mgr.plc_z_in_position else f"đang ở {curr_name} (Mã {plc_mgr.current_z_level})"
        raise HTTPException(
            status_code=400,
            detail=(
                f"⚠️ CẢNH BÁO AN TOÀN TRỤC Z: Thao tác tại ô [{norm}] yêu cầu Trục Z phải ở {target_name} (Mã {required_z}), "
                f"nhưng hiện tại Trục Z {status_text}! "
                f"Vui lòng nhấn nút [{target_name}] trên cụm điều khiển PLC trước khi gửi lệnh xuống Robot."
            ),
        )


@robot_router.post("/command", response_model=RobotStatusResponse)
async def execute_robot_command(req: RobotCommandRequest):
    if device_lock_manager.is_device_locked("ROBOT01"):
        raise HTTPException(
            status_code=409,
            detail=f"Robot đang bị khóa bởi Nhiệm vụ AUTO #{device_lock_manager.get_locking_mission_id('ROBOT01')}! Vui lòng không can thiệp thủ công."
        )

    mgr = RobotManager.get_instance()
    # Check if robot is already running a motion cycle (allow CANCEL/STOP)
    if (mgr.state in ("MOVING", "PICKING", "PLACING", "BUSY") or mgr._is_busy_moving) and req.command not in (
        RobotCommand.CANCEL,
    ):
        raise HTTPException(
            status_code=409,
            detail=f"⚠️ Robot đang trong hành trình chuyển động ({mgr.state})! Không thể nhận lệnh thao tác mới lúc này.",
        )

    # Khóa an toàn liên động Trục Z (Cách B)
    if req.command in (
        RobotCommand.PICK,
        RobotCommand.PICK_PRODUCT,
        RobotCommand.STORE,
        RobotCommand.PLACE_PRODUCT,
    ) and req.slot:
        check_z_axis_precondition(req.slot)

    status = await mgr.execute_command(req.command, slot=req.slot)

    # Broadcast Robot status to realtime WebSocket
    await system_ws_manager.broadcast("ROBOT_STATUS", status.model_dump())
    return status


@robot_router.post("/pick")
async def robot_pick(req: RobotSlotRequest):
    if device_lock_manager.is_device_locked("ROBOT01"):
        raise HTTPException(
            status_code=409,
            detail=f"Robot đang bị khóa bởi Nhiệm vụ AUTO #{device_lock_manager.get_locking_mission_id('ROBOT01')}! Vui lòng không can thiệp thủ công."
        )

    mgr = RobotManager.get_instance()
    if mgr.state in ("MOVING", "PICKING", "PLACING", "BUSY") or mgr._is_busy_moving:
        raise HTTPException(
            status_code=409,
            detail=f"⚠️ Robot đang trong hành trình chuyển động ({mgr.state})! Không thể nhận lệnh gắp mới lúc này.",
        )

    # Khóa an toàn liên động Trục Z (Cách B)
    check_z_axis_precondition(req.slot)

    status = await mgr.execute_command(RobotCommand.PICK, slot=req.slot)

    await system_ws_manager.broadcast("ROBOT_STATUS", status.model_dump())
    return {
        "message": f"Lệnh Robot gắp hàng tại ô {req.slot or 'N/A'} thành công!",
        "status": status.model_dump(),
    }


@robot_router.post("/store")
async def robot_store(req: RobotSlotRequest):
    if device_lock_manager.is_device_locked("ROBOT01"):
        raise HTTPException(
            status_code=409,
            detail=f"Robot đang bị khóa bởi Nhiệm vụ AUTO #{device_lock_manager.get_locking_mission_id('ROBOT01')}! Vui lòng không can thiệp thủ công."
        )

    mgr = RobotManager.get_instance()
    if mgr.state in ("MOVING", "PICKING", "PLACING", "BUSY") or mgr._is_busy_moving:
        raise HTTPException(
            status_code=409,
            detail=f"⚠️ Robot đang trong hành trình chuyển động ({mgr.state})! Không thể nhận lệnh cất mới lúc này.",
        )

    # Khóa an toàn liên động Trục Z (Cách B)
    check_z_axis_precondition(req.slot)

    status = await mgr.execute_command(RobotCommand.STORE, slot=req.slot)

    await system_ws_manager.broadcast("ROBOT_STATUS", status.model_dump())
    return {
        "message": f"Lệnh Robot cất hàng vào ô {req.slot or 'N/A'} thành công!",
        "status": status.model_dump(),
    }


@robot_router.post("/home")
async def robot_home():
    if device_lock_manager.is_device_locked("ROBOT01"):
        raise HTTPException(
            status_code=409,
            detail=f"Robot đang bị khóa bởi Nhiệm vụ AUTO #{device_lock_manager.get_locking_mission_id('ROBOT01')}! Vui lòng không can thiệp thủ công."
        )

    mgr = RobotManager.get_instance()
    status = await mgr.execute_command(RobotCommand.MOVE_HOME)

    await system_ws_manager.broadcast("ROBOT_STATUS", status.model_dump())
    return {
        "message": "Lệnh Robot di chuyển về HOME thành công!",
        "status": status.model_dump(),
    }


@robot_router.post("/place")
async def robot_place(req: RobotSlotRequest):
    if device_lock_manager.is_device_locked("ROBOT01"):
        raise HTTPException(
            status_code=409,
            detail=f"Robot đang bị khóa bởi Nhiệm vụ AUTO #{device_lock_manager.get_locking_mission_id('ROBOT01')}! Vui lòng không can thiệp thủ công."
        )

    # Khóa an toàn liên động Trục Z (Cách B)
    check_z_axis_precondition(req.slot or "N1")

    mgr = RobotManager.get_instance()
    status = await mgr.execute_command(RobotCommand.PLACE_PRODUCT, slot=req.slot)

    await system_ws_manager.broadcast("ROBOT_STATUS", status.model_dump())
    return {
        "message": f"Lệnh Robot đặt hàng từ ô {req.slot or 'N/A'} ra Docking thành công!",
        "status": status.model_dump(),
    }


@robot_router.post("/emergency-stop")
async def robot_emergency_stop():
    mgr = RobotManager.get_instance()
    status = mgr.emergency_stop()

    await system_ws_manager.broadcast("ROBOT_STATUS", status.model_dump())
    return {
        "message": "🛑 ĐÃ KÍCH HOẠT DỪNG KHẨN CẤP ROBOT FAIRINO!",
        "status": status.model_dump(),
    }


@robot_router.post("/done")
async def robot_signal_done():
    mgr = RobotManager.get_instance()
    mgr.signal_done()
    status = mgr.get_status()

    await system_ws_manager.broadcast("ROBOT_STATUS", status.model_dump())
    return {
        "message": "✅ Đã nhận tín hiệu ROBOT_DONE thành công!",
        "status": status.model_dump(),
    }


@robot_router.get("/status", response_model=RobotStatusResponse)
async def get_robot_status():
    mgr = RobotManager.get_instance()
    return mgr.get_status()

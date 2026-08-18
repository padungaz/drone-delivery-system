from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repository import get_session
from app.models.schemas import (
    DeviceCommandLogResponse,
    DeviceCommandResponse,
    DeviceConfigUpdateRequest,
    DeviceHeartbeatRequest,
    DeviceRegisterRequest,
    DeviceResponse,
    DeviceTestConnectionRequest,
    DeviceTestConnectionResponse,
    PLCCommand,
    RawSocketCommandRequest,
    RobotCommand,
)
from app.services.camera_manager import CameraManager
from app.services.device_manager import DeviceManager
from app.services.plc_manager import PLCManager
from app.services.robot_manager import RobotManager
from app.services.device_lock_manager import device_lock_manager
from app.websocket.manager import system_ws_manager
from fastapi import HTTPException

device_router = APIRouter(prefix="/api/device", tags=["Device Management"])


class DeviceCommandPayload(BaseModel):
    command: str
    target: Optional[str] = None


class QRScanTestPayload(BaseModel):
    qr_code: Optional[str] = "PROD-TEST-1001"


# ---------------------------------------------------------------------------
# Device Registration & Heartbeats
# ---------------------------------------------------------------------------

@device_router.post("/register", response_model=DeviceResponse)
async def register_device(
    req: DeviceRegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    mgr = DeviceManager(session)
    device = await mgr.register_device(req)

    await system_ws_manager.broadcast("DEVICE_STATUS", {
        "device_name": device.device_name,
        "type": device.device_type,
        "ip": device.ip_address,
        "status": device.status,
    })

    return device


@device_router.post("/heartbeat", response_model=DeviceResponse)
async def device_heartbeat(
    req: DeviceHeartbeatRequest,
    session: AsyncSession = Depends(get_session),
):
    mgr = DeviceManager(session)
    device = await mgr.update_heartbeat(req)
    if not device:
        return {"error": "Device not registered"}

    await system_ws_manager.broadcast("DEVICE_HEARTBEAT", {
        "device_name": device.device_name,
        "status": device.status,
        "last_heartbeat": device.last_heartbeat.isoformat(),
    })

    return device


@device_router.get("", response_model=List[DeviceResponse])
@device_router.get("/list", response_model=List[DeviceResponse])
async def list_devices(
    session: AsyncSession = Depends(get_session),
):
    mgr = DeviceManager(session)
    return await mgr.get_all_devices()


@device_router.get("/logs", response_model=List[DeviceCommandLogResponse])
async def get_device_logs(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    mgr = DeviceManager(session)
    logs = await mgr.get_command_logs(limit=limit)
    return logs


# ---------------------------------------------------------------------------
# PLC Device Command Endpoints
# ---------------------------------------------------------------------------

@device_router.post("/plc/command", response_model=DeviceCommandResponse)
async def execute_plc_device_command(
    req: DeviceCommandPayload,
    session: AsyncSession = Depends(get_session),
):
    plc_mgr = PLCManager.get_instance()
    dev_mgr = DeviceManager(session)

    cmd_str = req.command.upper().strip()
    try:
        cmd_enum = PLCCommand(cmd_str)
        if cmd_enum not in (PLCCommand.STOP_PLC, PLCCommand.RESET_PLC) and device_lock_manager.is_device_locked("PLC01"):
            raise HTTPException(
                status_code=409,
                detail=f"PLC đang bị khóa bởi Nhiệm vụ AUTO #{device_lock_manager.get_locking_mission_id('PLC01')}!"
            )
        status_res = await plc_mgr.execute_command(cmd_enum)
        res_str = "SUCCESS" if not status_res.plc_error else "FAILED"
        msg = f"PLC executed command {cmd_str} successfully" if res_str == "SUCCESS" else f"PLC failed command {cmd_str}"
    except HTTPException:
        raise
    except Exception as exc:
        res_str = "FAILED"
        msg = f"Error executing PLC command {cmd_str}: {exc}"

    await dev_mgr.log_command(
        device="PLC01",
        command=cmd_str,
        target=req.target,
        result=res_str,
        message=msg,
    )

    await system_ws_manager.broadcast("DEVICE_COMMAND_LOG", {
        "device": "PLC01",
        "command": cmd_str,
        "target": req.target,
        "result": res_str,
        "message": msg,
    })

    return DeviceCommandResponse(
        device="PLC",
        command=cmd_str,
        target=req.target,
        status="DONE" if res_str == "SUCCESS" else "FAILED",
        message=msg,
    )


# ---------------------------------------------------------------------------
# Robot Device Command Endpoints
# ---------------------------------------------------------------------------

@device_router.post("/robot/command", response_model=DeviceCommandResponse)
async def execute_robot_device_command(
    req: DeviceCommandPayload,
    session: AsyncSession = Depends(get_session),
):
    robot_mgr = RobotManager.get_instance()
    dev_mgr = DeviceManager(session)

    cmd_str = req.command.upper().strip()
    target_str = req.target or "PAD"
    if cmd_str not in ("ESTOP", "STOP", "RESET") and device_lock_manager.is_device_locked("ROBOT01"):
        raise HTTPException(
            status_code=409,
            detail=f"Robot đang bị khóa bởi Nhiệm vụ AUTO #{device_lock_manager.get_locking_mission_id('ROBOT01')}!"
        )

    try:
        cmd_enum = RobotCommand(cmd_str)
        status_res = await robot_mgr.execute_command(cmd_enum, slot=target_str)
        res_str = "SUCCESS" if status_res.state != "ERROR" else "FAILED"
        msg = f"Robot executed command {cmd_str} (target: {target_str}) successfully"
    except HTTPException:
        raise
    except Exception as exc:
        res_str = "FAILED"
        msg = f"Error executing Robot command {cmd_str}: {exc}"

    await dev_mgr.log_command(
        device="ROBOT01",
        command=cmd_str,
        target=target_str,
        result=res_str,
        message=msg,
    )

    await system_ws_manager.broadcast("DEVICE_COMMAND_LOG", {
        "device": "ROBOT01",
        "command": cmd_str,
        "target": target_str,
        "result": res_str,
        "message": msg,
    })

    return DeviceCommandResponse(
        device="ROBOT",
        command=cmd_str,
        target=target_str,
        status="DONE" if res_str == "SUCCESS" else "FAILED",
        message=msg,
    )


# ---------------------------------------------------------------------------
# Camera Device Command Endpoints
# ---------------------------------------------------------------------------

@device_router.post("/camera/start", response_model=DeviceCommandResponse)
async def start_camera_device(
    session: AsyncSession = Depends(get_session),
):
    cam_mgr = CameraManager.get_instance()
    dev_mgr = DeviceManager(session)

    success = cam_mgr.start_camera()
    msg = "Camera stream started successfully" if success else "Failed to start camera stream"
    res_str = "SUCCESS" if success else "FAILED"

    await dev_mgr.log_command(
        device="CAM01",
        command="START",
        result=res_str,
        message=msg,
    )

    return DeviceCommandResponse(
        device="CAMERA",
        command="START",
        status="DONE" if success else "FAILED",
        message=msg,
    )


@device_router.post("/camera/stop", response_model=DeviceCommandResponse)
async def stop_camera_device(
    session: AsyncSession = Depends(get_session),
):
    cam_mgr = CameraManager.get_instance()
    dev_mgr = DeviceManager(session)

    success = cam_mgr.stop_camera()
    msg = "Camera stream stopped"
    res_str = "SUCCESS"

    await dev_mgr.log_command(
        device="CAM01",
        command="STOP",
        result=res_str,
        message=msg,
    )

    return DeviceCommandResponse(
        device="CAMERA",
        command="STOP",
        status="DONE",
        message=msg,
    )


@device_router.post("/camera/qr_scan")
async def test_camera_qr_scan(
    payload: Optional[QRScanTestPayload] = None,
    session: AsyncSession = Depends(get_session),
):
    cam_mgr = CameraManager.get_instance()
    dev_mgr = DeviceManager(session)

    raw_qr = payload.qr_code if payload and payload.qr_code else "PROD-TEST-1001"
    scan_res = await cam_mgr.test_qr_scan(raw_qr)

    res_str = "SUCCESS" if scan_res.get("status") in ("success", "already_assigned") else "FAILED"
    msg = scan_res.get("message", "QR scan completed")

    await dev_mgr.log_command(
        device="CAM01",
        command="QR_SCAN",
        target=raw_qr,
        result=res_str,
        message=msg,
    )

    return {
        "device": "CAMERA",
        "command": "QR_SCAN",
        "target": raw_qr,
        "result": scan_res,
    }


# ---------------------------------------------------------------------------
# Device Hardware Configuration & Interactive Socket Testing Endpoints
# ---------------------------------------------------------------------------

@device_router.put("/config/{device_name}", response_model=DeviceResponse)
async def update_device_config(
    device_name: str,
    req: DeviceConfigUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    dev_mgr = DeviceManager(session)
    device = await dev_mgr.update_device_config(
        name=device_name,
        ip_address=req.ip_address,
        port=req.port,
        simulator_mode=req.simulator_mode,
        rack=req.rack,
        slot=req.slot,
        db_number=req.db_number,
    )
    if not device:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Device '{device_name}' not found")

    await system_ws_manager.broadcast("DEVICE_CONFIG_UPDATED", {
        "device_name": device.device_name,
        "type": device.device_type,
        "ip": device.ip_address,
        "port": device.port,
        "simulator_mode": device.simulator_mode,
        "status": device.status,
    })

    return device


@device_router.post("/test-connection", response_model=DeviceTestConnectionResponse)
async def test_device_connection(
    req: DeviceTestConnectionRequest,
    session: AsyncSession = Depends(get_session),
):
    """Perform direct TCP socket connection ping / diagnostic status test to device."""
    import asyncio, time
    dev_name = req.device_name.upper().strip()
    target_ip = req.ip_address or "127.0.0.1"
    target_port = req.port or 8090
    timeout = req.timeout or 3.0

    start_t = time.time()

    if dev_name in ("ROBOT01", "ROBOT", "FAIRINO"):
        robot_mgr = RobotManager.get_instance()
        if robot_mgr.simulator_mode:
            return DeviceTestConnectionResponse(
                device_name=dev_name,
                success=True,
                ip_address=robot_mgr.robot_ip,
                port=robot_mgr.robot_port,
                latency_ms=1.2,
                response_text="STATE:IDLE BUSY:FALSE POSITION:HOME [SIMULATOR MODE]",
                message="✅ Fairino Robot (Simulator Mode Active)",
            )

        target_ip = req.ip_address or robot_mgr.robot_ip
        target_port = req.port or robot_mgr.robot_port

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(target_ip, target_port),
                timeout=timeout
            )
            writer.write(b"STATUS\r\n")
            await writer.drain()

            resp_bytes = await asyncio.wait_for(reader.readline(), timeout=timeout)
            resp_str = resp_bytes.decode("utf-8", errors="ignore").strip()

            writer.close()
            await writer.wait_closed()
            latency = (time.time() - start_t) * 1000.0

            return DeviceTestConnectionResponse(
                device_name=dev_name,
                success=True,
                ip_address=target_ip,
                port=target_port,
                latency_ms=round(latency, 2),
                response_text=resp_str or "OK",
                message=f"✅ Socket connection to Fairino Robot ({target_ip}:{target_port}) successful!",
            )
        except Exception as exc:
            latency = (time.time() - start_t) * 1000.0
            return DeviceTestConnectionResponse(
                device_name=dev_name,
                success=False,
                ip_address=target_ip,
                port=target_port,
                latency_ms=round(latency, 2),
                response_text="",
                message=f"❌ Socket connection failed ({target_ip}:{target_port}): {exc}",
            )

    elif dev_name in ("PLC01", "PLC", "SIEMENS"):
        plc_mgr = PLCManager.get_instance()
        target_ip = req.ip_address or plc_mgr.plc_ip
        if plc_mgr.simulator_mode:
            return DeviceTestConnectionResponse(
                device_name=dev_name,
                success=True,
                ip_address=target_ip,
                port=102,
                latency_ms=0.8,
                response_text="DB15 READ OK (plc_on=True, plc_locked=False, z_axis=DOWN)",
                message="✅ Siemens S7-1200 PLC (Simulator Mode Active)",
            )

        is_conn = await plc_mgr.check_connection()
        latency = (time.time() - start_t) * 1000.0
        return DeviceTestConnectionResponse(
            device_name=dev_name,
            success=is_conn,
            ip_address=target_ip,
            port=102,
            latency_ms=round(latency, 2),
            response_text=f"Connected: {is_conn}, DB15 Ready",
            message=f"✅ Siemens PLC ({target_ip}) connection ok" if is_conn else f"❌ Siemens PLC ({target_ip}) connection failed",
        )

    else:
        # Generic TCP socket test
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(target_ip, target_port),
                timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            latency = (time.time() - start_t) * 1000.0
            return DeviceTestConnectionResponse(
                device_name=dev_name,
                success=True,
                ip_address=target_ip,
                port=target_port,
                latency_ms=round(latency, 2),
                response_text="TCP Port Open",
                message=f"✅ Socket TCP ping ({target_ip}:{target_port}) successful!",
            )
        except Exception as exc:
            latency = (time.time() - start_t) * 1000.0
            return DeviceTestConnectionResponse(
                device_name=dev_name,
                success=False,
                ip_address=target_ip,
                port=target_port,
                latency_ms=round(latency, 2),
                response_text="",
                message=f"❌ Socket connection failed: {exc}",
            )


@device_router.get("/lock-status")
async def get_device_lock_status():
    """Get current safety interlock status across all devices."""
    return device_lock_manager.get_lock_status()


@device_router.post("/send-raw-command", response_model=DeviceCommandResponse)
async def send_raw_device_socket_command(
    req: RawSocketCommandRequest,
    session: AsyncSession = Depends(get_session),
):
    """Execute raw custom socket string command (e.g. 'MOVE_HOME', 'PICK A1', 'STORE B2') to hardware."""
    dev_name = req.device_name.upper().strip()
    cmd_str = req.command_text.strip()
    target_str = req.target or ""
    dev_mgr = DeviceManager(session)

    if cmd_str.upper() not in ("ESTOP", "STOP", "RESET", "STOP_PLC", "RESET_PLC") and device_lock_manager.is_device_locked(dev_name):
        raise HTTPException(
            status_code=409,
            detail=f"Thiết bị {dev_name} đang bị khóa bởi Nhiệm vụ AUTO #{device_lock_manager.get_locking_mission_id(dev_name)}!"
        )

    if dev_name in ("ROBOT01", "ROBOT", "FAIRINO"):
        robot_mgr = RobotManager.get_instance()
        # Parse command string
        full_payload = f"{cmd_str} {target_str}".strip() if target_str else cmd_str
        try:
            success = await robot_mgr._send_socket_command(full_payload, timeout=req.timeout or 15.0)
            res_str = "SUCCESS" if success else "FAILED"
            msg = f"Fairino Robot executed raw command '{full_payload}': {res_str}"
        except Exception as exc:
            res_str = "FAILED"
            msg = f"Error executing Fairino Robot command '{full_payload}': {exc}"

        await dev_mgr.log_command(
            device="ROBOT01",
            command=cmd_str,
            target=target_str or None,
            result=res_str,
            message=msg,
        )

        return DeviceCommandResponse(
            device="ROBOT01",
            command=cmd_str,
            target=target_str or None,
            status="DONE" if res_str == "SUCCESS" else "FAILED",
            message=msg,
        )

    elif dev_name in ("PLC01", "PLC", "SIEMENS"):
        plc_mgr = PLCManager.get_instance()
        try:
            cmd_enum = PLCCommand(cmd_str.upper())
            status_res = await plc_mgr.execute_command(cmd_enum)
            res_str = "SUCCESS" if not status_res.plc_error else "FAILED"
            msg = f"PLC executed '{cmd_str}' successfully" if res_str == "SUCCESS" else f"PLC execution failed '{cmd_str}'"
        except Exception as exc:
            res_str = "FAILED"
            msg = f"Error executing PLC command '{cmd_str}': {exc}"

        await dev_mgr.log_command(
            device="PLC01",
            command=cmd_str,
            target=target_str or None,
            result=res_str,
            message=msg,
        )

        return DeviceCommandResponse(
            device="PLC01",
            command=cmd_str,
            target=target_str or None,
            status="DONE" if res_str == "SUCCESS" else "FAILED",
            message=msg,
        )

    else:
        return DeviceCommandResponse(
            device=dev_name,
            command=cmd_str,
            target=target_str or None,
            status="FAILED",
            message=f"Unsupported raw command device: {dev_name}",
        )




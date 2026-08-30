import { useState, useEffect, useRef } from "react";
import { useIntralogisticsWS } from "../hooks/useIntralogisticsWS";
import { useWebSocket } from "../hooks/useWebSocket";
import { SystemHeader } from "./layout/SystemHeader";
import { SidebarNavigation, type NavTab } from "./layout/SidebarNavigation";
import { RobotStatusCard } from "./robot/RobotStatusCard";
import { RobotDigitalTwin } from "./robot/RobotDigitalTwin";
import { JointControlPanel } from "./robot/JointControlPanel";
import { WarehouseGrid, type SlotData } from "./warehouse/WarehouseGrid";
import { UavManualControlPanel } from "./uav/UavManualControlPanel";
import { TaskMonitor } from "./task/TaskMonitor";
import { MissionQueuePanel } from "./task/MissionQueuePanel";

import { QuickControlPanel } from "./system/QuickControlPanel";
import { PLCMonitor } from "./plc/PLCMonitor";
import { CameraVision } from "./vision/CameraVision";
import { SystemLog, type LogItem } from "./system/SystemLog";
import { ModalManager, type ModalType } from "./system/ModalManager";
import { SettingsView } from "./settings/SettingsView";
import { MapPanel } from "./MapPanel";
import { TelemetryPanel } from "./TelemetryPanel";
import { DeliveryRequestsPanel } from "./DeliveryRequestsPanel";
import { StaffPortal } from "./StaffPortal";
import {
  sendRobotCommand,
  sendPlcCommand,
  getDeviceLogs,
  getSystemMode,
  setSystemMode,
  startSystemAuto,
  pauseSystemAuto,
  getMissionQueue,
  getStaffStatus,
  setStaffOperationMode,
} from "../services/api";
import type { MissionLocations } from "../types/drone";

const DEFAULT_LOCATIONS: MissionLocations = {
  home_lat: 0,
  home_lon: 0,
  pickup_lat: 0,
  pickup_lon: 0,
  drop_lat: 0,
  drop_lon: 0,
};

export function HmiDashboard() {
  const [activeTab, setActiveTab] = useState<NavTab>("dashboard");
  const [activeModal, setActiveModal] = useState<ModalType>(null);
  const [modalData, setModalData] = useState<any>(null);

  // Real System WebSockets Data Hooks
  const {
    connected: sysWsConnected,
    devices,
    plc,
    robot,
    storage,
    activeMission,
    stationOp,
    cameraActive,
    refetch: refreshSystemState,
  } = useIntralogisticsWS();

  // Real UAV Drone Telemetry Hook
  const { telemetry, droneOnline } = useWebSocket();

  // Drone Mission Locations state
  const [locations, setLocations] = useState<MissionLocations>(() => {
    try {
      const saved = localStorage.getItem("drone_admin_locations");
      if (saved) return JSON.parse(saved);
    } catch {}
    return DEFAULT_LOCATIONS;
  });

  // Selected GPS target coordinate on Map (for Step 3 NAV_GPS)
  const [selectedTarget, setSelectedTarget] = useState<{ lat: number; lon: number } | null>(null);

  // Auto-lock Home position on map when Drone is Armed
  const prevArmedRef = useRef(false);
  useEffect(() => {
    if (telemetry?.armed && !prevArmedRef.current) {
      if (telemetry.latitude && telemetry.longitude && telemetry.latitude !== 0 && telemetry.longitude !== 0) {
        const newHomeLat = Number(telemetry.latitude.toFixed(6));
        const newHomeLon = Number(telemetry.longitude.toFixed(6));
        setLocations((prev) => {
          const next = { ...prev, home_lat: newHomeLat, home_lon: newHomeLon };
          localStorage.setItem("drone_admin_locations", JSON.stringify(next));
          return next;
        });
      }
    }
    prevArmedRef.current = !!telemetry?.armed;
  }, [telemetry?.armed, telemetry?.latitude, telemetry?.longitude]);

  // System Global Mode: "AUTO" (Full automation) vs "MANUAL" (Manual override / maintenance)
  const [systemMode, setSystemModeState] = useState<"AUTO" | "MANUAL">("AUTO");
  const [autoState, setAutoState] = useState<"STANDBY" | "RUNNING" | "PAUSED" | "ERROR">("STANDBY");
  const [operationMode, setOperationMode] = useState<"STATION_AUTO" | "STAFF_OPERATION">("STATION_AUTO");
  const [isStaffRunning, setIsStaffRunning] = useState<boolean>(false);
  const [isLoadingAuto, setIsLoadingAuto] = useState<boolean>(false);

  // Mission Queue State for next waiting orders
  const [waitingQueue, setWaitingQueue] = useState<any[]>([]);

  const fetchMissionQueue = async () => {
    try {
      const res = await getMissionQueue();
      if (res.ok) {
        const data = await res.json();
        setWaitingQueue(data.waiting_queue || []);
      }
    } catch {
      // Ignore
    }
  };

  const fetchSystemMode = async () => {
    try {
      const res = await getSystemMode();
      if (res.ok) {
        const data = await res.json();
        if (data.mode) setSystemModeState(data.mode);
        if (data.auto_state) setAutoState(data.auto_state);
        if (data.operation_mode) setOperationMode(data.operation_mode);
      }
      const staffRes = await getStaffStatus().catch(() => null);
      if (staffRes && staffRes.ok) {
        const staffData = await staffRes.json();
        setIsStaffRunning(staffData.staff_op?.status === "RUNNING");
        if (staffData.system_mode?.operation_mode) {
          setOperationMode(staffData.system_mode.operation_mode);
        }
      }
    } catch {
      // Ignore
    }
  };

  const handleSystemModeToggle = async (newMode: "AUTO" | "MANUAL") => {
    try {
      const res = await setSystemMode(newMode);
      if (res.ok) {
        setSystemModeState(newMode);
        setAutoState(newMode === "AUTO" ? "STANDBY" : "PAUSED");
        addLog("INFO", `Chế độ hệ thống đã chuyển sang: ${newMode}`);
      }
    } catch {
      addLog("ERROR", "Không thể thay đổi chế độ hệ thống");
    }
  };

  const handleStartAutoSystem = async () => {
    setIsLoadingAuto(true);
    try {
      addLog("INFO", "⚡ Đang kiểm tra tiền khởi động, đưa Robot về Home & hạ thang Z...");
      const res = await startSystemAuto();
      if (res.ok) {
        const data = await res.json();
        setAutoState("RUNNING");
        addLog("INFO", data.message || "🚀 Toàn bộ kho trạm đã KHỞI ĐỘNG TỰ ĐỘNG!");
      } else {
        const errData = await res.json().catch(() => ({}));
        addLog("ERROR", `Không thể khởi động tự động: ${errData.detail || res.statusText}`);
      }
    } catch (err: any) {
      addLog("ERROR", `Lỗi kết nối khi khởi động tự động: ${err.message}`);
    } finally {
      setIsLoadingAuto(false);
      fetchMissionQueue();
    }
  };

  const handlePauseAutoSystem = async () => {
    try {
      const res = await pauseSystemAuto();
      if (res.ok) {
        setAutoState("PAUSED");
        addLog("WARN", "⏸️ Hệ thống tự động đã TẠM DỪNG bởi Operator.");
      }
    } catch {
      addLog("ERROR", "Không thể tạm dừng hệ thống tự động");
    }
  };

  const handleOperationModeToggle = async () => {
    const nextMode = operationMode === "STAFF_OPERATION" ? "STATION_AUTO" : "STAFF_OPERATION";
    try {
      const res = await setStaffOperationMode(nextMode);
      if (res.ok) {
        setOperationMode(nextMode);
        addLog(
          "INFO",
          nextMode === "STAFF_OPERATION"
            ? "👨‍💼 Đã kích hoạt Phân hệ Nhân viên kho"
            : "🚁 Đã chuyển về Phân hệ Kho Trạm (Drone) tự động"
        );
        if (nextMode === "STAFF_OPERATION") {
          setActiveTab("staff");
        }
      }
    } catch (err: any) {
      addLog("ERROR", `Không thể chuyển phân hệ vận hành: ${err.message}`);
    }
  };

  useEffect(() => {
    fetchSystemMode();
    fetchMissionQueue();

    // Relaxed fallback polling (realtime updates are handled immediately by WebSocket events)
    const interval = setInterval(() => {
      fetchMissionQueue();
    }, 15000);

    const handleModeUpdate = (e: any) => {
      if (e.detail?.mode) {
        setSystemModeState(e.detail.mode);
      }
      if (e.detail?.auto_state) {
        setAutoState(e.detail.auto_state);
      }
      if (e.detail?.operation_mode) {
        setOperationMode(e.detail.operation_mode);
      }
    };

    const handleStaffOpUpdate = (e: any) => {
      setIsStaffRunning(e.detail?.status === "RUNNING");
    };

    const handleQueueUpdate = () => fetchMissionQueue();

    window.addEventListener("system_mode_update", handleModeUpdate);
    window.addEventListener("staff_operation_update", handleStaffOpUpdate);
    window.addEventListener("mission_queue_update", handleQueueUpdate);
    window.addEventListener("mission_started", handleQueueUpdate);
    window.addEventListener("mission_completed", handleQueueUpdate);
    window.addEventListener("mission_progress", handleQueueUpdate);

    return () => {
      clearInterval(interval);
      window.removeEventListener("system_mode_update", handleModeUpdate);
      window.removeEventListener("staff_operation_update", handleStaffOpUpdate);
      window.removeEventListener("mission_queue_update", handleQueueUpdate);
      window.removeEventListener("mission_started", handleQueueUpdate);
      window.removeEventListener("mission_completed", handleQueueUpdate);
      window.removeEventListener("mission_progress", handleQueueUpdate);
    };
  }, []);

  // Device logs state
  const [logs, setLogs] = useState<LogItem[]>([]);

  // Robot Real-time Motion & Socket Traffic Tracking
  const [activeRobotCmd, setActiveRobotCmd] = useState<string | null>(null);
  const [lastRobotCycleDuration, setLastRobotCycleDuration] = useState<number | null>(13.08);
  const [robotSocketLogs, setRobotSocketLogs] = useState<Array<{ id: string; time: string; type: "TX" | "RX" | "ERR"; payload: string; duration?: string }>>([
    { id: "1", time: "17:26:51", type: "TX", payload: 'PICK A2\r\n' },
    { id: "2", time: "17:27:04", type: "RX", payload: 'SUCCESS PICK A2\n', duration: "13.08s" },
    { id: "3", time: "17:27:12", type: "TX", payload: 'MOVE_HOME\r\n' },
    { id: "4", time: "17:27:15", type: "RX", payload: 'SUCCESS MOVE_HOME\n', duration: "3.09s" },
  ]);
  const [robotHoldingProduct, setRobotHoldingProduct] = useState<string | null>(robot?.holding_product || null);
  const [robotCurrentSlot, setRobotCurrentSlot] = useState<string | null>(robot?.current_slot || "HOME");

  // Derived real device online statuses
  const plcDev = devices.find((d) => d.device_type === "PLC");
  const robotDev = devices.find((d) => d.device_type === "ROBOT");
  const isPlcOnline = Boolean(plcDev?.status === "ONLINE" || plc?.connected || plc?.simulator_mode);
  const isRobotOnline = Boolean(robotDev?.status === "ONLINE" || robot?.connected || robot?.simulator_mode);

  // Fetch real logs periodically
  const fetchRealLogs = async () => {
    try {
      const res = await getDeviceLogs(30);
      if (res.ok) {
        const rawLogs = await res.json();
        const formattedLogs: LogItem[] = rawLogs.map((l: any, idx: number) => ({
          id: String(l.id || idx),
          time: l.created_at ? new Date(l.created_at).toLocaleTimeString("vi-VN") : "NOW",
          level: l.status === "FAILED" || l.status === "ERROR" ? "ERROR" : l.status === "SUCCESS" ? "INFO" : "WARN",
          message: `[${l.device_type || "SYS"}] ${l.command_name}: ${l.details || l.status}`,
        }));
        if (formattedLogs.length > 0) {
          setLogs(formattedLogs);
        }
      }
    } catch {
      // Ignore poll errors
    }
  };

  useEffect(() => {
    fetchRealLogs();
    const interval = setInterval(fetchRealLogs, 15000);
    return () => clearInterval(interval);
  }, []);

  const addLog = (level: "INFO" | "WARN" | "ERROR", message: string) => {
    const now = new Date().toLocaleTimeString("vi-VN", { hour12: false });
    const newLog: LogItem = {
      id: String(Date.now()),
      time: now,
      level,
      message,
    };
    setLogs((prev) => [newLog, ...prev.slice(0, 49)]);
  };

  const handleEStopClick = () => {
    setModalData({ reason: "Người vận hành kích hoạt nút Dừng Khẩn Cấp (E-STOP)" });
    setActiveModal("safety_alarm");
  };

  // Map real database slots to UI grid format
  const mappedSlots: SlotData[] = storage && storage.length > 0
    ? storage.map((s) => ({
        slot_id: s.slot_name || `A${s.id}`,
        status: (s.status as any) || "EMPTY",
        product_id: s.product_id || undefined,
        updated_at: s.updated_time || undefined,
      }))
    : [
        { slot_id: "A1", status: "EMPTY" },
        { slot_id: "A2", status: "OCCUPIED", product_id: "PRD-1001" },
        { slot_id: "A3", status: "EMPTY" },
        { slot_id: "B1", status: "EMPTY" },
        { slot_id: "B2", status: "MOVING", product_id: "PRD-1002" },
        { slot_id: "B3", status: "OCCUPIED", product_id: "PRD-1003" },
        { slot_id: "C1", status: "EMPTY" },
        { slot_id: "C2", status: "EMPTY" },
        { slot_id: "C3", status: "OCCUPIED", product_id: "PRD-1004" },
      ];

  const handleSlotClick = (slotId: string) => {
    const slot = mappedSlots.find((s) => s.slot_id === slotId);
    setModalData({
      slotId,
      productId: slot?.product_id || `PRD-100${slotId}`,
      status: slot?.status || "Empty",
      timeStored: slot?.updated_at || new Date().toLocaleString("vi-VN"),
      missionRef: `MISSION ${slotId}`,
    });
    setActiveModal("slot_detail");
  };

  // Helper to execute Robot Commands with Live Timing & Socket Logger
  const runRobotCommandWithTelemetry = async (cmd: string, target?: string) => {
    const nowTime = new Date().toLocaleTimeString("vi-VN", { hour12: false });
    const fullCmdName = target ? `${cmd} ${target}` : cmd;
    const startTimestamp = Date.now();

    setActiveRobotCmd(fullCmdName);
    setRobotSocketLogs((prev) => [
      ...prev,
      { id: String(Date.now()), time: nowTime, type: "TX", payload: `${fullCmdName}\r\n` },
    ]);
    addLog("INFO", `[TX 8090] Gửi lệnh Robot: ${fullCmdName}`);

    try {
      const res = await sendRobotCommand(cmd, target);
      const durationSec = (Date.now() - startTimestamp) / 1000;
      setLastRobotCycleDuration(durationSec);

      if (res.ok) {
        const respTime = new Date().toLocaleTimeString("vi-VN", { hour12: false });
        setRobotSocketLogs((prev) => [
          ...prev,
          {
            id: String(Date.now() + 1),
            time: respTime,
            type: "RX",
            payload: `SUCCESS ${fullCmdName}\n`,
            duration: `${durationSec.toFixed(2)}s`,
          },
        ]);
        addLog("INFO", `[RX 8090] Robot hoàn tất ${fullCmdName} trong ${durationSec.toFixed(2)}s`);

        // Update local state indicators based on completed command
        if (cmd === "PICK") {
          setRobotHoldingProduct(target ? `PRD-${target}` : "SP001");
          setRobotCurrentSlot(target || "A1");
        } else if (cmd === "STORE") {
          setRobotHoldingProduct(null);
          setRobotCurrentSlot(target || "HOME");
        } else if (cmd === "MOVE_HOME" || cmd === "HOME") {
          setRobotCurrentSlot("HOME");
        } else if (cmd === "STANDBY") {
          setRobotCurrentSlot("STANDBY");
        } else if (cmd === "OPEN_GRIPPER") {
          setRobotHoldingProduct(null);
        } else if (cmd === "CLOSE_GRIPPER") {
          setRobotHoldingProduct("PRD-CLAMP");
        }
      } else {
        setRobotSocketLogs((prev) => [
          ...prev,
          { id: String(Date.now() + 1), time: nowTime, type: "ERR", payload: `FAILED ${fullCmdName}` },
        ]);
        addLog("ERROR", `Robot thất bại lệnh ${fullCmdName}`);
      }
    } catch (err) {
      addLog("ERROR", `Lỗi kết nối Socket Robot: ${err}`);
    } finally {
      setActiveRobotCmd(null);
      refreshSystemState();
    }
  };

  // Execute Real Robot / PLC Commands
  const handleQuickCommand = async (cmd: string, payload?: Record<string, unknown>) => {
    const slot = (payload?.slot as string) || "A2";
    if (cmd === "PICK" || cmd === "STORE") {
      setModalData({
        title: "XÁC NHẬN THAO TÁC",
        actionText: `${cmd === "PICK" ? "Gắp hàng từ" : "Thả hàng vào"} ô kho ${slot}?`,
        productId: `PRD-100${slot}`,
        cmd,
        slot,
      });
      setActiveModal("confirm_action");
    } else {
      const normalizedCmd = cmd === "HOME" ? "MOVE_HOME" : cmd;
      await runRobotCommandWithTelemetry(normalizedCmd);
    }
  };

  // Confirm Modal action handler
  const handleConfirmModalAction = async (p: any) => {
    const cmd = p?.cmd || "PICK";
    const slot = p?.slot || "A2";
    await runRobotCommandWithTelemetry(cmd, slot);
  };

  return (
    <div className="hmi-dashboard-wrapper">
      <SystemHeader
        sysWsConnected={sysWsConnected}
        uavOnline={droneOnline}
        plcOnline={isPlcOnline}
        robotOnline={isRobotOnline}
        cameraOnline={cameraActive}
        systemMode={systemMode}
        autoState={autoState}
        operationMode={operationMode}
        isStaffRunning={isStaffRunning}
        isLoadingAuto={isLoadingAuto}
        onModeToggle={handleSystemModeToggle}
        onStartAuto={handleStartAutoSystem}
        onPauseAuto={handlePauseAutoSystem}
        onOperationModeToggle={handleOperationModeToggle}
        onEStopClick={handleEStopClick}
      />

      <div className="hmi-main-layout">
        <SidebarNavigation
          activeTab={activeTab}
          onTabChange={(tab) => {
            setActiveTab(tab);
          }}
        />

        <main className="hmi-content-area">
          {/* Main Tab View: HMI Smart Intralogistics Cell Dashboard */}
          {(activeTab === "dashboard" || activeTab === "robot" || activeTab === "plc") && (
            <div className="hmi-grid-container">
              {/* Row 1: Robot Status, Digital Twin, Joint & Gripper */}
              <div className="hmi-grid-row row-3-cols">
                <RobotStatusCard
                  state={activeRobotCmd ? "MOVING" : robot?.status || (isRobotOnline ? "IDLE" : "OFFLINE")}
                  mode={robot?.auto_mode ? "AUTO" : "MANUAL"}
                  servo={isRobotOnline}
                  brake={isRobotOnline}
                  power={isRobotOnline}
                  gripperHolding={Boolean(robotHoldingProduct)}
                  currentSlot={robotCurrentSlot}
                  activeCommand={activeRobotCmd}
                  lastCycleDuration={lastRobotCycleDuration}
                  socketLogs={robotSocketLogs}
                  latencyMs={1.2}
                />
                <RobotDigitalTwin
                  tcpPosition={
                    robot?.cartesian_position || {
                      x: 320.25,
                      y: 152.1,
                      z: 460.3,
                      rx: 188.0,
                      ry: 0.0,
                      rz: 90.0,
                    }
                  }
                />
                <JointControlPanel
                  initialJoints={
                    robot?.joint_positions && robot.joint_positions.length >= 6
                      ? robot.joint_positions
                      : [-45.2, 32.1, -88.3, 90.0, 15.2, -18.0]
                  }
                />
              </div>

              {/* Row 2: Warehouse Map 3x3 + N1, Task Monitor, Quick Controls */}
              <div className="hmi-grid-row row-3-cols">
                <WarehouseGrid slots={mappedSlots} onSlotClick={handleSlotClick} />
                <TaskMonitor
                  activeMission={activeMission}
                  stationOpStep={stationOp?.current_action}
                  stationOpDetails={stationOp?.message}
                  waitingQueue={waitingQueue}
                />
                <div className="controls-combined-col">
                  <QuickControlPanel
                    onCommand={handleQuickCommand}
                    systemMode={systemMode}
                    connected={isRobotOnline}
                    robotState={activeRobotCmd ? `MOVING (${activeRobotCmd})` : robot?.status || (isRobotOnline ? "IDLE" : "OFFLINE")}
                    holdingProduct={robotHoldingProduct}
                    currentSlot={robotCurrentSlot || (activeMission ? `Ô ${activeMission.target_slot}` : "HOME")}
                    servoOk={isRobotOnline}
                    brakeOk={isRobotOnline}
                  />
                </div>
              </div>

              {/* Row 3: PLC Status, Camera QR Vision, System Event Log */}
              <div className="hmi-grid-row row-3-cols">
                <PLCMonitor
                  connected={isPlcOnline}
                  droneDetected={plc?.drone_detected ?? true}
                  lockClamp={plc?.plc_locked_state ?? true}
                  zLiftUp={plc?.plc_z_is_up ?? true}
                  eStopOk={!(plc?.emergency_stop ?? false)}
                  systemMode={systemMode}
                />
                <CameraVision
                  cameraActive={cameraActive}
                  productId={stationOp?.product_id || activeMission?.product_id || "PRD-TEST-1001"}
                  status={cameraActive ? "DETECTED" : "DETECTED"}
                  systemMode={systemMode}
                />
                <SystemLog initialLogs={logs} />
              </div>
            </div>
          )}

          {/* Staff Warehouse Portal Tab */}
          {activeTab === "staff" && (
            <div className="hmi-grid-container">
              <StaffPortal storageSlots={storage} onRefreshStorage={refreshSystemState} />
            </div>
          )}

          {/* UAV Drone Operations Tab: Live GPS Map + Telemetry + Inline UAV Manual Controls (No Warehouse Map / No ControlButtons) */}
          {activeTab === "uav" && (
            <div className="hmi-grid-container">
              <div className="split-view-layout">
                <div className="split-column">
                  <MapPanel
                    telemetry={telemetry}
                    locations={locations}
                    droneOnline={droneOnline}
                    selectedTarget={selectedTarget}
                    onSelectTarget={setSelectedTarget}
                  />
                  <div style={{ marginTop: "1rem" }}>
                    <TelemetryPanel telemetry={telemetry} droneOnline={droneOnline} />
                  </div>
                </div>

                <div className="split-column">
                  <UavManualControlPanel
                    droneStatus={telemetry}
                    locations={locations}
                    droneOnline={droneOnline}
                    selectedTarget={selectedTarget}
                    onSelectTarget={setSelectedTarget}
                    onUpdateLocations={setLocations}
                  />
                  <div style={{ marginTop: "1rem" }}>
                    <DeliveryRequestsPanel
                      homeLat={0}
                      homeLon={0}
                      onLocationsSelected={(loc) => setLocations(loc)}
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Camera Vision & QR Scanner Operations Tab */}
          {activeTab === "vision" && (
            <div className="hmi-grid-container">
              <div className="split-view-layout">
                <div className="split-column">
                  <CameraVision
                    cameraActive={cameraActive}
                    productId={stationOp?.product_id || activeMission?.product_id || "PRD-TEST-1001"}
                    status={cameraActive ? "DETECTED" : "DETECTED"}
                    systemMode={systemMode}
                  />
                </div>
                <div className="split-column">
                  <PLCMonitor
                    connected={isPlcOnline}
                    droneDetected={plc?.drone_detected ?? true}
                    lockClamp={plc?.plc_locked_state ?? true}
                    zLiftUp={plc?.plc_z_is_up ?? true}
                    eStopOk={!(plc?.emergency_stop ?? false)}
                    systemMode={systemMode}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Warehouse Operations Tab: Warehouse Map 3x3 + Delivery Requests */}
          {activeTab === "warehouse" && (
            <div className="hmi-grid-container">
              <div className="split-view-layout">
                <div className="split-column">
                  <WarehouseGrid slots={mappedSlots} onSlotClick={handleSlotClick} />
                </div>
                <div className="split-column">
                  <DeliveryRequestsPanel
                    homeLat={0}
                    homeLon={0}
                    onLocationsSelected={(loc) => setLocations(loc)}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Tasks & Orders & Mission Queue Tab */}
          {activeTab === "tasks" && (
            <div className="hmi-grid-container">
              <MissionQueuePanel />
              <div style={{ marginTop: "1rem" }}>
                <DeliveryRequestsPanel
                  homeLat={0}
                  homeLon={0}
                  onLocationsSelected={(loc) => setLocations(loc)}
                />
              </div>
            </div>
          )}

          {/* Logs Tab */}
          {activeTab === "logs" && (
            <div className="hmi-grid-container">
              <SystemLog initialLogs={logs} />
            </div>
          )}

          {/* Settings Tab: Standalone Full Page for Hardware & System Configuration */}
          {activeTab === "settings" && (
            <SettingsView
              devices={devices}
              onRefreshDevices={refreshSystemState}
              sysWsConnected={sysWsConnected}
              isRobotOnline={isRobotOnline}
              isPlcOnline={isPlcOnline}
              droneOnline={droneOnline}
              cameraActive={cameraActive}
            />
          )}
        </main>
      </div>

      {/* Central HMI Modal Manager */}
      <ModalManager
        activeModal={activeModal}
        modalData={modalData}
        onClose={() => setActiveModal(null)}
        onConfirmAction={handleConfirmModalAction}
        onResetEStop={async () => {
          addLog("INFO", "Resetting PLC E-STOP...");
          try {
            await sendPlcCommand("reset");
          } catch (err) {
            addLog("ERROR", `Failed to reset PLC: ${err}`);
          }
        }}
      />
    </div>
  );
}

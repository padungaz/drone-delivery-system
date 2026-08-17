import { useState, useEffect } from "react";
import { useIntralogisticsWS } from "../hooks/useIntralogisticsWS";
import { useWebSocket } from "../hooks/useWebSocket";
import { SystemHeader } from "./layout/SystemHeader";
import { SidebarNavigation, type NavTab } from "./layout/SidebarNavigation";
import { RobotStatusCard } from "./robot/RobotStatusCard";
import { RobotDigitalTwin } from "./robot/RobotDigitalTwin";
import { JointControlPanel } from "./robot/JointControlPanel";
import { JogController } from "./robot/JogController";
import { WarehouseGrid, type SlotData } from "./warehouse/WarehouseGrid";
import { TaskMonitor } from "./task/TaskMonitor";
import { MissionQueuePanel } from "./task/MissionQueuePanel";

import { QuickControlPanel } from "./system/QuickControlPanel";
import { PLCMonitor } from "./plc/PLCMonitor";
import { CameraVision } from "./vision/CameraVision";
import { SystemLog, type LogItem } from "./system/SystemLog";
import { ModalManager, type ModalType } from "./system/ModalManager";
import { ManualControlModal } from "./ManualControlModal";
import { MapPanel } from "./MapPanel";
import { TelemetryPanel } from "./TelemetryPanel";
import { DeliveryRequestsPanel } from "./DeliveryRequestsPanel";
import { ControlButtons } from "./ControlButtons";
import {
  sendRobotCommand,
  sendPlcCommand,
  getDeviceLogs,
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
  const [isManualModalOpen, setManualModalOpen] = useState(false);

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
  } = useIntralogisticsWS();

  // Real UAV Drone Telemetry Hook
  const { telemetry, droneOnline } = useWebSocket();

  // Drone Mission Locations state
  const [locations, setLocations] = useState<MissionLocations>(DEFAULT_LOCATIONS);

  // Device logs state
  const [logs, setLogs] = useState<LogItem[]>([]);

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
    const interval = setInterval(fetchRealLogs, 4000);
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
    setLogs((prev) => [newLog, ...prev]);
  };

  // E-STOP Trigger -> Send real PLC stop command
  const handleEStopClick = async () => {
    setModalData({ reason: "Operator Pressed E-STOP button on Header" });
    setActiveModal("safety_alarm");
    addLog("ERROR", "🚨 EMERGENCY STOP TRIGGERED BY OPERATOR!");
    try {
      await sendPlcCommand("stop");
    } catch (err) {
      addLog("ERROR", `Failed to send PLC E-STOP: ${err}`);
    }
  };

  // Map real storage slots to WarehouseGrid format
  const mappedSlots: SlotData[] = storage.length > 0
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

  // Execute Real Robot / PLC Commands
  const handleQuickCommand = async (cmd: string, payload?: Record<string, unknown>) => {
    const slot = (payload?.slot as string) || "A2";
    if (cmd === "PICK" || cmd === "STORE") {
      setModalData({
        title: "XÁC NHẬN THAO TÁC",
        actionText: `${cmd} từ/vào ô kho ${slot}?`,
        productId: `PRD-100${slot}`,
        cmd,
        slot,
      });
      setActiveModal("confirm_action");
    } else {
      addLog("INFO", `Gửi lệnh phần cứng: ${cmd}`);
      try {
        if (cmd === "HOME") {
          await sendRobotCommand("HOME");
        } else if (cmd === "PLACE_PAD") {
          await sendRobotCommand("PLACE", "DOCK");
        } else if (cmd === "OPEN_GRIPPER") {
          await sendRobotCommand("GRIPPER_OPEN");
        } else if (cmd === "CLOSE_GRIPPER") {
          await sendRobotCommand("GRIPPER_CLOSE");
        }
      } catch (err) {
        addLog("ERROR", `Lỗi thực thi lệnh ${cmd}: ${err}`);
      }
    }
  };

  // Confirm Modal action handler
  const handleConfirmModalAction = async (p: any) => {
    const cmd = p?.cmd || "PICK";
    const slot = p?.slot || "A2";
    addLog("INFO", `Thực thi lệnh ${cmd} slot ${slot}...`);
    try {
      if (cmd === "PICK") {
        await sendRobotCommand("PICK", slot);
      } else if (cmd === "STORE") {
        await sendRobotCommand("STORE", slot);
      }
    } catch (err) {
      addLog("ERROR", `Lỗi gửi lệnh ${cmd}: ${err}`);
    }
  };

  return (
    <div className="hmi-dashboard-wrapper">
      <SystemHeader
        sysWsConnected={sysWsConnected}
        uavOnline={droneOnline}
        plcOnline={isPlcOnline}
        robotOnline={isRobotOnline}
        cameraOnline={cameraActive}
        onEStopClick={handleEStopClick}
      />

      <div className="hmi-main-layout">
        <SidebarNavigation
          activeTab={activeTab}
          onTabChange={(tab) => {
            setActiveTab(tab);
            if (tab === "settings") {
              setActiveModal("hardware_config");
            }
          }}
        />

        <main className="hmi-content-area">
          {/* Main Tab View: HMI Smart Intralogistics Cell Dashboard */}
          {(activeTab === "dashboard" || activeTab === "robot" || activeTab === "plc") && (
            <div className="hmi-grid-container">
              {/* Row 1: Robot Status, Digital Twin, Joint & Gripper */}
              <div className="hmi-grid-row row-3-cols">
                <RobotStatusCard
                  state={robot?.status || (isRobotOnline ? "IDLE" : "OFFLINE")}
                  mode={robot?.auto_mode ? "AUTO" : "MANUAL"}
                  servo={isRobotOnline}
                  brake={isRobotOnline}
                  power={isRobotOnline}
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
                  taskId={activeMission ? `#MISSION-${activeMission.id}` : "#TASK-READY"}
                  taskName={
                    activeMission
                      ? `${activeMission.mission_type} (${activeMission.target_slot})`
                      : "NO ACTIVE MISSION"
                  }
                  progressPercent={
                    activeMission?.status === "COMPLETED"
                      ? 100
                      : stationOp
                      ? 50
                      : 0
                  }
                />
                <div className="controls-combined-col">
                  <QuickControlPanel onCommand={handleQuickCommand} />
                  <div style={{ marginTop: "1rem" }}>
                    <JogController
                      onJogCommand={async (axis, step) => {
                        addLog("INFO", `Jogging ${axis} step=${step}mm`);
                        try {
                          await sendRobotCommand("JOG", axis);
                        } catch {
                          // Ignore
                        }
                      }}
                    />
                  </div>
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
                />
                <CameraVision
                  cameraActive={cameraActive}
                  productId={stationOp?.product_id || activeMission?.product_id || "PRD-TEST-1001"}
                  status={cameraActive ? "DETECTED" : "DETECTED"}
                />
                <SystemLog initialLogs={logs} />
              </div>
            </div>
          )}

          {/* UAV Drone Operations Tab: Live GPS Map + Telemetry + Flight Controls */}
          {(activeTab === "uav" || activeTab === "warehouse") && (
            <div className="hmi-grid-container">
              <div className="split-view-layout">
                <div className="split-column">
                  <MapPanel telemetry={telemetry} locations={locations} droneOnline={droneOnline} />
                  <div style={{ marginTop: "1rem" }}>
                    <TelemetryPanel telemetry={telemetry} droneOnline={droneOnline} />
                  </div>
                  <div style={{ marginTop: "1rem" }}>
                    <ControlButtons
                      locations={locations}
                      telemetry={telemetry}
                      droneOnline={droneOnline}
                      onOpenManual={() => setManualModalOpen(true)}
                    />
                  </div>
                </div>

                <div className="split-column">
                  <WarehouseGrid slots={mappedSlots} onSlotClick={handleSlotClick} />
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
        </main>
      </div>

      {/* UAV Drone Manual Control Modal */}
      <ManualControlModal
        isOpen={isManualModalOpen}
        onClose={() => setManualModalOpen(false)}
        droneStatus={telemetry}
        locations={locations}
      />

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

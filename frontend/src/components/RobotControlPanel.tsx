import { useState } from "react";
import type { RobotState } from "../types/drone";
import {
  sendRobotCommand,
  robotEmergencyStop,
  sendRobotDoneSignal,
  sendRawDeviceCommand,
  testDeviceConnection,
} from "../services/api";

interface Props {
  robot: RobotState | null;
}

interface SocketLogEntry {
  id: number;
  time: string;
  type: "send" | "response" | "error" | "info";
  text: string;
}

type RobotPanelTab = "operation" | "socket_tester";

export function RobotControlPanel({ robot }: Props) {
  const [activeTab, setActiveTab] = useState<RobotPanelTab>("operation");
  const [targetSlot, setTargetSlot] = useState("A1");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  // Socket Tester state inside Robot Panel
  const [customLuaCmd, setCustomLuaCmd] = useState("MOVE_HOME");
  const [luaTarget, setLuaTarget] = useState("");
  const [socketLogs, setSocketLogs] = useState<SocketLogEntry[]>([
    {
      id: 1,
      time: new Date().toLocaleTimeString(),
      type: "info",
      text: "⚡ Fairino Robot TCP Socket Tester sẵn sàng (Port 8090 / Socket 1).",
    },
  ]);

  const addSocketLog = (type: "send" | "response" | "error" | "info", text: string) => {
    setSocketLogs((prev) => [
      ...prev,
      {
        id: Date.now() + Math.random(),
        time: new Date().toLocaleTimeString(),
        type,
        text,
      },
    ]);
  };

  const handleHome = async () => {
    setLoading(true);
    setMsg(null);
    addSocketLog("send", ">>> SENDING SOCKET CMD: MOVE_HOME");
    try {
      const res = await sendRobotCommand("MOVE_HOME");
      if (!res.ok) {
        const errText = await res.text();
        setMsg(`Lỗi ${res.status}: ${errText}`);
        addSocketLog("error", `<<< ERROR: ${errText}`);
        return;
      }
      const data = await res.json();
      setMsg("🏠 Đã gửi lệnh Robot di chuyển về HOME thành công!");
      addSocketLog("response", `<<< RESPONSE: ${data.message || "SUCCESS MOVE_HOME"}`);
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
      addSocketLog("error", `<<< EXCEPTION: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const handlePick = async () => {
    setLoading(true);
    setMsg(null);
    addSocketLog("send", `>>> SENDING SOCKET CMD: PICK ${targetSlot}`);
    try {
      const res = await sendRobotCommand("PICK", targetSlot);
      if (!res.ok) {
        const errText = await res.text();
        setMsg(`Lỗi ${res.status}: ${errText}`);
        addSocketLog("error", `<<< ERROR: ${errText}`);
        return;
      }
      const data = await res.json();
      setMsg(`📦 Đã gửi lệnh Robot PICK -> Target: ${targetSlot}`);
      addSocketLog("response", `<<< RESPONSE: ${data.message || `SUCCESS PICK ${targetSlot}`}`);
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
      addSocketLog("error", `<<< EXCEPTION: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleStore = async () => {
    setLoading(true);
    setMsg(null);
    addSocketLog("send", `>>> SENDING SOCKET CMD: STORE ${targetSlot}`);
    try {
      const res = await sendRobotCommand("STORE", targetSlot);
      if (!res.ok) {
        const errText = await res.text();
        setMsg(`Lỗi ${res.status}: ${errText}`);
        addSocketLog("error", `<<< ERROR: ${errText}`);
        return;
      }
      const data = await res.json();
      setMsg(`📥 Đã gửi lệnh Robot STORE -> Target: ${targetSlot}`);
      addSocketLog("response", `<<< RESPONSE: ${data.message || `SUCCESS STORE ${targetSlot}`}`);
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
      addSocketLog("error", `<<< EXCEPTION: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const handlePlace = async () => {
    setLoading(true);
    setMsg(null);
    addSocketLog("send", ">>> SENDING SOCKET CMD: PLACE PAD");
    try {
      const res = await sendRobotCommand("PLACE", "PAD");
      if (!res.ok) {
        const errText = await res.text();
        setMsg(`Lỗi ${res.status}: ${errText}`);
        addSocketLog("error", `<<< ERROR: ${errText}`);
        return;
      }
      const data = await res.json();
      setMsg("📤 Đã gửi lệnh Robot PLACE -> Target: PAD");
      addSocketLog("response", `<<< RESPONSE: ${data.message || "SUCCESS PLACE PAD"}`);
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
      addSocketLog("error", `<<< EXCEPTION: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleEStop = async () => {
    setLoading(true);
    setMsg(null);
    addSocketLog("send", ">>> SENDING EMERGENCY ESTOP OVER SOCKET");
    try {
      const res = await robotEmergencyStop();
      if (!res.ok) {
        const errText = await res.text();
        setMsg(`Lỗi ${res.status}: ${errText}`);
        addSocketLog("error", `<<< ERROR: ${errText}`);
        return;
      }
      const data = await res.json();
      setMsg(data.message || "ĐÃ KÍCH HOẠT DỪNG KHẨN CẤP ROBOT!");
      addSocketLog("response", `<<< RESPONSE: ESTOP EXECUTED`);
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
      addSocketLog("error", `<<< EXCEPTION: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDoneSignal = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await sendRobotDoneSignal();
      if (!res.ok) {
        const errText = await res.text();
        setMsg(`Lỗi ${res.status}: ${errText}`);
        return;
      }
      const data = await res.json();
      setMsg(data.message || "✅ Đã nhận tín hiệu ROBOT_DONE!");
      addSocketLog("info", "✅ Received signal ROBOT_DONE");
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  // Socket Tester helpers
  const handlePingSocket = async () => {
    setLoading(true);
    addSocketLog("send", ">>> PING SOCKET TEST -> STATUS");
    try {
      const res = await testDeviceConnection("ROBOT01");
      if (res.ok) {
        const data = await res.json();
        const type = data.success ? "response" : "error";
        addSocketLog(type, `<<< ${data.message} | Response: "${data.response_text}" | Latency: ${data.latency_ms}ms`);
      }
    } catch (err) {
      addSocketLog("error", `<<< PING FAILED: ${err instanceof Error ? err.message : "Failed"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSendRawLuaSocket = async (cmdOverride?: string, targetOverride?: string) => {
    const cmd = cmdOverride || customLuaCmd;
    const tgt = targetOverride !== undefined ? targetOverride : luaTarget;
    if (!cmd.trim()) return;

    setLoading(true);
    const fullCmdStr = tgt ? `${cmd} ${tgt}` : cmd;
    addSocketLog("send", `>>> SENDING RAW LUA PAYLOAD: ${fullCmdStr}`);

    try {
      const res = await sendRawDeviceCommand("ROBOT01", cmd, tgt);
      if (res.ok) {
        const data = await res.json();
        const isSuccess = data.status === "DONE" || data.result === "SUCCESS";
        addSocketLog(isSuccess ? "response" : "error", `<<< RESPONSE: ${data.message}`);
      } else {
        const errText = await res.text();
        addSocketLog("error", `<<< SERVER ERROR: ${errText}`);
      }
    } catch (err) {
      addSocketLog("error", `<<< EXCEPTION: ${err instanceof Error ? err.message : "Failed"}`);
    } finally {
      setLoading(false);
    }
  };

  const statusClass =
    robot?.status === "IDLE"
      ? "status-online"
      : robot?.status === "BUSY"
      ? "status-busy"
      : "status-offline";

  return (
    <div className="panel robot-panel">
      <div className="panel-header-inline">
        <h3>🤖 Robot FAIRINO Manipulator</h3>
        <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
          <span className={`status-badge ${statusClass}`}>
            {robot?.status ?? "OFFLINE"}
          </span>
          {robot?.simulator_mode && (
            <span className="status-badge status-busy" title="Chế độ mô phỏng Robot">
              SIM
            </span>
          )}
        </div>
      </div>

      <div className="robot-info-grid">
        <div>
          <span className="label font-bold">Trạng thái:</span>{" "}
          <span>{robot?.status || "IDLE"}</span>
        </div>
        <div>
          <span className="label font-bold">Vị trí hiện tại:</span>{" "}
          <span>{robot?.current_task || "HOME"}</span>
        </div>
      </div>

      {/* Sub-Tab Navigation Bar inside Robot Panel */}
      <div style={{ display: "flex", gap: "8px", marginTop: "12px", borderBottom: "1px solid rgba(255, 255, 255, 0.1)", paddingBottom: "8px" }}>
        <button
          type="button"
          className={`btn btn-sm ${activeTab === "operation" ? "btn-primary" : "btn-secondary"}`}
          onClick={() => setActiveTab("operation")}
        >
          🎮 Vận Hành Tác Vụ
        </button>
        <button
          type="button"
          className={`btn btn-sm ${activeTab === "socket_tester" ? "btn-primary" : "btn-secondary"}`}
          onClick={() => setActiveTab("socket_tester")}
        >
          🔌 Socket Tester Console (LUA)
        </button>
      </div>

      {/* TAB 1: Warehouse Operation Control */}
      {activeTab === "operation" && (
        <div className="robot-action-box mt-2">
          <div className="form-group-inline">
            <label htmlFor="slot-select" className="font-bold">Chọn Ô Target Kho:</label>
            <select
              id="slot-select"
              className="form-control"
              value={targetSlot}
              onChange={(e) => setTargetSlot(e.target.value)}
              style={{ background: "#0f172a", color: "#00F0FF", fontWeight: "bold" }}
            >
              {["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3", "PAD"].map((s) => (
                <option key={s} value={s}>
                  {s === "PAD" ? "Sàn Đáp PAD" : `Ô ${s}`}
                </option>
              ))}
            </select>
          </div>

          <div className="robot-btn-group mt-1" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleHome}
              disabled={loading}
            >
              🏠 MOVE_HOME
            </button>

            <button
              type="button"
              className="btn btn-primary"
              onClick={handlePick}
              disabled={loading}
            >
              📦 PICK ({targetSlot})
            </button>

            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleStore}
              disabled={loading}
            >
              📥 STORE ({targetSlot})
            </button>

            <button
              type="button"
              className="btn btn-outline"
              onClick={handlePlace}
              disabled={loading}
            >
              📤 PLACE (PAD)
            </button>

            <button
              type="button"
              className="btn btn-success"
              onClick={handleDoneSignal}
              disabled={loading}
              title="Gửi tín hiệu báo Robot đã hoàn thành tác vụ (ROBOT_DONE) về Backend"
            >
              ✅ Signal DONE
            </button>

            <button
              type="button"
              className="btn btn-danger"
              onClick={handleEStop}
              disabled={loading}
            >
              🛑 E-Stop
            </button>
          </div>
        </div>
      )}

      {/* TAB 2: Embedded Fairino TCP Socket Tester & Interactive Console */}
      {activeTab === "socket_tester" && (
        <div style={{ marginTop: "10px", background: "#060911", padding: "12px", borderRadius: "8px", border: "1px solid rgba(0, 240, 255, 0.25)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
            <div style={{ fontWeight: "bold", fontSize: "0.85rem", color: "#00F0FF" }}>
              🔌 Fairino LUA Socket Tester (Port 8090 / Socket 1)
            </div>
            <div style={{ display: "flex", gap: "6px" }}>
              <button type="button" className="btn btn-outline btn-sm" onClick={handlePingSocket} disabled={loading} style={{ fontSize: "0.75rem" }}>
                🔍 Ping Socket
              </button>
              <button type="button" className="btn btn-outline btn-sm" onClick={() => setSocketLogs([])} style={{ fontSize: "0.75rem" }}>
                🗑️ Clear Logs
              </button>
            </div>
          </div>

          {/* Quick LUA Command Buttons */}
          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "8px" }}>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => handleSendRawLuaSocket("MOVE_HOME")}>🏠 MOVE_HOME</button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => handleSendRawLuaSocket("STATUS")}>📊 STATUS</button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => handleSendRawLuaSocket("PICK", "A1")}>📦 PICK A1</button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => handleSendRawLuaSocket("STORE", "B2")}>📥 STORE B2</button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => handleSendRawLuaSocket("PICK", "C3")}>📦 PICK C3</button>
            <button type="button" className="btn btn-warning btn-sm" onClick={() => handleSendRawLuaSocket("ESTOP")}>🚨 ESTOP</button>
          </div>

          {/* Custom LUA Command Bar */}
          <div style={{ display: "flex", gap: "6px", marginBottom: "8px" }}>
            <input
              type="text"
              className="form-control"
              placeholder="Lệnh LUA thô (VD: MOVE_HOME, PICK)..."
              value={customLuaCmd}
              onChange={(e) => setCustomLuaCmd(e.target.value)}
              style={{ flex: 2, fontFamily: "monospace", fontSize: "0.85rem" }}
            />
            <input
              type="text"
              className="form-control"
              placeholder="Target (VD: A1, B2)..."
              value={luaTarget}
              onChange={(e) => setLuaTarget(e.target.value)}
              style={{ flex: 1, fontFamily: "monospace", fontSize: "0.85rem" }}
            />
            <button
              type="button"
              className="btn btn-success btn-sm"
              onClick={() => handleSendRawLuaSocket()}
              disabled={loading}
            >
              ▶️ Gửi LUA
            </button>
          </div>

          {/* Socket Log Output Terminal Box */}
          <div style={{ background: "#020408", border: "1px solid rgba(255, 255, 255, 0.08)", borderRadius: "6px", padding: "8px", height: "160px", overflowY: "auto", fontFamily: "monospace", fontSize: "0.8rem" }}>
            {socketLogs.map((log) => (
              <div key={log.id} style={{ marginBottom: "3px", color: log.type === "response" ? "#10b981" : log.type === "error" ? "#ef4444" : log.type === "send" ? "#00F0FF" : "#94a3b8" }}>
                <span style={{ color: "#64748b" }}>[{log.time}]</span> {log.text}
              </div>
            ))}
          </div>
        </div>
      )}

      {msg && <div className="panel-msg mt-1">{msg}</div>}
    </div>
  );
}

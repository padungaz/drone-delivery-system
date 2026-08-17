import { useState } from "react";

export interface LogItem {
  id: string;
  time: string;
  level: "INFO" | "WARN" | "ERROR";
  message: string;
}

const DEFAULT_LOGS: LogItem[] = [
  { id: "1", time: "21:17:46", level: "INFO", message: "WebSocket connected successfully" },
  { id: "2", time: "21:17:44", level: "INFO", message: "Robot status: IDLE" },
  { id: "3", time: "21:17:42", level: "INFO", message: "PLC S7-1200 connected" },
  { id: "4", time: "21:17:40", level: "INFO", message: "Slot A2 detected product: PRD-1001" },
  { id: "5", time: "21:17:38", level: "WARN", message: "Slot B2 is moving..." },
  { id: "6", time: "21:17:36", level: "INFO", message: "Task PICK A2 started" },
  { id: "7", time: "21:17:34", level: "INFO", message: "System initialization completed" },
];

interface Props {
  initialLogs?: LogItem[];
}

export function SystemLog({ initialLogs = DEFAULT_LOGS }: Props) {
  const [logs, setLogs] = useState<LogItem[]>(initialLogs);
  const [filter, setFilter] = useState<"ALL" | "INFO" | "WARN" | "ERROR">("ALL");

  const filteredLogs = logs.filter((log) => {
    if (filter === "ALL") return true;
    return log.level === filter;
  });

  const clearLogs = () => {
    setLogs([]);
  };

  return (
    <div className="hmi-card system-log-card">
      <div className="card-header flex-between">
        <h3>📑 SYSTEM EVENT LOG</h3>
        <div className="log-actions">
          <div className="log-filters">
            {(["ALL", "INFO", "WARN", "ERROR"] as const).map((f) => (
              <button
                key={f}
                type="button"
                className={`filter-btn ${filter === f ? "active" : ""}`}
                onClick={() => setFilter(f)}
              >
                {f}
              </button>
            ))}
          </div>
          <button type="button" className="btn-clear" onClick={clearLogs}>
            🗑️ Clear
          </button>
        </div>
      </div>

      <div className="card-body terminal-log-window">
        {filteredLogs.length === 0 ? (
          <div className="empty-logs">Không có log nào.</div>
        ) : (
          filteredLogs.map((log) => (
            <div key={log.id} className={`log-line level-${log.level.toLowerCase()}`}>
              <span className="log-time">{log.time}</span>
              <span className={`log-level-badge level-${log.level.toLowerCase()}`}>
                {log.level}
              </span>
              <span className="log-msg">{log.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

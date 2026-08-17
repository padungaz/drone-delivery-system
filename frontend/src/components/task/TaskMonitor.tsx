export interface TaskStep {
  id: number;
  label: string;
  status: "completed" | "in_progress" | "pending";
}

export interface TaskQueueItem {
  id: string;
  name: string;
  status: string;
}

interface Props {
  taskId?: string;
  taskName?: string;
  progressPercent?: number;
  steps?: TaskStep[];
  queue?: TaskQueueItem[];
}

const DEFAULT_STEPS: TaskStep[] = [
  { id: 1, label: "1. Move Home", status: "completed" },
  { id: 2, label: "2. Move Above A2", status: "completed" },
  { id: 3, label: "3. Lower To Pick Position", status: "completed" },
  { id: 4, label: "4. Close Gripper (Grip)", status: "in_progress" },
  { id: 5, label: "5. Lift Up", status: "pending" },
  { id: 6, label: "6. Move To Place / Store", status: "pending" },
];

const DEFAULT_QUEUE: TaskQueueItem[] = [
  { id: "#TASK-20260816-046", name: "STORE B3", status: "Chờ" },
  { id: "#TASK-20260816-047", name: "PLACE PAD (N1)", status: "Chờ" },
  { id: "#TASK-20260816-048", name: "PICK C3", status: "Chờ" },
];

export function TaskMonitor({
  taskId = "#TASK-20260816-005",
  taskName = "PICK A2",
  progressPercent = 68,
  steps = DEFAULT_STEPS,
  queue = DEFAULT_QUEUE,
}: Props) {
  return (
    <div className="hmi-card task-monitor-card">
      <div className="card-header flex-between">
        <h3>📋 CURRENT TASK MONITOR</h3>
        <span className="task-id-badge">{taskId}</span>
      </div>

      <div className="card-body task-monitor-layout">
        <div className="active-task-hero">
          <div className="task-title-bar flex-between">
            <h4>{taskName}</h4>
            <span className="progress-value">{progressPercent}%</span>
          </div>

          <div className="progress-bar-bg main-progress">
            <div
              className="progress-bar-fill animated-stripes"
              style={{ width: `${progressPercent}%` }}
            ></div>
          </div>

          <div className="task-stepper-list">
            {steps.map((st) => (
              <div
                key={`step-${st.id}`}
                className={`stepper-item ${st.status}`}
              >
                <div className="stepper-icon">
                  {st.status === "completed" && "✓"}
                  {st.status === "in_progress" && "🔵"}
                  {st.status === "pending" && "○"}
                </div>
                <span className="stepper-label">{st.label}</span>
                <span className="stepper-status-text">
                  {st.status === "completed" && "Hoàn thành ✓"}
                  {st.status === "in_progress" && "Đang thực hiện..."}
                  {st.status === "pending" && "Chờ thực hiện"}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="task-queue-section">
          <div className="queue-header flex-between">
            <h5>TASK QUEUE ({queue.length})</h5>
            <small>Tự động thực hiện</small>
          </div>

          <div className="queue-list">
            {queue.map((q, idx) => (
              <div key={q.id} className="queue-item flex-between">
                <div className="queue-info">
                  <span className="queue-index">{idx + 1}</span>
                  <span className="queue-name">{q.name}</span>
                </div>
                <span className="queue-id">{q.id}</span>
                <span className="queue-status-badge">{q.status}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

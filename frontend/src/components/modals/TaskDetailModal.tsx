interface Props {
  isOpen: boolean;
  taskId?: string;
  opType?: string;
  target?: string;
  status?: string;
  progressPercent?: number;
  startTime?: string;
  etaTime?: string;
  onClose: () => void;
}

export function TaskDetailModal({
  isOpen,
  taskId = "#TASK-20260816-005",
  opType = "PICK",
  target = "A2",
  status = "Đang thực hiện",
  progressPercent = 68,
  startTime = "21:16:12",
  etaTime = "21:18:30",
  onClose,
}: Props) {
  if (!isOpen) return null;

  return (
    <div className="hmi-modal-backdrop">
      <div className="hmi-modal-dialog task-detail-modal">
        <div className="modal-header flex-between">
          <h4>THÔNG TIN NHIỆM VỤ</h4>
          <span className="task-id-tag font-mono">{taskId}</span>
          <button type="button" className="btn-close-x" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="modal-body">
          <div className="info-grid">
            <div className="info-row flex-between">
              <span>Task ID:</span>
              <strong className="font-mono text-cyan">{taskId}</strong>
            </div>
            <div className="info-row flex-between">
              <span>Loại nhiệm vụ:</span>
              <strong className="text-cyan">{opType}</strong>
            </div>
            <div className="info-row flex-between">
              <span>Target (Ô kho/Pad):</span>
              <strong className="font-mono">{target}</strong>
            </div>
            <div className="info-row flex-between">
              <span>Trạng thái:</span>
              <strong className="text-yellow">{status}</strong>
            </div>
            <div className="info-row flex-between">
              <span>Bắt đầu lúc:</span>
              <span className="font-mono">{startTime}</span>
            </div>
            <div className="info-row flex-between">
              <span>Dự kiến hoàn thành:</span>
              <span className="font-mono">{etaTime}</span>
            </div>
          </div>

          <div className="progress-section">
            <div className="flex-between progress-header">
              <span>Tiến độ:</span>
              <strong className="text-cyan font-mono">{progressPercent}%</strong>
            </div>
            <div className="progress-bar-bg">
              <div
                className="progress-bar-fill animated-stripes"
                style={{ width: `${progressPercent}%` }}
              ></div>
            </div>
          </div>
        </div>

        <div className="modal-footer flex-center">
          <button type="button" className="btn-hmi btn-secondary" onClick={onClose}>
            CLOSE
          </button>
        </div>
      </div>
    </div>
  );
}

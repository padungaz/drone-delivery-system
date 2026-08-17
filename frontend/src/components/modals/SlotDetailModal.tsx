interface Props {
  isOpen: boolean;
  slotId?: string;
  productId?: string;
  productName?: string;
  status?: string;
  timeStored?: string;
  missionRef?: string;
  onClose: () => void;
  onPick?: (slotId: string) => void;
  onStore?: (slotId: string) => void;
}

export function SlotDetailModal({
  isOpen,
  slotId = "A2",
  productId = "PRD-1002",
  productName = "Motor Gearbox",
  status = "Occupied",
  timeStored = "16/08/2026 20:45:12",
  missionRef = "PICK A2",
  onClose,
  onPick,
  onStore,
}: Props) {
  if (!isOpen) return null;

  return (
    <div className="hmi-modal-backdrop">
      <div className="hmi-modal-dialog slot-detail-modal">
        <div className="modal-header flex-between">
          <h4>CHI TIẾT Ô KHO {slotId}</h4>
          <span className={`status-pill ${status.toLowerCase()}`}>
            ● {status.toUpperCase()}
          </span>
          <button type="button" className="btn-close-x" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="modal-body">
          <div className="info-grid">
            <div className="info-row flex-between">
              <span className="info-label">Product ID:</span>
              <strong className="info-val font-mono text-cyan">{productId}</strong>
            </div>
            <div className="info-row flex-between">
              <span className="info-label">Tên sản phẩm:</span>
              <span className="info-val">{productName}</span>
            </div>
            <div className="info-row flex-between">
              <span className="info-label">Trạng thái:</span>
              <strong className="info-val text-green">{status}</strong>
            </div>
            <div className="info-row flex-between">
              <span className="info-label">Thời gian lưu:</span>
              <span className="info-val font-mono">{timeStored}</span>
            </div>
            <div className="info-row flex-between">
              <span className="info-label">Nhiệm vụ liên quan:</span>
              <span className="info-val text-yellow font-mono">{missionRef}</span>
            </div>
          </div>
        </div>

        <div className="modal-footer flex-center">
          {onPick && (
            <button
              type="button"
              className="btn-hmi btn-green"
              onClick={() => onPick(slotId)}
            >
              📦 PICK
            </button>
          )}
          {onStore && (
            <button
              type="button"
              className="btn-hmi btn-orange"
              onClick={() => onStore(slotId)}
            >
              📥 STORE
            </button>
          )}
          <button type="button" className="btn-hmi btn-secondary" onClick={onClose}>
            CLOSE
          </button>
        </div>
      </div>
    </div>
  );
}

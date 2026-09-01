import { useState } from "react";

interface Props {
  isOpen: boolean;
  initialSlot?: string;
  onClose: () => void;
  onConfirm?: (slot: string, taskType: string, note?: string) => void;
}

export function InputSlotModal({
  isOpen,
  initialSlot = "B1",
  onClose,
  onConfirm,
}: Props) {
  const [slot, setSlot] = useState(initialSlot);
  const [taskType, setTaskType] = useState("PICK");
  const [note, setNote] = useState("");

  if (!isOpen) return null;

  const handleConfirm = () => {
    if (onConfirm) {
      onConfirm(slot, taskType, note);
    }
    onClose();
  };

  return (
    <div className="hmi-modal-backdrop">
      <div className="hmi-modal-dialog input-slot-modal">
        <div className="modal-header flex-between">
          <h4>📍 NHẬP VỊ TRÍ Ô KHO</h4>
          <button type="button" className="btn-close-x" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="modal-body">
          <div className="form-group">
            <label>Chọn ô kho:</label>
            <select
              value={slot}
              onChange={(e) => setSlot(e.target.value)}
              className="hmi-input font-mono"
            >
              {["A1", "A2", "A3", "B1", "B2", "B3"].map((s) => (
                <option key={s} value={s}>
                  Slot {s}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Nhiệm vụ:</label>
            <select
              value={taskType}
              onChange={(e) => setTaskType(e.target.value)}
              className="hmi-input"
            >
              <option value="PICK">PICK (Gắp từ ô kho)</option>
              <option value="STORE">STORE (Đặt vào ô kho)</option>
              <option value="PLACE_PAD">PLACE PAD (Đặt lên Drone N1)</option>
            </select>
          </div>

          <div className="form-group">
            <label>Ghi chú (tùy chọn):</label>
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Nhập ghi chú..."
              className="hmi-input"
            />
          </div>
        </div>

        <div className="modal-footer flex-center">
          <button type="button" className="btn-hmi btn-secondary" onClick={onClose}>
            CANCEL
          </button>
          <button type="button" className="btn-hmi btn-primary" onClick={handleConfirm}>
            CONFIRM
          </button>
        </div>
      </div>
    </div>
  );
}

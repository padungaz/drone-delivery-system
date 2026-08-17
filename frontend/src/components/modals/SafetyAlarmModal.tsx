interface Props {
  isOpen: boolean;
  reason?: string;
  onReset: () => void;
  onClose: () => void;
}

export function SafetyAlarmModal({
  isOpen,
  reason = "Operator Pressed E-STOP",
  onReset,
  onClose,
}: Props) {
  if (!isOpen) return null;

  return (
    <div className="hmi-modal-backdrop estop-backdrop">
      <div className="hmi-modal-dialog safety-alarm-modal">
        <div className="modal-header flex-between">
          <h4 className="text-red">🚨 CẢNH BÁO AN TOÀN</h4>
          <button type="button" className="btn-close-x" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="modal-body text-center">
          <div className="alarm-flashing-icon">🛑</div>
          <h3 className="estop-active-title text-red font-heading">EMERGENCY STOP ACTIVE!</h3>
          <p className="estop-subtitle">
            Hệ thống đã dừng tất cả các thiết bị. Bạn có muốn RESET hệ thống?
          </p>

          <div className="alarm-details-card">
            <div className="alarm-row flex-between">
              <span>Lý do:</span>
              <strong className="text-yellow">{reason}</strong>
            </div>
            <div className="alarm-row flex-between">
              <span>Trạng thái Robot:</span>
              <strong className="text-red">STOPPED (STOP_EMERGENCY)</strong>
            </div>
            <div className="alarm-row flex-between">
              <span>Trạng thái PLC:</span>
              <strong className="text-red">E-STOP TRIGGERED (DB2.6)</strong>
            </div>
          </div>
        </div>

        <div className="modal-footer flex-center">
          <button type="button" className="btn-hmi btn-secondary" onClick={onClose}>
            CANCEL
          </button>
          <button type="button" className="btn-hmi btn-danger-reset" onClick={onReset}>
            🔄 RESET E-STOP
          </button>
        </div>
      </div>
    </div>
  );
}

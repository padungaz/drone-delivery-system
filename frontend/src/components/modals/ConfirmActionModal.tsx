interface Props {
  isOpen: boolean;
  title?: string;
  actionText?: string;
  productId?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmActionModal({
  isOpen,
  title = "XÁC NHẬN THAO TÁC",
  actionText = "PICK từ ô kho A2?",
  productId = "PRD-1001",
  onConfirm,
  onCancel,
}: Props) {
  if (!isOpen) return null;

  return (
    <div className="hmi-modal-backdrop">
      <div className="hmi-modal-dialog confirm-modal">
        <div className="modal-header flex-between">
          <h4 className="text-yellow">⚠️ {title}</h4>
          <button type="button" className="btn-close-x" onClick={onCancel}>
            ✕
          </button>
        </div>

        <div className="modal-body text-center">
          <div className="warning-icon-large">⚠️</div>
          <p className="confirm-msg">
            Bạn có chắc chắn muốn thực hiện <br />
            <strong className="text-cyan font-heading">{actionText}</strong>
          </p>
          <div className="product-tag font-mono">Product ID: {productId}</div>
        </div>

        <div className="modal-footer flex-center">
          <button type="button" className="btn-hmi btn-secondary" onClick={onCancel}>
            CANCEL
          </button>
          <button type="button" className="btn-hmi btn-primary" onClick={onConfirm}>
            CONFIRM
          </button>
        </div>
      </div>
    </div>
  );
}

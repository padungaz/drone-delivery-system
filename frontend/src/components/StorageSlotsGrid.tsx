import { useState, memo } from "react";
import type { StorageSlot } from "../types/drone";
import { clearStorageSlot, scanQR } from "../services/api";

interface Props {
  slots: StorageSlot[];
}

export const StorageSlotsGrid = memo(function StorageSlotsGrid({ slots }: Props) {
  const [selectedSlot, setSelectedSlot] = useState<StorageSlot | null>(null);
  const [qrInput, setQrInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  // Default 9 grid matrix A1..C3
  const gridNames = [
    ["A1", "A2", "A3"],
    ["B1", "B2", "B3"],
    ["C1", "C2", "C3"],
  ];

  const getSlotData = (name: string): StorageSlot | undefined => {
    return slots.find((s) => s.slot_name === name || `Slot-${s.id}` === name);
  };

  const handleClear = async (slotId: number | string) => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await clearStorageSlot(slotId);
      if (!res.ok) {
        const errText = await res.text();
        setMsg(`Lỗi ${res.status}: ${errText}`);
        return;
      }
      const data = await res.json();
      setMsg(data.message || `Đã xóa hàng / giải phóng ô kho ${slotId} thành công!`);
      setSelectedSlot(null);
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSimulateQR = async () => {
    if (!qrInput.trim()) return;
    setLoading(true);
    setMsg(null);
    try {
      const res = await scanQR(qrInput.trim());
      if (!res.ok) {
        const errText = await res.text();
        setMsg(`Lỗi ${res.status}: ${errText}`);
        return;
      }
      const data = await res.json();
      setMsg(data.message || `Đã quét QR [${qrInput}], gán vào ô thành công!`);
      setQrInput("");
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const isSlotOccupied = (slot?: StorageSlot): boolean => {
    if (!slot) return false;
    if (slot.status === "OCCUPIED") return true;
    if (slot.is_empty === false) return true;
    if (slot.product_id && slot.product_id.trim() !== "") return true;
    return false;
  };

  const isSlotReserved = (slot?: StorageSlot): boolean => {
    return slot?.status === "RESERVED";
  };

  const occupiedCount = slots.filter((s) => isSlotOccupied(s)).length;

  return (
    <div className="panel storage-slots-panel">
      <div className="panel-header-inline">
        <h3>🏬 Sơ đồ 9 Vị trí Lưu kho Tạm thời (Grid A1..C3)</h3>
        <span className="text-sm font-bold">
          Đang sử dụng: {occupiedCount} / 9 ô
        </span>
      </div>

      {/* 3x3 Visual Grid */}
      <div className="grid-3x3">
        {gridNames.map((row, rIdx) => (
          <div key={`row-${rIdx}`} className="grid-row">
            {row.map((slotName) => {
              const slot = getSlotData(slotName);
              const occupied = isSlotOccupied(slot);
              const reserved = isSlotReserved(slot);
              const isSelected = selectedSlot?.slot_name === slotName;

              let slotClass = "slot-empty";
              let statusLabel = "TRỐNG";

              if (occupied) {
                slotClass = "slot-occupied";
                statusLabel = "CÓ HÀNG";
              } else if (reserved) {
                slotClass = "slot-reserved";
                statusLabel = "ĐANG GIỮ";
              }

              return (
                <button
                  type="button"
                  key={slotName}
                  className={`slot-card ${slotClass} ${isSelected ? "selected" : ""}`}
                  onClick={() => setSelectedSlot(slot || null)}
                >
                  <div className="slot-header">
                    <span className="slot-name">{slotName}</span>
                    <span className="slot-badge">{statusLabel}</span>
                  </div>

                  <div className="slot-body">
                    {occupied ? (
                      <>
                        <div className="slot-product-id">📦 {slot?.product_id || `SP-${slotName}`}</div>
                        <div className="slot-qr text-sm">{slot?.qr_code || slot?.sender_name || "Mã QR"}</div>
                      </>
                    ) : (
                      <div className="slot-placeholder">Trống</div>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        ))}
      </div>

      {/* Selected Slot Details Modal/Panel */}
      {selectedSlot && (
        <div className="slot-details-box">
          <h4>📌 Chi tiết Ô kho: {selectedSlot.slot_name || `Slot #${selectedSlot.id}`}</h4>
          <div className="slot-info-list">
            <div>
              <strong>Trạng thái:</strong> {selectedSlot.status || (isSlotOccupied(selectedSlot) ? "OCCUPIED" : "EMPTY")}
            </div>
            <div>
              <strong>Mã Sản phẩm (Product ID):</strong> {selectedSlot.product_id || "N/A"}
            </div>
            <div>
              <strong>Mã QR Scanned:</strong> {selectedSlot.qr_code || "N/A"}
            </div>
            {selectedSlot.sender_name && (
              <div>
                <strong>Người gửi:</strong> {selectedSlot.sender_name}
              </div>
            )}
            {selectedSlot.updated_time && (
              <div>
                <strong>Cập nhật cuối:</strong>{" "}
                {new Date(selectedSlot.updated_time).toLocaleString()}
              </div>
            )}
          </div>

          <div className="slot-actions" style={{ display: "flex", gap: "8px", marginTop: "12px" }}>
            <button
              type="button"
              className="btn btn-danger btn-sm"
              style={{ background: "#ef4444", color: "#fff", fontWeight: "bold" }}
              onClick={() => handleClear(selectedSlot.slot_name || selectedSlot.id)}
              disabled={loading}
            >
              🗑️ Xóa Hàng Trong Ô (Clear Slot)
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setSelectedSlot(null)}
            >
              Đóng
            </button>
          </div>
        </div>
      )}

      <div className="qr-simulator">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
          <label htmlFor="qrInput" className="font-bold">📷 Quét mã QR Sản phẩm Kho:</label>
        </div>

        <div className="input-group">
          <input
            id="qrInput"
            type="text"
            className="input"
            placeholder="Nhập mã QR thủ công (VD: PROD-8899)"
            value={qrInput}
            onChange={(e) => setQrInput(e.target.value)}
          />
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSimulateQR}
            disabled={loading || !qrInput.trim()}
          >
            Quét & Lấy ô kho
          </button>
        </div>
      </div>

      {msg && <div className="action-msg text-sm mt-2">{msg}</div>}
    </div>
  );
});

import { useState, useEffect } from "react";
import type { StorageSlot } from "../types/drone";
import { API_BASE, clearStorageSlot, scanQR, startBackendCamera, stopBackendCamera } from "../services/api";

interface Props {
  slots: StorageSlot[];
  externalCameraActive?: boolean;
}

export function StorageSlotsGrid({ slots, externalCameraActive }: Props) {
  const [selectedSlot, setSelectedSlot] = useState<StorageSlot | null>(null);
  const [qrInput, setQrInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    if (externalCameraActive !== undefined) {
      setCameraActive(externalCameraActive);
    }
  }, [externalCameraActive]);

  const handleToggleBackendCamera = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const res = cameraActive ? await stopBackendCamera() : await startBackendCamera();
      if (!res.ok) {
        const errText = await res.text();
        setMsg(`Lỗi ${res.status}: ${errText}`);
        return;
      }
      const data = await res.json();
      setCameraActive(!cameraActive);
      setMsg(data.message || `Đã ${!cameraActive ? "BẬT" : "TẮT"} Backend Camera QR Scanner thành công!`);
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  // Default 9 grid matrix A1..C3
  const gridNames = [
    ["A1", "A2", "A3"],
    ["B1", "B2", "B3"],
    ["C1", "C2", "C3"],
  ];

  const getSlotData = (name: string): StorageSlot | undefined => {
    return slots.find((s) => s.slot_name === name || `Slot-${s.id}` === name);
  };

  const handleClear = async (slotId: number) => {
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
      setMsg(data.message || `Đã dọn dẹp ô kho #${slotId}`);
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

          <div className="slot-actions">
            <button
              type="button"
              className="btn btn-danger btn-sm"
              onClick={() => handleClear(selectedSlot.id)}
              disabled={loading}
            >
              🗑️ Giải phóng Ô kho
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

      {/* Backend USB Camera QR Scanner Test Controls */}
      <div className="qr-simulator">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
          <label htmlFor="qrInput" className="font-bold">📷 Quét mã QR Sản phẩm Kho:</label>
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              type="button"
              className={`btn btn-sm ${cameraActive ? "btn-danger" : "btn-secondary"}`}
              onClick={handleToggleBackendCamera}
              disabled={loading}
              title="Bật/Tắt luồng quét USB Camera trực tiếp từ Backend"
            >
              {cameraActive ? "⏹ Tắt USB Camera" : "📷 Test USB Camera"}
            </button>
          </div>
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

        {/* Live USB Camera Stream Preview */}
        {cameraActive && (
          <div style={{ marginTop: "10px", textAlign: "center", background: "#0f172a", padding: "10px", borderRadius: "8px", border: "1px solid #334155" }}>
            <div style={{ color: "#38bdf8", fontSize: "0.85rem", marginBottom: "8px", fontWeight: "600", display: "flex", alignItems: "center", justifyContent: "center", gap: "6px" }}>
              <span className="animate-pulse" style={{ color: "#ef4444" }}>🔴</span> LIVE Video Stream từ USB Camera (OpenCV Vision):
            </div>
            <img
              src={`${API_BASE}/api/inventory/camera-scan/video-feed`}
              alt="USB Camera Live Stream"
              style={{ maxWidth: "100%", maxHeight: "320px", borderRadius: "6px", border: "1px solid #475569", background: "#000" }}
              onError={(e) => {
                // If stream is loading or not available yet
                (e.target as HTMLElement).style.display = "none";
              }}
            />
          </div>
        )}
      </div>

      {msg && <div className="action-msg text-sm mt-2">{msg}</div>}
    </div>
  );
}

import React, { useState } from "react";
import {
  startCameraDevice,
  stopCameraDevice,
  triggerCameraQrScan,
  captureAndScanRealCamera,
  API_BASE,
} from "../../services/api";

interface Props {
  productId?: string;
  timestamp?: string;
  status?: "DETECTED" | "SCANNING" | "NOT_FOUND" | "OFFLINE";
  cameraActive?: boolean;
  systemMode?: "AUTO" | "MANUAL";
  liveMessage?: string;
}

export const CameraVision = React.memo(function CameraVision({
  productId = "Chờ quét...",
  timestamp = "--:--:--",
  status = "DETECTED",
  cameraActive = true,
  systemMode = "AUTO",
  liveMessage,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [customQr, setCustomQr] = useState("SP001");
  const [feedback, setFeedback] = useState<string | null>(null);

  const handleToggleCamera = async () => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = cameraActive ? await stopCameraDevice() : await startCameraDevice();
      if (res.ok) {
        setFeedback(cameraActive ? "⏹ Camera stream đã dừng" : "📷 Camera stream đã khởi động");
      }
    } catch {
      setFeedback("❌ Lỗi điều khiển camera");
    } finally {
      setLoading(false);
    }
  };

  // 1. Chụp ảnh thực tế từ Camera USB CAM01 và quét mã QR bằng OpenCV
  const handleCaptureRealCamera = async () => {
    setLoading(true);
    setFeedback("📸 Đang chụp khung hình từ Camera và giải mã OpenCV...");
    try {
      const res = await captureAndScanRealCamera();
      const data = await res.json();
      if (res.ok && data.status === "success") {
        setFeedback(`✅ Quét thành công từ Camera thật: ${data.product_id}`);
      } else if (data.status === "not_found") {
        setFeedback(`⚠️ ${data.message || "Camera chưa nhìn thấy mã QR! Vui lòng đưa tem vào giữa ống kính."}`);
      } else {
        setFeedback(`❌ ${data.message || "Lỗi khi quét từ camera"}`);
      }
    } catch {
      setFeedback("❌ Lỗi kết nối đến Camera API");
    } finally {
      setLoading(false);
    }
  };

  // 2. Giả lập nhập mã thủ công bằng text (Dành cho kiểm thử)
  const handleManualScan = async () => {
    if (!customQr.trim()) return;
    setLoading(true);
    setFeedback(null);
    try {
      const res = await triggerCameraQrScan(customQr);
      if (res.ok) {
        const data = await res.json();
        setFeedback(`🧪 [Giả lập] Nhập mã thành công: ${data.data?.product_id || customQr}`);
      } else {
        setFeedback("❌ Lỗi quét mã QR giả lập");
      }
    } catch {
      setFeedback("❌ Lỗi kết nối Camera API");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="hmi-card camera-vision-card">
      <div className="card-header flex-between">
        <div className="card-title-group">
          <h3>📷 CAMERA QR (CAM01)</h3>
          <span className="card-subtitle">AUTO VISION SCANNER & SLOT MAPPER</span>
        </div>
        <span className={`live-badge ${cameraActive ? "live-on" : "live-off"}`}>
          {cameraActive ? "● LIVE STREAM" : "○ STREAM OFF"}
        </span>
      </div>

      <div className="card-body camera-layout">
        <div className="camera-viewport" style={{ position: "relative", overflow: "hidden", minHeight: "220px", background: "#0b132b", borderRadius: "8px" }}>
          {cameraActive ? (
            <div style={{ position: "relative", width: "100%", height: "100%", display: "flex", justifyContent: "center", alignItems: "center" }}>
              <img
                src={`${API_BASE}/api/inventory/camera-scan/video-feed`}
                alt="USB Camera Live Stream"
                style={{ width: "100%", height: "100%", maxHeight: "240px", objectFit: "cover", borderRadius: "6px", display: "block" }}
                onError={(e) => {
                  // If mjpeg stream drops, show placeholder
                  (e.currentTarget as HTMLElement).style.display = "none";
                }}
              />
              {/* Overlay Crosshairs */}
              <div className="camera-crosshairs">
                <div className="ch-line-h"></div>
                <div className="ch-line-v"></div>
              </div>
              <div className="cam-meta-overlay top-left" style={{ position: "absolute", top: "8px", left: "8px", background: "rgba(0,0,0,0.6)", padding: "2px 6px", borderRadius: "4px", fontSize: "0.75rem" }}>
                USB CAM01 (DIRECTSHOW)
              </div>
              <div className="cam-meta-overlay top-right" style={{ position: "absolute", top: "8px", right: "8px", background: "rgba(0,0,0,0.6)", padding: "2px 6px", borderRadius: "4px", fontSize: "0.75rem", color: "#00ffcc" }}>
                {systemMode === "AUTO" ? "⚡ AUTO SCANNING" : "🎮 MANUAL READY"}
              </div>
            </div>
          ) : (
            <div className="video-stream-placeholder">
              <div className="camera-crosshairs">
                <div className="ch-line-h"></div>
                <div className="ch-line-v"></div>
              </div>

              <div className="qr-bounding-box">
                <div className="corner top-left"></div>
                <div className="corner top-right"></div>
                <div className="corner bottom-left"></div>
                <div className="corner bottom-right"></div>
                <div className="scan-line"></div>
                
                {/* Detailed Simulated QR Pattern Graphic */}
                <div className="qr-code-graphic">
                  <div className="qr-finder top-l"></div>
                  <div className="qr-finder top-r"></div>
                  <div className="qr-finder bot-l"></div>
                  <div className="qr-bits-grid"></div>
                </div>
              </div>

              <div className="cam-meta-overlay top-left">USB CAM01 / DEV_0</div>
              <div className="cam-meta-overlay top-right">FPS: STANDBY | RES: 1080p</div>
            </div>
          )}
        </div>


        {/* Live Notification Banner during Auto or Manual Scan */}
        {(liveMessage || feedback) && (
          <div
            className="manual-feedback-pill font-mono"
            style={{
              margin: "10px 0 4px 0",
              padding: "7px 12px",
              borderRadius: "6px",
              fontSize: "0.85rem",
              background:
                status === "DETECTED"
                  ? "rgba(16, 185, 129, 0.15)"
                  : status === "NOT_FOUND"
                  ? "rgba(239, 68, 68, 0.15)"
                  : "rgba(14, 165, 233, 0.15)",
              border: `1px solid ${
                status === "DETECTED" ? "#10b981" : status === "NOT_FOUND" ? "#ef4444" : "#0ea5e9"
              }`,
              color: status === "DETECTED" ? "#34d399" : status === "NOT_FOUND" ? "#f87171" : "#38bdf8",
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            {feedback || liveMessage}
          </div>
        )}

        <div className="camera-info-footer flex-between">
          <div className="info-group">
            <span className="label">Product ID</span>
            <strong className="value text-cyan font-mono" style={{ fontSize: "1rem" }}>
              {productId}
            </strong>
          </div>

          <div className="info-group">
            <span className="label">Scan Time</span>
            <span className="value font-mono">{timestamp}</span>
          </div>

          <div className="info-group">
            <span className="label">Vision Status</span>
            <strong
              className={`value ${
                status === "DETECTED"
                  ? "text-green"
                  : status === "SCANNING"
                  ? "text-yellow"
                  : status === "NOT_FOUND"
                  ? "text-red"
                  : "text-gray"
              }`}
            >
              {status}
            </strong>
          </div>
        </div>

        {/* Camera Manual Control Toolbar - VISIBLE IN MANUAL MODE */}
        {systemMode === "MANUAL" && (
          <div className="camera-manual-controls-section" style={{ marginTop: "12px", borderTop: "1px solid rgba(255,255,255,0.08)", paddingTop: "10px" }}>
            <div className="manual-section-title flex-between" style={{ marginBottom: "8px" }}>
              <span className="font-mono text-cyan" style={{ fontSize: "0.85rem" }}>
                🎮 ĐIỀU KHIỂN THỦ CÔNG CAMERA:
              </span>
              <span className="mode-indicator-tag active-manual">MANUAL SẴN SÀNG</span>
            </div>

            {/* Main Action Buttons Row */}
            <div className="camera-manual-actions-row flex-between" style={{ gap: "8px", flexWrap: "wrap" }}>
              <button
                type="button"
                className={`btn-manual-cam ${cameraActive ? "btn-cam-stop" : "btn-cam-start"}`}
                onClick={handleToggleCamera}
                disabled={loading}
                style={{ padding: "8px 12px", borderRadius: "6px" }}
              >
                {cameraActive ? "⏹ Tắt Stream" : "📷 Bật Stream"}
              </button>

              {/* Nút chụp từ Camera thật theo yêu cầu của bạn */}
              <button
                type="button"
                className="btn-cyan btn-capture-real"
                onClick={handleCaptureRealCamera}
                disabled={loading || !cameraActive}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "8px 14px",
                  background: "linear-gradient(135deg, #00b4d8, #0077b6)",
                  color: "#fff",
                  border: "none",
                  borderRadius: "6px",
                  cursor: "pointer",
                  fontWeight: "bold",
                  fontSize: "0.85rem",
                  boxShadow: "0 0 8px rgba(0, 180, 216, 0.35)",
                }}
                title="Chụp 1 khung hình từ Camera thật ngay lúc này và quét mã QR"
              >
                📸 Chụp ảnh từ Camera thật để quét
              </button>
            </div>

            {/* Sub Row: Giả lập nhập text dành riêng cho test */}
            <div
              style={{
                marginTop: "10px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
                fontSize: "0.75rem",
                color: "#94a3b8",
              }}
            >
              <span>🧪 Giả lập:</span>
              <input
                type="text"
                className="input-qr-test"
                value={customQr}
                onChange={(e) => setCustomQr(e.target.value)}
                placeholder="Mã QR test..."
                style={{
                  flex: 1,
                  maxWidth: "140px",
                  padding: "4px 8px",
                  fontSize: "0.75rem",
                  background: "rgba(15, 23, 42, 0.6)",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: "4px",
                  color: "#e2e8f0",
                }}
              />
              <button
                type="button"
                className="btn-manual-scan"
                onClick={handleManualScan}
                disabled={loading}
                style={{
                  padding: "4px 8px",
                  fontSize: "0.75rem",
                  background: "rgba(51, 65, 85, 0.8)",
                  border: "none",
                  borderRadius: "4px",
                  color: "#cbd5e1",
                  cursor: "pointer",
                }}
                title="Kiểm thử nhập mã giả lập bằng tay vào kho"
              >
                Gửi mã test
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
});

import { useState } from "react";
import { startCameraDevice, stopCameraDevice, triggerCameraQrScan } from "../../services/api";

interface Props {
  productId?: string;
  timestamp?: string;
  status?: "DETECTED" | "SCANNING" | "OFFLINE";
  cameraActive?: boolean;
  systemMode?: "AUTO" | "MANUAL";
}

export function CameraVision({
  productId = "PRD-TEST-1001",
  timestamp = "21:17:43",
  status = "DETECTED",
  cameraActive = true,
  systemMode = "AUTO",
}: Props) {
  const [loading, setLoading] = useState(false);
  const [customQr, setCustomQr] = useState("PRD-MANUAL-888");
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

  const handleManualScan = async () => {
    if (!customQr.trim()) return;
    setLoading(true);
    setFeedback(null);
    try {
      const res = await triggerCameraQrScan(customQr);
      if (res.ok) {
        const data = await res.json();
        setFeedback(`✅ Quét thành công QR: ${data.data?.product_id || customQr}`);
      } else {
        setFeedback("❌ Lỗi quét mã QR");
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
        <div className="camera-viewport">
          {/* Cyber Industrial Camera Viewport Overlay */}
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

            <div className="cam-meta-overlay top-left">RTSP://192.168.1.50/live</div>
            <div className="cam-meta-overlay top-right">FPS: 30.0 | RES: 1080p</div>
          </div>
        </div>

        <div className="camera-info-footer flex-between">
          <div className="info-group">
            <span className="label">Product ID</span>
            <strong className="value text-cyan font-mono">{productId}</strong>
          </div>

          <div className="info-group">
            <span className="label">Scan Time</span>
            <span className="value font-mono">{timestamp}</span>
          </div>

          <div className="info-group">
            <span className="label">Vision Status</span>
            <strong
              className={`value ${
                status === "DETECTED" ? "text-green" : "text-yellow"
              }`}
            >
              {status}
            </strong>
          </div>
        </div>

        {/* Camera Manual Control Toolbar - ONLY VISIBLE IN MANUAL MODE */}
        {systemMode === "MANUAL" && (
          <div className="camera-manual-controls-section">
            <div className="manual-section-title flex-between">
              <span className="font-mono text-cyan">🎮 ĐIỀU KHIỂN THỦ CÔNG CAMERA:</span>
              <span className="mode-indicator-tag active-manual">MANUAL SẴN SÀNG</span>
            </div>

            {feedback && <div className="manual-feedback-pill font-mono">{feedback}</div>}

            <div className="camera-manual-actions-row flex-between">
              <button
                type="button"
                className={`btn-manual-cam ${cameraActive ? "btn-cam-stop" : "btn-cam-start"}`}
                onClick={handleToggleCamera}
                disabled={loading}
              >
                {cameraActive ? "⏹ Tắt Stream" : "📷 Bật Stream"}
              </button>

              <div className="qr-test-input-group flex-between">
                <input
                  type="text"
                  className="input-qr-test"
                  value={customQr}
                  onChange={(e) => setCustomQr(e.target.value)}
                  placeholder="Mã QR test..."
                />
                <button
                  type="button"
                  className="btn-manual-scan"
                  onClick={handleManualScan}
                  disabled={loading}
                  title="Bắn tín hiệu quét mã QR này"
                >
                  🔍 Quét QR
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

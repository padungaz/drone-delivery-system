interface Props {
  productId?: string;
  timestamp?: string;
  status?: "DETECTED" | "SCANNING" | "OFFLINE";
  cameraActive?: boolean;
}

export function CameraVision({
  productId = "PRD-TEST-1001",
  timestamp = "21:17:43",
  status = "DETECTED",
}: Props) {
  return (
    <div className="hmi-card camera-vision-card">
      <div className="card-header flex-between">
        <div className="card-title-group">
          <h3>📷 CAMERA QR (CAM01)</h3>
          <span className="card-subtitle">AUTO VISION SCANNER & SLOT MAPPER</span>
        </div>
        <span className="live-badge">● LIVE STREAM</span>
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

            <div className="cam-meta-overlay top-left">RTSP://192.168.58.50/live</div>
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
      </div>
    </div>
  );
}

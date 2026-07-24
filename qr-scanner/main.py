"""
QR Scanner Station — Entry Point.

Chạy trên máy tính đặt trong kho hàng.
Luồng chính: Camera loop → detect QR → gửi HTTP POST tới Backend.
Luồng phụ: WebSocket listener → nhận & hiển thị storage updates.

Usage:
    python main.py
"""

import asyncio
import logging
import signal
import sys
import threading

import config
from api_client import get_storage_state, print_storage_state, send_qr_to_server
from scanner import QRCodeScanner
from ws_client import StorageWSClient

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("qr-scanner")


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


def on_qr_detected(qr_data: dict) -> None:
    """Callback khi camera phát hiện QR code mới (đã debounce).

    Gửi dữ liệu tới Backend qua HTTP POST /storage/scan.
    """
    logger.info(
        "━━━ QR DETECTED ━━━ Sender: %s | Address: %s",
        qr_data.get("senderName", "?"),
        qr_data.get("address", "?"),
    )

    result = send_qr_to_server(qr_data)

    if result.get("status") == "success":
        logger.info("✅ %s", result.get("message", "Saved"))
    else:
        logger.error("❌ %s", result.get("detail", "Failed"))


def on_storage_update(payload: dict) -> None:
    """Callback khi nhận storage_update từ WebSocket."""
    print_storage_state(payload)


# ---------------------------------------------------------------------------
# WebSocket background thread
# ---------------------------------------------------------------------------


def run_ws_client(ws_client: StorageWSClient) -> None:
    """Chạy WebSocket client trong một asyncio event loop riêng."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(ws_client.connect())
    except Exception as exc:
        logger.error("WebSocket thread error: %s", exc)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point chính."""
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║       📷  QR SCANNER STATION — WAREHOUSE        ║")
    print("╠══════════════════════════════════════════════════╣")
    server_str = f"{config.SERVER_IP}:{config.SERVER_PORT}"
    cam_str = f"index {config.CAMERA_INDEX}"
    prev_str = "ON" if config.SHOW_PREVIEW else "OFF"
    print(f"║  Server:  {server_str:<37}║")
    print(f"║  Camera:  {cam_str:<37}║")
    print(f"║  Preview: {prev_str:<37}║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    # 1. Hiển thị trạng thái kho hiện tại
    logger.info("Fetching current storage state...")
    state = get_storage_state()
    if state:
        print_storage_state(state)
    else:
        logger.warning("Could not fetch storage state (server offline?)")

    # 2. Khởi động WebSocket client (background thread)
    ws_client = StorageWSClient(on_storage_update=on_storage_update)
    ws_thread = threading.Thread(target=run_ws_client, args=(ws_client,), daemon=True)
    ws_thread.start()
    logger.info("WebSocket client started (background thread)")

    # 3. Khởi động Camera Scanner (main thread, blocking)
    scanner = QRCodeScanner(on_qr_detected=on_qr_detected)

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        logger.info("Shutting down...")
        scanner.stop()
        ws_client.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    logger.info("Starting camera scanner...")
    scanner.run()

    # Cleanup
    ws_client.stop()
    logger.info("QR Scanner Station stopped.")


if __name__ == "__main__":
    main()

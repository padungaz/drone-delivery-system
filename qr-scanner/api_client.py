"""
HTTP API Client — Gửi dữ liệu QR tới Backend server.

Giao tiếp qua HTTP POST /storage/scan.
"""

import logging

import httpx

import config

logger = logging.getLogger(__name__)

# Persistent HTTP client (connection pooling)
_client = httpx.Client(timeout=10.0)


def send_qr_to_server(qr_data: dict) -> dict:
    """Gửi dữ liệu QR tới Backend POST /storage/scan.

    Args:
        qr_data: Dict chứa ít nhất {"senderName": "...", "address": "..."}.

    Returns:
        Response body dict từ server.

    Raises:
        Exception nếu request fail hoặc server trả lỗi.
    """
    url = config.SCAN_API_URL
    logger.info("Sending QR data to %s", url)

    try:
        response = _client.post(url, json=qr_data)

        if response.status_code == 200:
            result = response.json()
            logger.info(
                "Server response: %s (slot #%s)",
                result.get("message", "OK"),
                result.get("slot_id", "?"),
            )
            return result

        # Handle error responses
        error_detail = "Unknown error"
        try:
            error_body = response.json()
            error_detail = error_body.get("detail", str(error_body))
        except Exception:
            error_detail = response.text

        logger.error(
            "Server returned %d: %s", response.status_code, error_detail
        )
        return {"status": "error", "detail": error_detail}

    except httpx.ConnectError:
        logger.error("Cannot connect to server at %s", url)
        return {"status": "error", "detail": "Cannot connect to server"}
    except httpx.TimeoutException:
        logger.error("Request timeout to %s", url)
        return {"status": "error", "detail": "Request timeout"}
    except Exception as exc:
        logger.error("Unexpected error sending QR: %s", exc)
        return {"status": "error", "detail": str(exc)}


def get_storage_state() -> dict:
    """Lấy trạng thái kho hiện tại từ Backend GET /storage.

    Returns:
        Storage state dict hoặc empty dict nếu lỗi.
    """
    url = config.STORAGE_API_URL
    try:
        response = _client.get(url)
        if response.status_code == 200:
            return response.json()
        logger.error("GET /storage returned %d", response.status_code)
        return {}
    except Exception as exc:
        logger.error("Failed to get storage state: %s", exc)
        return {}


def print_storage_state(state: dict) -> None:
    """In trạng thái kho ra console với màu sắc."""
    slots = state.get("slots", [])
    if not slots:
        print("  [Không có dữ liệu kho]")
        return

    print("\n" + "=" * 50)
    print("  TRẠNG THÁI KHO HÀNG")
    print("=" * 50)

    for slot in slots:
        slot_id = slot.get("id", "?")
        is_empty = slot.get("isEmpty", True)
        item = slot.get("item")

        if is_empty:
            # Green for empty
            print(f"  [{slot_id}] 🟢 Trống")
        else:
            # Red for occupied
            sender = item.get("senderName", "?") if item else "?"
            address = item.get("senderAddress", "?") if item else "?"
            print(f"  [{slot_id}] 🔴 {sender} — {address}")

    occupied = sum(1 for s in slots if not s.get("isEmpty", True))
    print(f"\n  Đã sử dụng: {occupied}/9")
    print("=" * 50 + "\n")

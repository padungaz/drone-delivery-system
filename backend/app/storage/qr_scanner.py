import json
import logging
from typing import Optional

from app.storage.schemas import QRScanPayload

logger = logging.getLogger(__name__)


def parse_qr_data(raw: str | dict) -> Optional[QRScanPayload]:
    """Parse and validate QR code data from the warehouse camera scanner.

    Accepts either:
    - A dict (already parsed JSON from the camera client)
    - A raw JSON string scanned from the QR code

    Returns a validated QRScanPayload or None if parsing fails.
    """
    try:
        if isinstance(raw, str):
            data = json.loads(raw)
        else:
            data = raw

        payload = QRScanPayload(**data)
        logger.info("QR data parsed: sender=%s, address=%s", payload.sender_name, payload.address)
        return payload
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning("Failed to parse QR data: %s", exc)
        return None

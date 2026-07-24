import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import StorageSlotRecord
from app.storage.schemas import QRScanPayload, StorageItem, StorageSlotResponse, StorageStateResponse

logger = logging.getLogger(__name__)

TOTAL_SLOTS = 9


class StorageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Initialization ───────────────────────────────────────────────────────

    async def init_storage_slots(self) -> None:
        """Seed the 9 fixed storage slots if they don't already exist."""
        result = await self.session.execute(
            select(StorageSlotRecord).order_by(StorageSlotRecord.id)
        )
        existing_ids = {row.id for row in result.scalars().all()}

        for slot_id in range(1, TOTAL_SLOTS + 1):
            if slot_id not in existing_ids:
                self.session.add(StorageSlotRecord(id=slot_id, is_empty=True))
                logger.info("Created storage slot #%d", slot_id)

        await self.session.commit()

    # ── Read ─────────────────────────────────────────────────────────────────

    async def get_all_slots(self) -> list[StorageSlotRecord]:
        """Return all 9 slots ordered by id."""
        result = await self.session.execute(
            select(StorageSlotRecord).order_by(StorageSlotRecord.id)
        )
        return list(result.scalars().all())

    async def get_slot(self, slot_id: int) -> Optional[StorageSlotRecord]:
        """Return a single slot by id."""
        result = await self.session.execute(
            select(StorageSlotRecord).where(StorageSlotRecord.id == slot_id)
        )
        return result.scalar_one_or_none()

    async def find_first_empty_slot(self) -> Optional[StorageSlotRecord]:
        """Find the first empty slot (lowest id with is_empty=True)."""
        result = await self.session.execute(
            select(StorageSlotRecord)
            .where(StorageSlotRecord.is_empty.is_(True))
            .order_by(StorageSlotRecord.id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    # ── Write ────────────────────────────────────────────────────────────────

    async def assign_item_to_slot(
        self, slot: StorageSlotRecord, payload: QRScanPayload
    ) -> StorageSlotRecord:
        """Assign a scanned item to the given slot."""
        slot.is_empty = False
        slot.qr_code = payload.qr_code
        slot.sender_name = payload.sender_name
        slot.sender_address = payload.address
        slot.item_created_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(slot)
        logger.info(
            "Item assigned to slot #%d: sender=%s", slot.id, payload.sender_name
        )
        return slot

    async def clear_slot(self, slot_id: int) -> Optional[StorageSlotRecord]:
        """Remove item from a slot, resetting it to empty."""
        slot = await self.get_slot(slot_id)
        if slot is None:
            return None

        slot.is_empty = True
        slot.qr_code = None
        slot.sender_name = None
        slot.sender_address = None
        slot.item_created_at = None
        await self.session.commit()
        await self.session.refresh(slot)
        logger.info("Slot #%d cleared", slot_id)
        return slot

    # ── Helpers ──────────────────────────────────────────────────────────────

    def build_storage_state(self, slots: list[StorageSlotRecord]) -> StorageStateResponse:
        """Convert DB records to the API response format."""
        slot_responses = []
        for s in slots:
            item = None
            if not s.is_empty:
                item = StorageItem(
                    qr_code=s.qr_code,
                    sender_name=s.sender_name,
                    sender_address=s.sender_address,
                    created_at=s.item_created_at,
                )
            slot_responses.append(
                StorageSlotResponse(id=s.id, is_empty=s.is_empty, item=item)
            )
        return StorageStateResponse(total_slots=TOTAL_SLOTS, slots=slot_responses)

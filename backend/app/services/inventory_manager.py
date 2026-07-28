import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import ProductRecord, SystemLogRecord
from app.models.schemas import StorageSlotStatus, QRScanPayload
from app.storage.models import StorageSlotRecord

logger = logging.getLogger(__name__)

# Standard 9 slots for smart warehouse grid
SLOT_NAMES = ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3"]


class InventoryManager:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def init_default_slots(self) -> None:
        """Seed 9 storage slots (A1..C3) if table is empty."""
        stmt = select(StorageSlotRecord)
        res = await self.session.execute(stmt)
        existing = res.scalars().all()

        if not existing:
            now = datetime.utcnow()
            for name in SLOT_NAMES:
                slot = StorageSlotRecord(
                    slot_name=name,
                    status=StorageSlotStatus.EMPTY.value,
                    product_id=None,
                    qr_code=None,
                    updated_time=now,
                )
                self.session.add(slot)
            await self.session.commit()
            logger.info("Initialized 9 default storage slots (A1..C3)")

    async def get_all_slots(self) -> List[StorageSlotRecord]:
        """Fetch all 9 storage slots."""
        stmt = select(StorageSlotRecord).order_by(StorageSlotRecord.slot_name)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def find_available_slot(self) -> Optional[StorageSlotRecord]:
        """Find first EMPTY storage slot."""
        stmt = select(StorageSlotRecord).where(
            StorageSlotRecord.status == StorageSlotStatus.EMPTY.value
        ).order_by(StorageSlotRecord.slot_name)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def find_slot_by_product_id(self, product_id: str) -> Optional[StorageSlotRecord]:
        """Find slot containing a specific product ID."""
        stmt = select(StorageSlotRecord).where(
            StorageSlotRecord.product_id == product_id
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def update_slot(
        self,
        slot_name: str,
        status: StorageSlotStatus,
        product_id: Optional[str] = None,
        qr_code: Optional[str] = None,
    ) -> Optional[StorageSlotRecord]:
        """Update status and product of a specific storage slot."""
        stmt = select(StorageSlotRecord).where(StorageSlotRecord.slot_name == slot_name)
        res = await self.session.execute(stmt)
        slot = res.scalar_one_or_none()

        if not slot:
            return None

        slot.status = status.value
        if product_id is not None:
            slot.product_id = product_id
        if qr_code is not None:
            slot.qr_code = qr_code
        slot.updated_time = datetime.utcnow()

        logger.info("Updated slot %s -> status=%s, product=%s", slot_name, status.value, product_id)
        await self.session.commit()
        await self.session.refresh(slot)
        return slot

    async def clear_slot_by_id(self, slot_id: int) -> Optional[StorageSlotRecord]:
        """Clear/reset a storage slot by its ID."""
        stmt = select(StorageSlotRecord).where(StorageSlotRecord.id == slot_id)
        res = await self.session.execute(stmt)
        slot = res.scalar_one_or_none()
        if not slot:
            return None

        slot.status = StorageSlotStatus.EMPTY.value
        slot.product_id = None
        slot.qr_code = None
        slot.updated_time = datetime.utcnow()

        logger.info("Cleared slot ID %d (%s)", slot_id, slot.slot_name)
        await self.session.commit()
        await self.session.refresh(slot)
        return slot

    async def process_qr_scan(self, payload: QRScanPayload) -> Optional[StorageSlotRecord]:
        """Process QR code scan from Camera QR system.
        Finds an available slot, registers product in DB, and assigns product to free slot.
        """
        qr_code = payload.qr
        product_id = qr_code.strip()

        # Find or create product record
        stmt_p = select(ProductRecord).where(ProductRecord.qr_code == qr_code)
        res_p = await self.session.execute(stmt_p)
        product = res_p.scalar_one_or_none()

        if not product:
            product = ProductRecord(
                product_id=product_id,
                product_name=f"Sản phẩm {product_id}",
                qr_code=qr_code,
                status="IN_STOCK",
                created_at=datetime.utcnow(),
            )
            self.session.add(product)

        # Check if product is already in a slot
        existing_slot = await self.find_slot_by_product_id(product_id)
        if existing_slot:
            logger.info("Product %s already assigned to slot %s", product_id, existing_slot.slot_name)
            return existing_slot

        # Assign to first free slot
        free_slot = await self.find_available_slot()
        if not free_slot:
            logger.error("No free slot available for scanned product %s!", product_id)
            self.session.add(
                SystemLogRecord(
                    log_type="ERROR_LOG",
                    source="CAMERA",
                    message=f"No free slot for scanned product {product_id}",
                    created_at=datetime.utcnow(),
                )
            )
            await self.session.commit()
            return None

        free_slot.status = StorageSlotStatus.OCCUPIED.value
        free_slot.product_id = product_id
        free_slot.qr_code = qr_code
        free_slot.updated_time = datetime.utcnow()

        product.current_slot = free_slot.slot_name

        self.session.add(
            SystemLogRecord(
                log_type="SYSTEM_LOG",
                source="CAMERA",
                message=f"QR scanned product {product_id} assigned to slot {free_slot.slot_name}",
                created_at=datetime.utcnow(),
            )
        )
        await self.session.commit()
        await self.session.refresh(free_slot)
        return free_slot

import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import ProductRecord, SystemLogRecord, StorageSlotRecord
from app.models.schemas import StorageSlotStatus, QRScanPayload, StorageSlotResponse

logger = logging.getLogger(__name__)

# Smart warehouse grid slots: 6 active operational slots (A1..B3) + 3 symbolic reserved slots (C1..C3)
ACTIVE_SLOT_NAMES = ["A1", "A2", "A3", "B1", "B2", "B3"]
SYMBOLIC_SLOT_NAMES = ["C1", "C2", "C3"]
SLOT_NAMES = ACTIVE_SLOT_NAMES + SYMBOLIC_SLOT_NAMES


class InventoryManager:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def init_default_slots(self) -> None:
        """Seed 9 storage slots (A1..C3) with C1..C3 marked as RESERVED (symbolic)."""
        stmt = select(StorageSlotRecord).order_by(StorageSlotRecord.id)
        res = await self.session.execute(stmt)
        existing = list(res.scalars().all())

        if not existing:
            now = datetime.utcnow()
            for idx, name in enumerate(SLOT_NAMES, start=1):
                initial_status = (
                    StorageSlotStatus.EMPTY.value
                    if name in ACTIVE_SLOT_NAMES
                    else StorageSlotStatus.RESERVED.value
                )
                slot = StorageSlotRecord(
                    id=idx,
                    slot_name=name,
                    status=initial_status,
                    product_id=None,
                    qr_code=None,
                    updated_time=now,
                )
                self.session.add(slot)
            await self.session.commit()
            logger.info("Initialized 9 default storage slots (A1..B3 Active, C1..C3 Reserved)")
        else:
            now = datetime.utcnow()
            for idx, slot in enumerate(existing):
                if not slot.slot_name and idx < len(SLOT_NAMES):
                    slot.slot_name = SLOT_NAMES[idx]
                # Keep symbolic C1..C3 slots always RESERVED
                if slot.slot_name in SYMBOLIC_SLOT_NAMES:
                    slot.status = StorageSlotStatus.RESERVED.value
                    slot.product_id = None
                    slot.qr_code = None
                elif not slot.status:
                    slot.status = StorageSlotStatus.EMPTY.value
                if slot.updated_time is None:
                    slot.updated_time = now
            await self.session.commit()

    async def get_all_slots(self) -> List[StorageSlotRecord]:
        """Fetch all 9 storage slots (including symbolic C1..C3 for 3x3 grid display)."""
        stmt = select(StorageSlotRecord).order_by(StorageSlotRecord.slot_name)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def broadcast_inventory(self) -> List[dict]:
        """Broadcast latest 9 storage slots to all WebSockets (/ws/system and /ws/client)."""
        all_slots = await self.get_all_slots()
        slots_data = [
            StorageSlotResponse.model_validate(s, from_attributes=True).model_dump(mode="json")
            for s in all_slots
        ]
        try:
            from app.websocket.manager import system_ws_manager
            await system_ws_manager.broadcast("INVENTORY_STATUS", slots_data)
        except Exception as err:
            logger.warning("Error broadcasting INVENTORY_STATUS: %s", err)

        try:
            from app.websocket.handler import manager as drone_ws_manager
            await drone_ws_manager.broadcast_to_clients({
                "type": "storage_update",
                "payload": slots_data,
            })
        except Exception as err:
            logger.warning("Error broadcasting storage_update: %s", err)

        return slots_data

    async def find_available_slot(self) -> Optional[StorageSlotRecord]:
        """Find first EMPTY storage slot among active slots (A1..B3)."""
        stmt = select(StorageSlotRecord).where(
            StorageSlotRecord.slot_name.in_(ACTIVE_SLOT_NAMES),
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

    async def find_occupied_slot(self) -> Optional[StorageSlotRecord]:
        """Find first OCCUPIED storage slot among active slots (A1..B3) (for delivery/export)."""
        stmt = select(StorageSlotRecord).where(
            StorageSlotRecord.slot_name.in_(ACTIVE_SLOT_NAMES),
            StorageSlotRecord.status == StorageSlotStatus.OCCUPIED.value
        ).order_by(StorageSlotRecord.slot_name)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_occupied_slots(self) -> List[StorageSlotRecord]:
        """Fetch all OCCUPIED storage slots among active slots (A1..B3)."""
        stmt = select(StorageSlotRecord).where(
            StorageSlotRecord.slot_name.in_(ACTIVE_SLOT_NAMES),
            StorageSlotRecord.status == StorageSlotStatus.OCCUPIED.value
        ).order_by(StorageSlotRecord.slot_name)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def update_slot(
        self,
        slot_name: str,
        status: StorageSlotStatus,
        product_id: Optional[str] = None,
        qr_code: Optional[str] = None,
        auto_broadcast: bool = False,
    ) -> Optional[StorageSlotRecord]:
        """Update status and product of a specific storage slot."""
        stmt = select(StorageSlotRecord).where(StorageSlotRecord.slot_name == slot_name)
        res = await self.session.execute(stmt)
        slot = res.scalar_one_or_none()

        if not slot:
            return None

        status_val = status.value if hasattr(status, "value") else str(status)
        slot.status = status_val
        if status_val == StorageSlotStatus.EMPTY.value or status_val == "EMPTY":
            slot.product_id = product_id
            slot.qr_code = qr_code
            slot.sender_name = None
        else:
            if product_id is not None:
                slot.product_id = product_id
            if qr_code is not None:
                slot.qr_code = qr_code
        slot.updated_time = datetime.utcnow()

        logger.info("Updated slot %s -> status=%s, product=%s", slot_name, status_val, slot.product_id)
        await self.session.commit()
        await self.session.refresh(slot)

        if auto_broadcast:
            await self.broadcast_inventory()

        return slot

    async def clear_slot_by_id(self, slot_id: int, auto_broadcast: bool = False) -> Optional[StorageSlotRecord]:
        """Clear/reset a storage slot by its ID."""
        return await self.clear_slot(slot_id, auto_broadcast=auto_broadcast)

    async def clear_slot(self, slot_identifier: str | int, auto_broadcast: bool = False) -> Optional[StorageSlotRecord]:
        """Clear/reset a storage slot by its ID or slot_name."""
        if isinstance(slot_identifier, int) or (isinstance(slot_identifier, str) and slot_identifier.isdigit()):
            stmt = select(StorageSlotRecord).where(StorageSlotRecord.id == int(slot_identifier))
        else:
            stmt = select(StorageSlotRecord).where(StorageSlotRecord.slot_name == str(slot_identifier).upper())
        res = await self.session.execute(stmt)
        slot = res.scalar_one_or_none()
        if not slot:
            return None

        slot.status = StorageSlotStatus.EMPTY.value
        slot.product_id = None
        slot.qr_code = None
        slot.sender_name = None
        slot.updated_time = datetime.utcnow()

        logger.info("Cleared slot %s (ID: %d)", slot.slot_name, slot.id)
        await self.session.commit()
        await self.session.refresh(slot)

        if auto_broadcast:
            await self.broadcast_inventory()

        return slot

    async def process_qr_scan(self, payload: QRScanPayload) -> Optional[StorageSlotRecord]:
        """Process QR code scan from Camera QR system.
        Finds an available slot, registers product in DB, and assigns product to free slot.
        """
        qr_code = payload.qr.strip()
        product_id = qr_code
        sender_name = payload.sender_name or "Khách hàng"
        address = payload.address or "Kho trung tâm"

        if payload.product_id:
            product_id = payload.product_id

        # If qr_code is JSON string, extract fields
        if qr_code.startswith("{") and qr_code.endswith("}"):
            try:
                import json
                data = json.loads(qr_code)
                if isinstance(data, dict):
                    product_id = str(data.get("productId") or data.get("product_id") or product_id)
                    sender_name = str(data.get("senderName") or data.get("sender_name") or sender_name)
                    address = str(data.get("address") or data.get("sender_address") or address)
            except Exception:
                pass

        now = datetime.utcnow()

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
                created_at=now,
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
                    created_at=now,
                )
            )
            await self.session.commit()
            return None

        # Smart Intralogistics fields
        free_slot.status = StorageSlotStatus.OCCUPIED.value
        free_slot.product_id = product_id
        free_slot.qr_code = qr_code
        free_slot.updated_time = now

        # Legacy fields for backward compatibility
        free_slot.is_empty = False
        free_slot.sender_name = sender_name
        free_slot.sender_address = address
        free_slot.item_created_at = now

        product.current_slot = free_slot.slot_name

        self.session.add(
            SystemLogRecord(
                log_type="SYSTEM_LOG",
                source="CAMERA",
                message=f"QR scanned product {product_id} assigned to slot {free_slot.slot_name}",
                created_at=now,
            )
        )
        await self.session.commit()
        await self.session.refresh(free_slot)
        return free_slot

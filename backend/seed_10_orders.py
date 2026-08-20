"""
Seed Script: Clear all order history and generate 10 new sample orders & missions.
"""
import sys
import asyncio
from datetime import datetime

# Configure UTF-8 for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import select, delete
from app.database.repository import async_session, init_db
from app.models.database import (
    CustomerRecord,
    DeliveryRequestRecord,
    IntralogisticsMissionRecord,
    MissionHistoryRecord,
    StorageSlotRecord,
    ProductRecord,
    WarehouseConfigRecord,
)
from app.models.schemas import StorageSlotStatus
from app.services.device_lock_manager import device_lock_manager

SAMPLE_CUSTOMERS = [
    {"name": "Nguyễn Văn An", "phone": "0905123456", "addr": "54 Nguyễn Lương Bằng, Hòa Khánh Bắc, Liên Chiểu", "lat": 16.0752, "lon": 108.1510},
    {"name": "Trần Thị Mai", "phone": "0905234567", "addr": "120 Tôn Đức Thắng, Hòa Minh, Liên Chiểu", "lat": 16.0680, "lon": 108.1620},
    {"name": "Lê Hoàng Nam", "phone": "0905345678", "addr": "45 Điện Biên Phủ, Thanh Khê", "lat": 16.0640, "lon": 108.1850},
    {"name": "Phạm Thu Trang", "phone": "0905456789", "addr": "88 Nguyễn Tri Phương, Hải Châu", "lat": 16.0590, "lon": 108.2050},
    {"name": "Đặng Minh Quân", "phone": "0905567890", "addr": "15 Lê Duẩn, Hải Châu", "lat": 16.0710, "lon": 108.2190},
    {"name": "Vũ Quốc Hưng", "phone": "0905678901", "addr": "22 Bạch Đằng, Hải Châu", "lat": 16.0740, "lon": 108.2250},
    {"name": "Hoàng Kim Oanh", "phone": "0905789012", "addr": "105 Võ Nguyên Giáp, Sơn Trà", "lat": 16.0650, "lon": 108.2450},
    {"name": "Bùi Thanh Tùng", "phone": "0905890123", "addr": "68 Ngô Quyền, Sơn Trà", "lat": 16.0780, "lon": 108.2320},
    {"name": "Đỗ Mai Anh", "phone": "0905901234", "addr": "12 Lê Văn Hiến, Ngũ Hành Sơn", "lat": 16.0350, "lon": 108.2480},
    {"name": "Ngô Đức Trọng", "phone": "0905012345", "addr": "250 Cách Mạng Tháng 8, Cẩm Lệ", "lat": 16.0280, "lon": 108.2010},
]

SLOT_NAMES = ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3"]

async def reset_and_seed_orders():
    await init_db()

    async with async_session() as session:
        print("[RESET] Đang xóa sạch toàn bộ lịch sử đơn hàng và nhiệm vụ cũ...")

        # 1. Clear tables
        await session.execute(delete(IntralogisticsMissionRecord))
        await session.execute(delete(DeliveryRequestRecord))
        await session.execute(delete(MissionHistoryRecord))
        await session.execute(delete(ProductRecord))

        # Unlock station
        device_lock_manager.unlock_station()

        # 2. Get or seed warehouse config
        res_wh = await session.execute(select(WarehouseConfigRecord))
        wh = res_wh.scalars().first()
        if not wh:
            wh = WarehouseConfigRecord(
                id=1,
                name="Smart Intralogistics Center A",
                latitude=16.0748,
                longitude=108.1498,
                address_text="Khu Công Nghệ Cao Đà Nẵng",
            )
            session.add(wh)
            await session.flush()

        wh_lat = wh.latitude
        wh_lon = wh.longitude
        wh_addr = wh.address_text or wh.name

        # 3. Reset 9 Storage Slots (A1..C3)
        # Slots A1..A3, B1: OCCUPIED with stock for export
        # Slots B2..B3, C1..C3: EMPTY for incoming pickup
        print("[STOCK] Khởi tạo lại trạng thái 9 ô kho (A1..C3)...")
        res_slots = await session.execute(select(StorageSlotRecord).order_by(StorageSlotRecord.id))
        slots_db = list(res_slots.scalars().all())

        initial_stock = {
            "A1": {"prod": "PRD-1001", "name": "Gói Hàng Vi Mạch FR3-01", "status": StorageSlotStatus.OCCUPIED.value},
            "A2": {"prod": "PRD-1002", "name": "Cảm Biến Công Nghiệp S7-02", "status": StorageSlotStatus.OCCUPIED.value},
            "A3": {"prod": "PRD-1003", "name": "Module Quang Điện Tử OPT-03", "status": StorageSlotStatus.OCCUPIED.value},
            "B1": {"prod": "PRD-1004", "name": "Bộ Điều Khiển MAVLink CTL-04", "status": StorageSlotStatus.OCCUPIED.value},
            "B2": {"prod": None, "name": None, "status": StorageSlotStatus.EMPTY.value},
            "B3": {"prod": None, "name": None, "status": StorageSlotStatus.EMPTY.value},
            "C1": {"prod": None, "name": None, "status": StorageSlotStatus.EMPTY.value},
            "C2": {"prod": None, "name": None, "status": StorageSlotStatus.EMPTY.value},
            "C3": {"prod": None, "name": None, "status": StorageSlotStatus.EMPTY.value},
        }

        now = datetime.utcnow()
        if not slots_db:
            for idx, s_name in enumerate(SLOT_NAMES, start=1):
                s_info = initial_stock.get(s_name, {"prod": None, "status": "EMPTY"})
                s_rec = StorageSlotRecord(
                    id=idx,
                    slot_name=s_name,
                    status=s_info["status"],
                    product_id=s_info["prod"],
                    qr_code=s_info["prod"],
                    is_empty=(s_info["status"] == "EMPTY"),
                    updated_time=now,
                )
                session.add(s_rec)
        else:
            for slot in slots_db:
                s_name = slot.slot_name or (SLOT_NAMES[slot.id - 1] if slot.id <= len(SLOT_NAMES) else "A1")
                slot.slot_name = s_name
                s_info = initial_stock.get(s_name, {"prod": None, "status": "EMPTY"})
                slot.status = s_info["status"]
                slot.product_id = s_info["prod"]
                slot.qr_code = s_info["prod"]
                slot.is_empty = (s_info["status"] == "EMPTY")
                slot.updated_time = now

        # Add initial products to ProductRecord
        for s_name, s_info in initial_stock.items():
            if s_info["prod"]:
                prod = ProductRecord(
                    product_id=s_info["prod"],
                    product_name=s_info["name"],
                    qr_code=s_info["prod"],
                    status="IN_STOCK",
                    current_slot=s_name,
                    created_at=now,
                )
                session.add(prod)

        await session.flush()

        # 4. Create 10 Delivery Requests & FIFO Intralogistics Missions
        print("[ORDERS] Đang tạo 10 đơn hàng mới cho hàng chờ mô phỏng...")
        created_orders = []

        # Order 1..5: DRONE_DELIVERY (Xuất kho giao cho khách)
        # Order 6..10: DRONE_PICKUP (Thu gom từ khách về nhập kho)
        for i in range(10):
            c_info = SAMPLE_CUSTOMERS[i]
            # Ensure CustomerRecord exists
            res_cust = await session.execute(select(CustomerRecord).where(CustomerRecord.phone == c_info["phone"]))
            cust = res_cust.scalars().first()
            if not cust:
                cust = CustomerRecord(name=c_info["name"], phone=c_info["phone"], created_at=now)
                session.add(cust)
                await session.flush()

            prod_id = f"PRD-100{i+1}" if i < 9 else "PRD-1010"
            is_delivery = (i < 5)  # First 5 are export deliveries, next 5 are pickup imports

            if is_delivery:
                deliv_type = "RECEIVE_FROM_WAREHOUSE"
                pickup_lat, pickup_lon, pickup_addr = wh_lat, wh_lon, wh_addr
                drop_lat, drop_lon, drop_addr = c_info["lat"], c_info["lon"], c_info["addr"]
                mission_type = "DRONE_DELIVERY"
                assigned_slot = ["A1", "A2", "A3", "B1", "A1"][i]
                note = f"Giao hàng linh kiện {prod_id} từ ô kho {assigned_slot} đến khách hàng {c_info['name']}"
            else:
                deliv_type = "SEND_TO_WAREHOUSE"
                pickup_lat, pickup_lon, pickup_addr = c_info["lat"], c_info["lon"], c_info["addr"]
                drop_lat, drop_lon, drop_addr = wh_lat, wh_lon, wh_addr
                mission_type = "DRONE_PICKUP"
                assigned_slot = ["B2", "B3", "C1", "C2", "C3"][i - 5]
                note = f"Nhập hàng từ khách hàng {c_info['name']} về lưu trữ tại ô kho {assigned_slot}"

            # Create Delivery Request Record
            req = DeliveryRequestRecord(
                customer_id=cust.id,
                customer_name=c_info["name"],
                customer_phone=c_info["phone"],
                delivery_type=deliv_type,
                pickup_lat=pickup_lat,
                pickup_lon=pickup_lon,
                pickup_address=pickup_addr,
                drop_lat=drop_lat,
                drop_lon=drop_lon,
                drop_address=drop_addr,
                status="APPROVED",  # Approved and queued
                note=note,
                created_at=now,
                updated_at=now,
            )
            session.add(req)
            await session.flush()

            # Create Intralogistics Mission in FIFO WAITING queue
            priority = 10 - i
            mission = IntralogisticsMissionRecord(
                order_id=req.id,
                mission_type=mission_type,
                drone_id="UAV01",
                product_id=prod_id,
                target_slot=assigned_slot,
                status="WAITING",
                current_phase="WAITING",
                state="WAITING",
                priority=priority,
                step_details=f"Đơn hàng #{req.id} đang ở hàng chờ FIFO (Độ ưu tiên: {priority}).",
                created_at=now,
                started_at=None,
                completed_at=None,
                updated_at=now,
            )
            session.add(mission)
            await session.flush()

            # Link mission_id to delivery request
            req.mission_id = mission.id
            created_orders.append((req.id, mission.id, mission_type, prod_id, assigned_slot, c_info["name"]))

        await session.commit()
        print("[SUCCESS] ĐÃ TẠO THÀNH CÔNG 10 ĐƠN HÀNG MỚI (HÀNG CHỜ FIFO):")
        for req_id, m_id, m_type, p_id, slot, c_name in created_orders:
            print(f"  * Đơn #{req_id} -> Mission #{m_id}: [{m_type}] Sản phẩm {p_id} | Ô {slot} | Khách: {c_name}")

if __name__ == "__main__":
    asyncio.run(reset_and_seed_orders())

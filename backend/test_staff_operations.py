import asyncio
import logging
from httpx import AsyncClient, ASGITransport
from app.main import app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def main():
    logger.info("🧪 Bắt đầu In-Memory ASGI Integration Test cho Staff Operations Module...")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test Status
        res = await client.get("/api/staff/status")
        logger.info("1. GET /api/staff/status: status=%d, body=%s", res.status_code, res.json())
        assert res.status_code == 200
        data = res.json()
        assert "system_mode" in data
        assert "staff_op" in data

        # 2. Test Switch Mode to STAFF_OPERATION
        res = await client.post("/api/staff/mode", json={"operation_mode": "STAFF_OPERATION"})
        logger.info("2. POST /api/staff/mode (STAFF_OPERATION): status=%d, body=%s", res.status_code, res.json())
        assert res.status_code == 200
        assert res.json()["operation_mode"] == "STAFF_OPERATION"

        # 3. Test Outbound flow (simulate picking A2, B1)
        res = await client.post("/api/staff/outbound/start", json={"slots": ["A2", "B1"]})
        logger.info("3. POST /api/staff/outbound/start: status=%d, body=%s", res.status_code, res.json())
        assert res.status_code == 200

        # Wait a moment to let background task run
        logger.info("⏳ Chờ tiến trình lấy hàng chạy...")
        await asyncio.sleep(4)

        # Check status
        res = await client.get("/api/staff/status")
        logger.info("4. GET /api/staff/status (Sau khi lấy): %s", res.json())

        # 4. Test Inbound flow (simulate storing 2 items from O1)
        # Cancel outbound if needed
        await client.post("/api/staff/outbound/cancel")
        await asyncio.sleep(1)

        res = await client.post("/api/staff/inbound/start", json={"mode": "QUANTITY", "target_count": 2})
        logger.info("5. POST /api/staff/inbound/start: status=%d, body=%s", res.status_code, res.json())
        assert res.status_code == 200

        logger.info("⏳ Chờ tiến trình nạp hàng chạy...")
        await asyncio.sleep(4)

        res = await client.get("/api/staff/status")
        logger.info("6. GET /api/staff/status (Sau khi nạp): %s", res.json())

        # 5. Stop inbound and switch back to STATION_AUTO
        await client.post("/api/staff/inbound/stop")
        await asyncio.sleep(0.5)
        res = await client.post("/api/staff/mode", json={"operation_mode": "STATION_AUTO"})
        logger.info("7. POST /api/staff/mode (STATION_AUTO): status=%d", res.status_code)
        assert res.status_code == 200

    logger.info("🎉 Tất cả các bài kiểm tra Staff Operations đã HOÀN TẤT THÀNH CÔNG!")


if __name__ == "__main__":
    asyncio.run(main())

"""
Customer & Admin Delivery API routes.

Customer endpoints:
  GET  /warehouse                             — Get warehouse location
  POST /customer/delivery                     — Create delivery request
  GET  /customer/delivery?phone=...          — Track orders by phone
  GET  /customer/delivery/{id}              — Get single order
  POST /customer/address                     — Create saved address
  GET  /customer/address?customer_id=...    — List saved addresses
  PUT  /customer/address/{id}              — Update address
  DELETE /customer/address/{id}            — Delete address

Admin endpoints (no auth, LAN-only):
  GET  /admin/delivery-requests             — All orders (with status filter)
  GET  /admin/delivery-requests/{id}       — Single order detail
  PATCH /admin/delivery-requests/{id}/status — Approve / Reject / update
  GET  /admin/warehouse                     — Get warehouse config
  PUT  /admin/warehouse                     — Update warehouse config
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.database.repository import CustomerRepository, async_session
from app.models.schemas import (
    CustomerAddressCreate,
    CustomerAddressResponse,
    CustomerAddressUpdate,
    DeliveryRequestCreate,
    DeliveryRequestResponse,
    DeliveryStatus,
    DeliveryType,
    WarehouseConfigResponse,
    WarehouseConfigUpdate,
)
from app.websocket.handler import manager

logger = logging.getLogger(__name__)
customer_router = APIRouter()


def _delivery_response(r) -> DeliveryRequestResponse:
    return DeliveryRequestResponse(
        id=r.id,
        customer_id=r.customer_id,
        customer_name=r.customer_name,
        customer_phone=r.customer_phone,
        delivery_type=r.delivery_type,
        pickup_lat=r.pickup_lat,
        pickup_lon=r.pickup_lon,
        pickup_address=r.pickup_address,
        drop_lat=r.drop_lat,
        drop_lon=r.drop_lon,
        drop_address=r.drop_address,
        status=r.status,
        mission_id=r.mission_id,
        note=r.note,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


def _address_response(r) -> CustomerAddressResponse:
    return CustomerAddressResponse(
        id=r.id,
        customer_id=r.customer_id,
        address_type=r.address_type,
        address_name=r.address_name,
        address_text=r.address_text,
        latitude=r.latitude,
        longitude=r.longitude,
        created_at=r.created_at,
    )


# ---------------------------------------------------------------------------
# Warehouse (public read)
# ---------------------------------------------------------------------------

@customer_router.get("/warehouse", response_model=WarehouseConfigResponse)
async def get_warehouse():
    """Public: Get warehouse location (used by customer frontend)."""
    async with async_session() as session:
        repo = CustomerRepository(session)
        wh = await repo.get_warehouse()
        if wh is None:
            # Auto-create default record
            wh = await repo.upsert_warehouse(
                name="Main Warehouse",
                latitude=16.0544,
                longitude=108.2022,
                address_text="Kho chính",
            )
        return WarehouseConfigResponse(
            id=wh.id,
            name=wh.name,
            latitude=wh.latitude,
            longitude=wh.longitude,
            address_text=wh.address_text,
            updated_at=wh.updated_at,
        )


# ---------------------------------------------------------------------------
# Customer Delivery Requests
# ---------------------------------------------------------------------------

@customer_router.post("/customer/delivery", response_model=DeliveryRequestResponse)
async def create_delivery(body: DeliveryRequestCreate):
    """
    Customer creates a delivery request.
    - RECEIVE_FROM_WAREHOUSE: pickup = warehouse, drop = customer location
    - SEND_TO_WAREHOUSE: pickup = customer location, drop = warehouse
    """
    async with async_session() as session:
        repo = CustomerRepository(session)

        # Get warehouse location
        wh = await repo.get_warehouse()
        if wh is None:
            raise HTTPException(status_code=503, detail="Warehouse not configured")

        wh_lat, wh_lon = wh.latitude, wh.longitude
        wh_addr = wh.address_text or wh.name

        # Determine pickup/drop based on delivery type
        if body.delivery_type == DeliveryType.RECEIVE_FROM_WAREHOUSE:
            pickup_lat, pickup_lon, pickup_addr = wh_lat, wh_lon, wh_addr
            drop_lat, drop_lon, drop_addr = (
                body.customer_lat,
                body.customer_lon,
                body.customer_address,
            )
        else:  # SEND_TO_WAREHOUSE
            pickup_lat, pickup_lon, pickup_addr = (
                body.customer_lat,
                body.customer_lon,
                body.customer_address,
            )
            drop_lat, drop_lon, drop_addr = wh_lat, wh_lon, wh_addr

        # Get/create customer record
        customer = await repo.get_or_create_customer(
            name=body.customer_name,
            phone=body.customer_phone,
        )

        record = await repo.create_delivery_request(
            customer_id=customer.id,
            customer_name=body.customer_name,
            customer_phone=body.customer_phone,
            delivery_type=body.delivery_type.value,
            pickup_lat=pickup_lat,
            pickup_lon=pickup_lon,
            pickup_address=pickup_addr,
            drop_lat=drop_lat,
            drop_lon=drop_lon,
            drop_address=drop_addr,
            note=body.note,
        )
        logger.info(
            "Delivery request #%d created: %s — %s",
            record.id,
            body.customer_phone,
            body.delivery_type,
        )
        await manager.broadcast_to_clients({"type": "delivery_requests_update", "payload": {}})
        return _delivery_response(record)


@customer_router.get("/customer/delivery", response_model=list[DeliveryRequestResponse])
async def list_customer_deliveries(phone: str):
    """Customer tracks their orders by phone number."""
    async with async_session() as session:
        repo = CustomerRepository(session)
        records = await repo.get_delivery_requests(customer_phone=phone)
        return [_delivery_response(r) for r in records]


@customer_router.get("/customer/delivery/{request_id}", response_model=DeliveryRequestResponse)
async def get_customer_delivery(request_id: int):
    """Get single delivery request detail."""
    async with async_session() as session:
        repo = CustomerRepository(session)
        record = await repo.get_delivery_request(request_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Delivery request not found")
        return _delivery_response(record)


# ---------------------------------------------------------------------------
# Customer Addresses (saved address book)
# ---------------------------------------------------------------------------

@customer_router.post("/customer/address", response_model=CustomerAddressResponse)
async def create_address(body: CustomerAddressCreate):
    """Create a saved address for a customer."""
    async with async_session() as session:
        repo = CustomerRepository(session)
        record = await repo.create_address(
            customer_id=body.customer_id,
            address_type=body.address_type,
            address_name=body.address_name,
            address_text=body.address_text,
            latitude=body.latitude,
            longitude=body.longitude,
        )
        return _address_response(record)


@customer_router.get("/customer/address", response_model=list[CustomerAddressResponse])
async def list_addresses(
    customer_id: int,
    address_type: Optional[str] = None,
):
    """List saved addresses for a customer. Filter by address_type (RECEIVE/SEND)."""
    async with async_session() as session:
        repo = CustomerRepository(session)
        records = await repo.get_addresses(
            customer_id=customer_id,
            address_type=address_type,
        )
        return [_address_response(r) for r in records]


@customer_router.put("/customer/address/{address_id}", response_model=CustomerAddressResponse)
async def update_address(address_id: int, body: CustomerAddressUpdate):
    """Update a saved address."""
    async with async_session() as session:
        repo = CustomerRepository(session)
        record = await repo.update_address(
            address_id,
            address_type=body.address_type,
            address_name=body.address_name,
            address_text=body.address_text,
            latitude=body.latitude,
            longitude=body.longitude,
        )
        if record is None:
            raise HTTPException(status_code=404, detail="Address not found")
        return _address_response(record)


@customer_router.delete("/customer/address/{address_id}")
async def delete_address(address_id: int):
    """Delete a saved address."""
    async with async_session() as session:
        repo = CustomerRepository(session)
        deleted = await repo.delete_address(address_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Address not found")
        return {"status": "deleted", "id": address_id}


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

@customer_router.get("/admin/delivery-requests", response_model=list[DeliveryRequestResponse])
async def admin_list_deliveries(status: Optional[str] = None, limit: int = 100):
    """Admin: list all delivery requests, optionally filtered by status."""
    async with async_session() as session:
        repo = CustomerRepository(session)
        records = await repo.get_delivery_requests(status=status, limit=limit)
        return [_delivery_response(r) for r in records]


@customer_router.get(
    "/admin/delivery-requests/{request_id}", response_model=DeliveryRequestResponse
)
async def admin_get_delivery(request_id: int):
    """Admin: get single delivery request detail."""
    async with async_session() as session:
        repo = CustomerRepository(session)
        record = await repo.get_delivery_request(request_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Delivery request not found")
        return _delivery_response(record)


@customer_router.patch("/admin/delivery-requests/{request_id}/status")
async def admin_update_delivery_status(
    request_id: int,
    status: DeliveryStatus,
    note: Optional[str] = None,
    mission_id: Optional[int] = None,
):
    """
    Admin: update delivery request status.
    PENDING → APPROVED (Admin approves)
    PENDING → REJECTED (Admin rejects)
    APPROVED → FLYING (Admin starts mission)
    FLYING → DELIVERED / FAILED
    """
    async with async_session() as session:
        repo = CustomerRepository(session)
        record = await repo.update_delivery_request_status(
            request_id=request_id,
            status=status.value,
            note=note,
            mission_id=mission_id,
        )
        if record is None:
            raise HTTPException(status_code=404, detail="Delivery request not found")
        logger.info("Delivery #%d status → %s", request_id, status)
        await manager.broadcast_to_clients({"type": "delivery_requests_update", "payload": {}})
        return {"status": "updated", "id": request_id, "new_status": status}


@customer_router.get("/admin/warehouse", response_model=WarehouseConfigResponse)
async def admin_get_warehouse():
    """Admin: get warehouse config."""
    async with async_session() as session:
        repo = CustomerRepository(session)
        wh = await repo.get_warehouse()
        if wh is None:
            wh = await repo.upsert_warehouse()
        return WarehouseConfigResponse(
            id=wh.id,
            name=wh.name,
            latitude=wh.latitude,
            longitude=wh.longitude,
            address_text=wh.address_text,
            updated_at=wh.updated_at,
        )


@customer_router.put("/admin/warehouse", response_model=WarehouseConfigResponse)
async def admin_update_warehouse(body: WarehouseConfigUpdate):
    """Admin: update warehouse location and name."""
    async with async_session() as session:
        repo = CustomerRepository(session)
        wh = await repo.upsert_warehouse(
            name=body.name,
            latitude=body.latitude,
            longitude=body.longitude,
            address_text=body.address_text,
        )
        logger.info(
            "Warehouse updated: %s (%.6f, %.6f)", wh.name, wh.latitude, wh.longitude
        )
        return WarehouseConfigResponse(
            id=wh.id,
            name=wh.name,
            latitude=wh.latitude,
            longitude=wh.longitude,
            address_text=wh.address_text,
            updated_at=wh.updated_at,
        )

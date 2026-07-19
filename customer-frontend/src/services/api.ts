import type {
  CreateAddressPayload,
  CreateDeliveryPayload,
  CustomerAddress,
  DeliveryRequest,
  WarehouseInfo,
} from "../types/customer";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://192.168.2.28:8000";

export { API_BASE };

// ── Warehouse ──────────────────────────────────────────────────────────────

export async function getWarehouse(): Promise<WarehouseInfo> {
  const res = await fetch(`${API_BASE}/warehouse`);
  if (!res.ok) throw new Error("Cannot fetch warehouse info");
  return res.json();
}

// ── Delivery Requests ──────────────────────────────────────────────────────

export async function createDelivery(payload: CreateDeliveryPayload): Promise<DeliveryRequest> {
  const res = await fetch(`${API_BASE}/customer/delivery`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Tạo đơn thất bại");
  }
  return res.json();
}

export async function getDeliveriesByPhone(phone: string): Promise<DeliveryRequest[]> {
  const res = await fetch(`${API_BASE}/customer/delivery?phone=${encodeURIComponent(phone)}`);
  if (!res.ok) throw new Error("Cannot fetch deliveries");
  return res.json();
}

export async function getDelivery(id: number): Promise<DeliveryRequest> {
  const res = await fetch(`${API_BASE}/customer/delivery/${id}`);
  if (!res.ok) throw new Error("Cannot fetch delivery");
  return res.json();
}

// ── Customer Addresses ─────────────────────────────────────────────────────

export async function createAddress(payload: CreateAddressPayload): Promise<CustomerAddress> {
  const res = await fetch(`${API_BASE}/customer/address`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Tạo địa chỉ thất bại");
  }
  return res.json();
}

export async function getAddresses(
  customerId: number,
  addressType?: "RECEIVE" | "SEND",
): Promise<CustomerAddress[]> {
  const params = new URLSearchParams({ customer_id: String(customerId) });
  if (addressType) params.append("address_type", addressType);
  const res = await fetch(`${API_BASE}/customer/address?${params}`);
  if (!res.ok) throw new Error("Cannot fetch addresses");
  return res.json();
}

export async function updateAddress(
  id: number,
  data: Partial<Omit<CreateAddressPayload, "customer_id">>,
): Promise<CustomerAddress> {
  const res = await fetch(`${API_BASE}/customer/address/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Cập nhật địa chỉ thất bại");
  return res.json();
}

export async function deleteAddress(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/customer/address/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Xóa địa chỉ thất bại");
}

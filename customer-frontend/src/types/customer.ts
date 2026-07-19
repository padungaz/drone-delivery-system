// Customer app types

export type DeliveryType = "RECEIVE_FROM_WAREHOUSE" | "SEND_TO_WAREHOUSE";

export type DeliveryStatus =
  | "PENDING"
  | "APPROVED"
  | "FLYING"
  | "DELIVERED"
  | "FAILED"
  | "REJECTED";

export interface WarehouseInfo {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
  address_text: string;
}

export interface DeliveryRequest {
  id: number;
  customer_id: number;
  customer_name: string;
  customer_phone: string;
  delivery_type: DeliveryType;
  pickup_lat: number;
  pickup_lon: number;
  pickup_address: string;
  drop_lat: number;
  drop_lon: number;
  drop_address: string;
  status: DeliveryStatus;
  mission_id: number | null;
  note: string;
  created_at: string;
  updated_at: string;
}

export interface CustomerAddress {
  id: number;
  customer_id: number;
  address_type: "RECEIVE" | "SEND";
  address_name: string;
  address_text: string;
  latitude: number;
  longitude: number;
  created_at: string;
}

export interface CreateDeliveryPayload {
  customer_name: string;
  customer_phone: string;
  delivery_type: DeliveryType;
  customer_lat: number;
  customer_lon: number;
  customer_address: string;
  note: string;
}

export interface CreateAddressPayload {
  customer_id: number;
  address_type: "RECEIVE" | "SEND";
  address_name: string;
  address_text: string;
  latitude: number;
  longitude: number;
}

export interface LatLon {
  lat: number;
  lon: number;
}

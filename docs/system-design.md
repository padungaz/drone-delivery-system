# Thiết kế Hệ thống (System Design)

Tài liệu này cung cấp cái nhìn tổng quát về kiến trúc hệ thống, cơ sở dữ liệu, các giao thức kết nối, và máy trạng thái hữu hạn (FSM) điều khiển chuyến bay.

---

## 1. Sơ đồ Kiến trúc Hệ thống

```mermaid
graph TD
    subgraph ClientLayer [Client Applications]
        AdminApp["🖥️ Admin Frontend (React + TS)<br/>Port: 5173"]
        CustApp["📱 Customer Frontend (React + TS)<br/>Port: 5174"]
    end

    subgraph ServerLayer [FastAPI Server]
        API["⚡ FastAPI Web App<br/>Port: 8000"]
        DB[(💾 SQLite Database<br/>drone_delivery.db)]
        ConnMgr["🔌 Connection Manager<br/>(WebSockets)"]
    end

    subgraph HardwareLayer [Drone & Companion Computer]
        RPi["🍓 Raspberry Pi 5<br/>(Companion Computer)"]
        Pixhawk["🛸 Pixhawk 6C<br/>(Flight Controller / PX4)"]
        Cam["📷 RPi Camera<br/>(ArUco Landing / Stream)"]
    end

    CustApp -->|HTTP REST API| API
    AdminApp -->|HTTP REST API| API
    AdminApp <-->|WebSockets (Telemetry & Cmds)| ConnMgr
    ConnMgr <-->|WebSockets| RPi
    
    API <-->|SQLAlchemy Async| DB
    RPi <-->|MAVLink (Serial/Telem)| Pixhawk
    RPi -->|Camera Interface| Cam

    style AdminApp fill:#2a3a52,stroke:#3b82f6,stroke-width:2px,color:#fff
    style CustApp fill:#1f2d45,stroke:#8b5cf6,stroke-width:2px,color:#fff
    style API fill:#111827,stroke:#10b981,stroke-width:2px,color:#fff
    style DB fill:#111827,stroke:#f59e0b,stroke-width:2px,color:#fff
    style RPi fill:#800020,stroke:#ef4444,stroke-width:2px,color:#fff
    style Pixhawk fill:#333,stroke:#666,stroke-width:2px,color:#fff
```

---

## 2. Luồng Nghiệp vụ Giao hàng (Delivery Flow)

```mermaid
sequenceDiagram
    autonumber
    actor Customer as 👤 Khách hàng
    participant CustApp as 📱 Customer App
    participant Backend as ⚡ FastAPI Backend
    actor Admin as 🖥️ Admin Dashboard
    participant Drone as 🚁 Drone (Companion + PX4)

    Customer->>CustApp: Chọn "Nhận/Gửi" & Điền thông tin + Bản đồ
    CustApp->>Backend: POST /customer/delivery (Tọa độ nhận/gửi)
    Note over Backend: Auto-resolve tọa độ:<br/>Kho ⟷ Khách hàng
    Backend-->>CustApp: Trả về đơn hàng (Status: PENDING)
    
    Admin->>Backend: GET /admin/delivery-requests
    Backend-->>Admin: Trả về danh sách đơn hàng
    Admin->>Backend: PATCH /admin/delivery-requests/{id}/status (APPROVED)
    
    Admin->>Admin: Nhấn "Chọn & START"
    Note over Admin: Tọa độ tự động điền vào Form bay
    Admin->>Backend: POST /missions/start (Với tọa độ Home, Pickup, Drop)
    Backend->>Backend: Cập nhật status đơn hàng: FLYING
    Backend->>Drone: Gửi Payload bay (MAVLink Commands)
    
    loop Realtime Telemetry
        Drone-->>Backend: Telemetry (GPS, Vận tốc, Pin, Camera status)
        Backend-->>Admin: WebSocket Push Telemetry
    end

    Drone->>Drone: Auto Landing bằng ArUco Precision Landing
    Drone-->>Backend: Báo cáo hoàn thành nhiệm vụ
    Backend->>Backend: Cập nhật status đơn hàng: DELIVERED
```

---

## 3. Thiết kế Cơ sở Dữ liệu (ERD)

Hệ thống sử dụng SQLite với 4 bảng dữ liệu cốt lõi phục vụ nghiệp vụ (version 2.0).

```mermaid
erDiagram
    customers {
        int id PK
        string name
        string phone UK
        datetime created_at
    }

    customer_addresses {
        int id PK
        int customer_id FK
        string address_type "RECEIVE / SEND"
        string address_name "Nhà, Công ty..."
        string address_text
        float latitude
        float longitude
        datetime created_at
    }

    delivery_requests {
        int id PK
        int customer_id FK
        string customer_name
        string customer_phone
        string delivery_type "RECEIVE_FROM_WAREHOUSE / SEND_TO_WAREHOUSE"
        float pickup_lat
        float pickup_lon
        string pickup_address
        float drop_lat
        float drop_lon
        string drop_address
        string status "PENDING / APPROVED / FLYING / DELIVERED / FAILED / REJECTED"
        int mission_id FK
        text note
        datetime created_at
        datetime updated_at
    }

    warehouse_config {
        int id PK
        string name
        float latitude
        float longitude
        string address_text
        datetime updated_at
    }

    customers ||--o{ customer_addresses : "has"
    customers ||--o{ delivery_requests : "places"
```

---

## 4. Tài liệu API (RESTful Endpoints)

### 4.1. Dành cho Khách hàng (Customer API)
* **`GET /warehouse`**: Lấy vị trí GPS của kho hàng đang được cấu hình.
* **`POST /customer/delivery`**: Đặt đơn hàng mới (Nhận hàng từ kho hoặc Gửi hàng về kho).
* **`GET /customer/delivery?phone={phone}`**: Tra cứu lịch sử đơn hàng theo số điện thoại.
* **`POST /customer/address`**: Thêm một địa chỉ nhận/gửi mới.
* **`GET /customer/address?customer_id={id}`**: Lấy danh sách địa chỉ đã lưu.
* **`PUT /customer/address/{id}`**: Cập nhật địa chỉ đã lưu.
* **`DELETE /customer/address/{id}`**: Xóa địa chỉ.

### 4.2. Dành cho Quản trị viên (Admin API)
* **`GET /admin/delivery-requests`**: Xem danh sách đơn hàng (hỗ trợ lọc `PENDING`, `APPROVED`, `FLYING`,...).
* **`PATCH /admin/delivery-requests/{id}/status`**: Cập nhật trạng thái đơn hàng (Duyệt, Từ chối).
* **`GET /admin/warehouse`**: Xem cấu hình chi tiết của kho hàng.
* **`PUT /admin/warehouse`**: Chỉnh sửa vị trí (GPS), tên kho hoặc địa chỉ.

---

## 5. Máy Trạng thái Chuyến bay (Flight Control FSM)

Toàn bộ quy trình điều khiển Drone được mô hình hóa qua Finite State Machine (FSM).

```mermaid
stateDiagram-v2
    [*] --> IDLE : Power On
    IDLE --> TAKEOFF : Launch Command (Admin)
    TAKEOFF --> FLY_TO_PICKUP : Reach Alt Limit
    
    state FLY_TO_PICKUP {
        [*] --> NavigateGPS
        NavigateGPS --> ArUcoPrecisionLanding : ArUco detected
    }
    
    FLY_TO_PICKUP --> WAIT_PICKUP_CONFIRM : Disarm (At Pickup Location)
    WAIT_PICKUP_CONFIRM --> FLY_TO_DROP : Confirm Load (Admin/User)
    
    state FLY_TO_DROP {
        [*] --> NavigateGPSDrop
        NavigateGPSDrop --> ArUcoPrecisionLandingDrop : ArUco detected
    }
    
    FLY_TO_DROP --> WAIT_DROP_CONFIRM : Disarm (At Drop Location)
    WAIT_DROP_CONFIRM --> RETURN_HOME : Confirm Unload (Admin/User)
    
    RETURN_HOME --> LAND : Arrived Home Coords
    LAND --> IDLE : Disarmed (Completed)
    
    IDLE --> RTL : RTL Triggered (Any State)
    FLY_TO_PICKUP --> RTL : Battery Low / Failsafe
    FLY_TO_DROP --> RTL : Battery Low / Failsafe
    RTL --> LAND
```

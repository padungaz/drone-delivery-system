# Thiết kế Hệ thống (System Design v3.0)

Tài liệu này cung cấp cái nhìn tổng quát và chi tiết về kiến trúc hệ thống giao hàng bằng Drone kết hợp Trạm lưu kho thông minh (Smart Intralogistics Controller System), cơ sở dữ liệu v3.0, các giao thức kết nối LAN, máy trạng thái hữu hạn (FSM) và toàn bộ **Lưu đồ Thuật toán (Flowcharts)** tổng hợp cũng như chi tiết từng phân hệ.

---

## 1. Sơ đồ Kiến trúc Hệ thống (v3.0)

### 1.1. Sơ đồ Khối Kiến trúc Phần cứng & Phần mềm

```mermaid
graph TD
    subgraph ClientLayer [Client Applications & Controls]
        AdminApp["🖥️ Admin Dashboard (React + TS)<br/>Port: 5173 (Kho thông minh + Live Map)"]
        CustApp["📱 Customer App (React + TS)<br/>Port: 5174"]
    end

    subgraph ServerLayer [Centralized FastAPI Orchestration Engine]
        API["⚡ Central FastAPI Web App (v3.0)<br/>Port: 8000"]
        DB[(💾 SQLite Database<br/>drone_delivery.db)]
        WSMgr["🔌 WebSocket Hub<br/>/ws/system & /ws/drone"]
        Orchestrator["⚙️ Master Intralogistics FSM<br/>(MissionManager)"]
    end

    subgraph WarehouseHardware [LAN Hardware & Smart Warehouse]
        PLC["⚙️ Siemens S7-1200 PLC<br/>(Pad Sensor, Clamps X/Y, Z-Lift)"]
        ROBOT["🤖 FAIRINO Robot Arm<br/>(Cobot 6-DoF, Pick/Place A1..C3)"]
        CAM["📷 QR Code Vision Camera<br/>(Auto Scan & Slot Assign)"]
        GRID["📦 Ô chứa hàng 3x3<br/>(Slots A1..C3 Grid)"]
    end

    subgraph UAVHardware [UAV Drone & Flight Control]
        RPi["🍓 Raspberry Pi 5<br/>(Companion Computer)"]
        Pixhawk["🛸 Pixhawk 6C<br/>(PX4 Firmware / MAVLink)"]
        ArUcoCam["📷 RPi USB Cam<br/>(ArUco Precision Landing)"]
    end

    CustApp -->|HTTP REST| API
    AdminApp -->|HTTP REST| API
    AdminApp <-->|WebSockets (/ws/system)| WSMgr
    WSMgr <-->|WebSockets (/ws/drone)| RPi
    
    API <-->|SQLAlchemy Async| DB
    API <--> Orchestrator
    Orchestrator -->|PLC Commands| PLC
    Orchestrator -->|Robot Commands| ROBOT
    Orchestrator -->|Inventory Logic| GRID
    CAM -->|QR Payload API| API

    RPi <-->|MAVLink (UART)| Pixhawk
    RPi --> ArUcoCam

    style AdminApp fill:#2a3a52,stroke:#3b82f6,stroke-width:2px,color:#fff
    style CustApp fill:#1f2d45,stroke:#8b5cf6,stroke-width:2px,color:#fff
    style API fill:#111827,stroke:#10b981,stroke-width:2px,color:#fff
    style DB fill:#111827,stroke:#f59e0b,stroke-width:2px,color:#fff
    style PLC fill:#1e3a8a,stroke:#3b82f6,stroke-width:2px,color:#fff
    style ROBOT fill:#701a75,stroke:#c084fc,stroke-width:2px,color:#fff
    style RPi fill:#800020,stroke:#ef4444,stroke-width:2px,color:#fff
```

---

### 1.2. Lưu đồ Thuật toán Tổng hợp Toàn Hệ thống (Master System Algorithm Flowchart)

```mermaid
flowchart TD
    Start([🚀 KÍCH HOẠT HỆ THỐNG]) --> UserRequest{Loại yêu cầu}

    %% Luồng 1: Khách hàng đặt đơn nhận/gửi
    UserRequest -->|1. Đặt đơn giao nhận| CustOrder[Khách hàng gửi yêu cầu qua Customer App]
    CustOrder --> BackendPending[Backend lưu đơn hàng trạng thái PENDING]
    BackendPending --> AdminReview{Admin duyệt đơn?}
    AdminReview -->|Từ chối| OrderCancel[Hủy đơn hàng]
    AdminReview -->|Phê duyệt| MissionStart[Admin phát lệnh START Chuyến bay / Mission]

    %% Luồng 2: Điều phối Drone bay
    MissionStart --> UAVTakeoff[UAV Cất cánh & Bay theo tọa độ GPS]
    UAVTakeoff --> ReachDestination{Đến điểm chỉ định?}
    ReachDestination -->|Chưa đến| UAVTakeoff
    ReachDestination -->|Đến vị trí| DetectArUco{Camera quét thấy ArUco?}
    DetectArUco -->|Có| ArUcoLand[Hạ cánh chính xác bằng ArUco Precision Landing]
    DetectArUco -->|Không| GPSLand[Hạ cánh khẩn cấp theo GPS]
    
    ArUcoLand --> PadTouchdown[UAV tiếp đất sàn Landing Pad]
    GPSLand --> PadTouchdown

    %% Luồng 3: Điều phối Trạm Kho thông minh
    PadTouchdown --> PLCSensor{Cảm biến PLC phát hiện Drone?}
    PLCSensor -->|Chờ| PadTouchdown
    PLCSensor -->|Đã phát hiện| PLCLock[PLC đóng kẹp X/Y - LOCK_DRONE]
    
    PLCLock --> CheckMissionType{Loại nhiệm vụ kho?}

    %% Flow 8: DRONE_PICKUP (Nhập kho)
    CheckMissionType -->|DRONE_PICKUP| RobotHome1[Robot FAIRINO di chuyển về HOME]
    RobotHome1 --> PLCZUp1[PLC nâng Trục Z - Z_UP]
    PLCZUp1 --> RobotPickUAV[Robot gắp sản phẩm từ UAV]
    RobotPickUAV --> RobotHome2[Robot lùi về HOME]
    RobotHome2 --> PLCZDown1[PLC hạ Trục Z - Z_DOWN]
    PLCZDown1 --> FindSlot[InventoryManager tìm ô trống A1..C3]
    FindSlot --> SlotFound{Có ô trống?}
    SlotFound -->|Không| StoreError[Báo lỗi Kho đầy - ERROR_NO_FREE_SLOT]
    SlotFound -->|Có| RobotStoreSlot[Robot cất sản phẩm vào ô - OCCUPIED]
    RobotStoreSlot --> PLCUnlock1[PLC mở kẹp X/Y - UNLOCK_DRONE]
    PLCUnlock1 --> PickupComplete([✅ HOÀN THÀNH NHẬP KHO])

    %% Flow 9: DRONE_DELIVERY (Xuất kho đi giao)
    CheckMissionType -->|DRONE_DELIVERY| FindProductSlot[InventoryManager tìm ô chứa hàng product_id]
    FindProductSlot --> ProdFound{Tìm thấy hàng?}
    ProdFound -->|Không| DeliveryError[Báo lỗi Không có hàng - ERROR_PRODUCT_NOT_FOUND]
    ProdFound -->|Có| RobotPickSlot[Robot gắp sản phẩm từ ô - Slot -> EMPTY]
    RobotPickSlot --> RobotHome3[Robot lùi về HOME giữ hàng]
    RobotHome3 --> PLCZUp2[PLC nâng Trục Z - Z_UP]
    PLCZUp2 --> RobotPlaceUAV[Robot đặt sản phẩm lên gá Drone]
    RobotPlaceUAV --> RobotHome4[Robot lùi về HOME]
    RobotHome4 --> PLCZDown2[PLC hạ Trục Z - Z_DOWN]
    PLCZDown2 --> PLCUnlock2[PLC mở kẹp X/Y - UNLOCK_DRONE]
    PLCUnlock2 --> UAVTakeoffDelivery[Cấp phép UAV cất cánh đi giao hàng]
    UAVTakeoffDelivery --> DeliveryComplete([✅ HOÀN THÀNH XUẤT KHO & GIAO HÀNG])

    style Start fill:#10b981,color:#fff
    style PickupComplete fill:#10b981,color:#fff
    style DeliveryComplete fill:#10b981,color:#fff
    style StoreError fill:#ef4444,color:#fff
    style DeliveryError fill:#ef4444,color:#fff
```

---

## 2. Luồng Nghiệp vụ Giao hàng & Kho thông minh

### 2.1. Luồng Giao hàng Khách hàng (Delivery Flow)
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
    Backend-->>CustApp: Trả về đơn hàng (Status: PENDING)
    
    Admin->>Backend: GET /admin/delivery-requests
    Admin->>Backend: PATCH /admin/delivery-requests/{id}/status (APPROVED)
    
    Admin->>Admin: Nhấn "Chọn & START"
    Admin->>Backend: POST /missions/start (Home, Pickup, Drop)
    Backend->>Drone: Gửi Payload bay (MAVLink Commands)
    
    loop Realtime Telemetry
        Drone-->>Backend: Telemetry (GPS, Pin, ArUco detection)
        Backend-->>Admin: WebSocket Push Telemetry
    end

    Drone->>Drone: Auto Landing bằng ArUco Precision Landing
    Drone-->>Backend: Báo cáo hoàn thành nhiệm vụ
    Backend->>Backend: Cập nhật status đơn hàng: DELIVERED
```

---

### 2.2. Sơ đồ Trình tự Bắt tay Tín hiệu (Handshake Sequence) giữa PLC & Robot FAIRINO

#### A. Trình tự Bắt tay Nhập kho (Flow 8: DRONE_PICKUP)
```mermaid
sequenceDiagram
    autonumber
    participant UAV as 🚁 UAV Drone
    participant Backend as ⚡ FastAPI (MissionManager)
    participant PLC as ⚙️ PLC S7-1200
    participant Robot as 🤖 Robot FAIRINO
    participant Grid as 📦 Ô chứa 3x3

    UAV->>PLC: Touchdown sàn hạ cánh
    PLC->>Backend: drone_detected = True
    Backend->>PLC: Command: LOCK_DRONE
    PLC->>PLC: Đóng kẹp X & Y (LOCKING -> DONE)
    PLC-->>Backend: Status: drone_locked = True
    
    Backend->>Robot: Command: MOVE_HOME
    Robot-->>Backend: Status: READY (At HOME)

    Backend->>Robot: Command: REQUEST_Z_UP
    Backend->>PLC: Command: Z_UP
    PLC->>PLC: Nâng bàn nâng Z
    PLC-->>Backend: Status: z_axis = "UP"

    Backend->>Robot: Command: PICK_PRODUCT (from UAV)
    Robot->>Robot: Gắp sản phẩm từ UAV
    Robot-->>Backend: Status: holding_product = "SP001"

    Backend->>Robot: Command: MOVE_HOME
    Backend->>Robot: Command: REQUEST_Z_DOWN
    Backend->>PLC: Command: Z_DOWN
    PLC->>PLC: Hạ bàn nâng Z về vị trí an toàn
    PLC-->>Backend: Status: z_axis = "DOWN"

    Backend->>Grid: find_available_slot()
    Grid-->>Backend: Return slot = "B2"
    Backend->>Robot: Command: STORE (slot="B2")
    Robot->>Grid: Đặt sản phẩm vào ô B2
    Grid->>Grid: Cập nhật slot B2 -> OCCUPIED
    Robot-->>Backend: Status: holding_product = None

    Backend->>PLC: Command: UNLOCK_DRONE
    PLC->>PLC: Mở kẹp X & Y
    PLC-->>Backend: Status: drone_locked = False
```

#### B. Trình tự Bắt tay Xuất kho (Flow 9: DRONE_DELIVERY)
```mermaid
sequenceDiagram
    autonumber
    participant Backend as ⚡ FastAPI (MissionManager)
    participant Grid as 📦 Ô chứa 3x3
    participant Robot as 🤖 Robot FAIRINO
    participant UAV as 🚁 UAV Drone
    participant PLC as ⚙️ PLC S7-1200

    Backend->>Grid: find_slot_by_product_id("SP001")
    Grid-->>Backend: Return slot = "A3"
    
    Backend->>Robot: Command: PICK (slot="A3")
    Robot->>Grid: Gắp sản phẩm từ ô A3
    Grid->>Grid: Cập nhật slot A3 -> EMPTY
    Robot-->>Backend: Status: holding_product = "SP001"
    
    Backend->>Robot: Command: MOVE_HOME
    Robot-->>Backend: Status: READY (At HOME holding product)

    UAV->>PLC: Tiếp đất sàn hạ cánh
    PLC->>Backend: drone_detected = True
    Backend->>PLC: Command: LOCK_DRONE
    PLC-->>Backend: Status: drone_locked = True

    Backend->>Robot: Command: REQUEST_Z_UP
    Backend->>PLC: Command: Z_UP
    PLC-->>Backend: Status: z_axis = "UP"

    Backend->>Robot: Command: PLACE_PRODUCT (onto UAV)
    Robot->>UAV: Đặt sản phẩm lên gá UAV
    Robot-->>Backend: Status: holding_product = None

    Backend->>Robot: Command: MOVE_HOME
    Backend->>Robot: Command: REQUEST_Z_DOWN
    Backend->>PLC: Command: Z_DOWN
    PLC-->>Backend: Status: z_axis = "DOWN"

    Backend->>PLC: Command: UNLOCK_DRONE
    PLC-->>Backend: Status: drone_locked = False
    Backend->>UAV: Phát lệnh MAVLink Cấp phép Cất cánh
```

---

## 3. Quy trình Trạng thái Kho thông minh (Intralogistics FSM)

### Flow 8: DRONE_PICKUP (Drone mang hàng về Kho nhập)
1. **STARTED**: Khởi tạo nhiệm vụ `DRONE_PICKUP`.
2. **TAKEOFF_AND_FLYING**: Drone di chuyển tới trạm hạ cánh kho.
3. **TOUCHDOWN**: Drone tiếp đất sàn hạ cánh. Cảm biến PLC nhận diện.
4. **DRONE_LOCKED**: PLC đóng kẹp cơ khí X & Y khóa chặt chân Drone.
5. **ROBOT_HOME**: Cánh tay Robot FAIRINO di chuyển về gốc HOME.
6. **Z_UP**: PLC điều khiển trục Z nâng lên độ cao nhận hàng.
7. **ROBOT_PICK**: Robot gắp hàng khỏi UAV.
8. **Z_DOWN**: PLC hạ trục Z về độ cao kho.
9. **STORE_SLOT**: InventoryManager tìm ô trống (A1..C3), Robot cất hàng vào ô.
10. **UNLOCK_DRONE**: PLC mở kẹp giải phóng Drone, hoàn tất nhiệm vụ (`MISSION_COMPLETE`).

### Flow 9: DRONE_DELIVERY (Xuất hàng từ Kho lên Drone)
1. **STARTED**: Khởi tạo nhiệm vụ `DRONE_DELIVERY`.
2. **FIND_PRODUCT**: Tìm vị trí sản phẩm trong ô lưu trữ (A1..C3).
3. **ROBOT_PICK_SLOT**: Robot gắp hàng từ ô lưu trữ & chuyển ô sang `EMPTY`.
4. **DRONE_LOCKED**: Drone tiếp đất & PLC đóng kẹp X/Y.
5. **Z_UP & PLACE**: Trục Z nâng lên, Robot đặt hàng lên Drone.
6. **Z_DOWN**: Trục Z hạ xuống, Robot rút về HOME.
7. **UNLOCK_DRONE**: PLC mở kẹp khóa, phát lệnh cấp phép cất cánh cho Drone (`MISSION_COMPLETE`).

---

## 4. Thiết kế Cơ sở Dữ liệu (ERD v3.0)

```mermaid
erDiagram
    devices {
        int id PK
        string device_name UK
        string device_type "UAV / PLC / ROBOT / CAMERA"
        string ip_address
        string status "ONLINE / OFFLINE / BUSY / ERROR"
        datetime last_heartbeat
        datetime created_at
    }

    products {
        int id PK
        string product_id UK
        string product_name
        string qr_code UK
        string status "IN_STOCK / IN_TRANSIT / DELIVERED"
        string current_slot "A1..C3"
        datetime created_at
    }

    storage_slots {
        int id PK "1..9"
        string slot_name UK "A1..C3"
        string status "EMPTY / OCCUPIED / RESERVED"
        string product_id FK
        bool is_empty
        string qr_code
        string sender_name
        string sender_address
        datetime updated_time
    }

    intralogistics_missions {
        int id PK
        string mission_type "DRONE_PICKUP / DRONE_DELIVERY"
        string drone_id
        string product_id
        string target_slot
        string state "STARTED / MISSION_COMPLETE / ERROR_..."
        text step_details
        datetime created_at
        datetime updated_at
    }

    system_logs {
        int id PK
        string log_type "SYSTEM_LOG / MISSION_LOG / DEVICE_LOG / ERROR_LOG"
        string source "PLC / ROBOT / UAV / SERVER / CAMERA"
        text message
        datetime created_at
    }

    customers {
        int id PK
        string name
        string phone UK
        datetime created_at
    }

    customer_addresses {
        int id PK
        int customer_id FK
        string address_type
        string address_name
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
        string delivery_type
        float pickup_lat
        float pickup_lon
        float drop_lat
        float drop_lon
        string status
        int mission_id FK
        datetime created_at
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
    products ||--o| storage_slots : "stored in"
```

---

## 5. Tài liệu API (RESTful Endpoints & WebSocket)

### 5.1. Smart Intralogistics API (v1 Router)
* **`GET /api/v1/devices`**: Danh sách tất cả thiết bị phần cứng trong mạng LAN.
* **`POST /api/v1/devices/register`**: Đăng ký thiết bị phần cứng mới.
* **`POST /api/v1/devices/heartbeat`**: Gửi heartbeat báo trạng thái Online.
* **`GET /api/v1/plc/status`**: Lấy trạng thái hiện tại của PLC (cảm biến sàn, kẹp X/Y, vị trí Z).
* **`POST /api/v1/plc/command`**: Gửi lệnh điều khiển PLC (`LOCK_DRONE`, `UNLOCK_DRONE`, `Z_UP`, `Z_DOWN`).
* **`GET /api/v1/robot/status`**: Lấy trạng thái Robot FAIRINO (State, slot, holding product).
* **`POST /api/v1/robot/command`**: Gửi lệnh Robot (`MOVE_HOME`, `PICK`, `STORE`, `REQUEST_Z_UP`, `REQUEST_Z_DOWN`).
* **`GET /api/v1/inventory/slots`**: Lấy thông tin 9 ô chứa hàng 3x3 (A1..C3).
* **`PUT /api/v1/inventory/slots/{slot_name}`**: Cập nhật trạng thái ô hàng.
* **`POST /api/v1/inventory/qr-scan`**: Nhận dữ liệu quét mã QR từ camera & tự động gán ô.
* **`POST /api/v1/missions/drone-pickup`**: Khởi chạy quy trình FSM DRONE_PICKUP (Flow 8).
* **`POST /api/v1/missions/drone-delivery`**: Khởi chạy quy trình FSM DRONE_DELIVERY (Flow 9).
* **`GET /api/v1/missions/active`**: Lấy thông tin nhiệm vụ FSM đang hoạt động.

### 5.2. WebSocket Realtime Hub
* **`WS /ws/system`**: Kênh Broadcast thông tin trạng thái toàn bộ hệ thống (Realtime Telemetry, PLC, Robot, ô chứa 3x3, và tiến trình FSM).
* **`WS /ws/drone/{drone_id}`**: Kênh WebSocket giao tiếp hai chiều với Companion Raspberry Pi trên Drone.

---

## 6. Máy Trạng thái Chuyến bay (Flight Control FSM)

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

---

## 7. Các Lưu đồ Thuật toán Chi tiết Từng Phân hệ (Detailed Component Flowcharts)

### 7.1. Lưu đồ Thuật toán Điều khiển PLC Siemens S7-1200 Docking Station

```mermaid
flowchart TD
    PLCStart([⚙️ KHỞI ĐỘNG VÒNG LẶP PLC S7-1200]) --> ReadSensors[Đọc trạng thái cảm biến Pad & Công tắc hành trình]
    ReadSensors --> WaitCmd{Nhận Lệnh từ Central Backend?}
    
    WaitCmd -->|Không| ReadSensors
    WaitCmd -->|Có: LOCK_DRONE| LockProcess[Cấp nguồn Xilanh Kẹp X & Y]
    LockProcess --> CheckClamps{Kẹp X & Y đã đóng hết hành trình?}
    CheckClamps -->|Đang đóng| LockProcess
    CheckClamps -->|Xác nhận DONE| SetLocked[Gán drone_locked = True & Phản hồi Backend]

    WaitCmd -->|Có: UNLOCK_DRONE| UnlockProcess[Thu xilanh Kẹp X & Y về vị trí MỞ]
    UnlockProcess --> SetUnlocked[Gán drone_locked = False, drone_detected = False]

    WaitCmd -->|Có: Z_UP| ZUpProcess[Bật Động cơ/Xilanh nâng Bàn Z lên vị trí cao]
    ZUpProcess --> CheckZUp{Đạt công tắc hành trình Z_UP?}
    CheckZUp -->|Đang nâng| ZUpProcess
    CheckZUp -->|Đã tới| SetZUp[Gán z_axis = UP & Phản hồi Backend]

    WaitCmd -->|Có: Z_DOWN| ZDownProcess[Hạ Bàn Z về vị trí thấp/HOME]
    ZDownProcess --> CheckZDown{Đạt công tắc hành trình Z_DOWN?}
    CheckZDown -->|Đang hạ| ZDownProcess
    CheckZDown -->|Đã tới| SetZDown[Gán z_axis = DOWN & Phản hồi Backend]

    SetLocked --> ReadSensors
    SetUnlocked --> ReadSensors
    SetZUp --> ReadSensors
    SetZDown --> ReadSensors

    style PLCStart fill:#1e3a8a,color:#fff
    style SetLocked fill:#10b981,color:#fff
    style SetUnlocked fill:#10b981,color:#fff
    style SetZUp fill:#10b981,color:#fff
    style SetZDown fill:#10b981,color:#fff
```

---

### 7.2. Lưu đồ Thuật toán Điều khiển Cánh tay Robot FAIRINO (Cobot 6-DoF)

```mermaid
flowchart TD
    RobotStart([🤖 KHỞI ĐỘNG ROBOT FAIRINO]) --> RobotIdle[Trạng thái READY / IDLE - Kiểm tra kết nối TCP/IP]
    RobotIdle --> WaitRobotCmd{Nhận Lệnh Điều khiển?}

    WaitRobotCmd -->|Không| RobotIdle

    %% Lệnh MOVE_HOME
    WaitRobotCmd -->|MOVE_HOME| ExecHome[Chạy thuật toán quy hoạch quỹ đạo đến điểm HOME]
    ExecHome --> CheckHome{Đã về điểm HOME?}
    CheckHome -->|Đang di chuyển| ExecHome
    CheckHome -->|Đã tới| SetStateReady[Cập nhật state = READY, current_slot = None]

    %% Lệnh PICK / PICK_PRODUCT
    WaitRobotCmd -->|PICK / PICK_PRODUCT| CheckSource{Gắp từ đâu?}
    CheckSource -->|Gắp từ UAV| PickUAVPos[Di chuyển Tay kẹp đến vị trí gá UAV]
    CheckSource -->|Gắp từ Ô Slot| PickSlotPos[Di chuyển Tay kẹp đến vị trí Ô A1..C3]
    PickUAVPos --> CloseGripper[Kích hoạt Tay kẹp Hút / Gắp sản phẩm]
    PickSlotPos --> CloseGripper
    CloseGripper --> SetHolding[Gán holding_product = SP_ID & state = READY]

    %% Lệnh STORE / PLACE_PRODUCT
    WaitRobotCmd -->|STORE / PLACE_PRODUCT| CheckDest{Đặt vào đâu?}
    CheckDest -->|Đặt vào Ô Slot| PlaceSlotPos[Di chuyển Tay kẹp tới vị trí Ô A1..C3]
    CheckDest -->|Đặt lên UAV| PlaceUAVPos[Di chuyển Tay kẹp tới gá chứa UAV]
    PlaceSlotPos --> OpenGripper[Nhả Tay kẹp giải phóng sản phẩm]
    PlaceUAVPos --> OpenGripper
    OpenGripper --> ClearHolding[Gán holding_product = None & state = READY]

    SetStateReady --> RobotIdle
    SetHolding --> RobotIdle
    ClearHolding --> RobotIdle

    style RobotStart fill:#701a75,color:#fff
    style SetStateReady fill:#10b981,color:#fff
    style SetHolding fill:#10b981,color:#fff
    style ClearHolding fill:#10b981,color:#fff
```

---

### 7.3. Lưu đồ Thuật toán Companion Raspberry Pi 5 & Hạ cánh chính xác ArUco

```mermaid
flowchart TD
    RPiStart([🍓 KHỞI ĐỘNG DRONE COMPANION]) --> InitMAVLink[Mở Cổng UART kết nối MAVLink Pixhawk 6C]
    InitMAVLink --> InitWS[Mở Kết nối WebSocket với Backend Central /ws/drone]
    InitWS --> CameraLoop[Mở OpenCV USB Camera Video Stream]

    CameraLoop --> ReadFrame[Đọc Frame Hình ảnh từ Camera]
    ReadFrame --> DetectArUco[Chạy cv2.aruco.detectMarkers]
    DetectArUco --> MarkerFound{Phát hiện ArUco Marker?}

    MarkerFound -->|Không| StandardFlight[Tiếp tục bay điều hướng GPS thông thường]
    MarkerFound -->|Có| CalcOffset[Tính toán Tọa độ Tâm Marker & Sai số Offset X, Y, Z]

    CalcOffset --> CheckThreshold{Sai số Offset < Ngưỡng cho phép?}
    CheckThreshold -->|Còn lệch| SendVelocityCmd[Gửi lệnh MAVLink SET_POSITION_TARGET_LOCAL_NED điều chỉnh vận tốc ngang]
    CheckThreshold -->|Đã căn giữa| SendLandCmd[Gửi lệnh MAVLink LAND hạ cánh thẳng đứng xuống Landing Pad]

    SendVelocityCmd --> ReadFrame
    SendLandCmd --> CheckTouchdown{Pixhawk báo Disarmed / Touchdown?}
    CheckTouchdown -->|Chưa| SendLandCmd
    CheckTouchdown -->|Đã tiếp đất| ReportBackend[Gửi WebSocket Notify: TOUCHDOWN_SUCCESS]

    StandardFlight --> ReadFrame
    ReportBackend --> CameraLoop

    style RPiStart fill:#800020,color:#fff
    style ReportBackend fill:#10b981,color:#fff
```

---

### 7.4. Lưu đồ Thuật toán Quản lý & Gán ô Kho 3x3 (Inventory QR Vision Slot Allocation)

```mermaid
flowchart TD
    InvStart([📦 KHỞI ĐỘNG INVENTORY MANAGER]) --> ScanQR[Camera quét mã QR trên Hàng hóa nhập kho]
    ScanQR --> ExtractPayload[Trích xuất QR Payload: product_id, sender, address]
    ExtractPayload --> QueryDB{Kiểm tra Sản phẩm trong CSDL?}

    QueryDB -->|Đã tồn tại| CheckStatus[Đọc trạng thái hiện tại của Product]
    QueryDB -->|Mới| CreateProduct[Tạo mới bản ghi Product trong DB]

    CreateProduct --> FindSlot[Duyệt ma trận 9 ô storage_slots A1..C3]
    CheckStatus --> FindSlot

    FindSlot --> CheckEmptySlot{Tìm thấy ô có is_empty = True?}
    CheckEmptySlot -->|Không có ô trống| ReturnFullError[Trả về Lỗi: WAREHOUSE_FULL]
    CheckEmptySlot -->|Tìm thấy ô slot_name| AssignSlot[Gán sản phẩm vào ô slot_name & đổi status = RESERVED / OCCUPIED]

    AssignSlot --> UpdateDB[Cập nhật SQLite DB & Phát WebSocket Broadcast /ws/system]
    UpdateDB --> InvDone([✅ GÁN Ô KHO THÀNH CÔNG])

    ReturnFullError --> InvFail([❌ GÁN Ô THẤT BẠI])

    style InvStart fill:#f59e0b,color:#fff
    style InvDone fill:#10b981,color:#fff
    style InvFail fill:#ef4444,color:#fff
```

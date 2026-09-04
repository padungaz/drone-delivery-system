-- =========================================================================
-- FAIRINO FR3 INDUSTRIAL WAREHOUSE ROBOT CONTROLLER  v2.0
-- Firmware: V3.9.21 / FR3 V6.0 | Port: 8090 / 9100
-- Quản lý: Kho 6 Ô Hoạt Động (A1 -> B3) + 3 Ô Dự Phòng (C1..C3), Trạm Drone (N1), Đầu Băng Tải (O1) & Vị trí HOME
-- =========================================================================
-- 
-- 🔌 BẢNG ÁNH XẠ I/O PHẦN CỨNG GIỮA ROBOT & PLC SIEMENS S7-1200:
-- -------------------------------------------------------------------------
-- [DI - INPUT TỪ PLC VÀO ROBOT]:
--   DI0: Lệnh từ PLC yêu cầu Robot về vị trí HOME an toàn.
--   DI1: Tín hiệu từ PLC báo vị trí đầu Băng tải O1 ĐANG TRỐNG -> Sẵn sàng để Robot lấy hàng và thả xuống O1.
--   DI2: Tín hiệu từ PLC báo vị trí đầu Băng tải O1 ĐANG CÓ HÀNG -> Sẵn sàng để Robot gắp hàng và cất vào Kho.
--
-- [DO - OUTPUT TỪ ROBOT SANG PLC & THIẾT BỊ]:
--   DO0: Tín hiệu từ Robot xác nhận đã về vị trí HOME thành công (HOME OK).
--   DO1: Xung báo Robot đã THẢ HÀNG XUỐNG O1 xong -> PLC chạy băng tải đưa hàng ra cho Nhân viên & đếm số lượng.
--   DO2: Xung báo Robot đã CẤT HÀNG VÀO Ô KHO xong (Inbound Store Complete) -> PLC đếm số lượng nạp.
-- =========================================================================
--
-- ⚠️  GHI CHÚ ĐẤU DÂY PHẦN CỨNG (QUAN TRỌNG):
--   Ngõ ra DO của Robot Fairino FR3 là dạng NPN (Sinking).
--   Ngõ vào DI của PLC Siemens S7-1200 đấu theo kiểu Source (+24VDC chung 1M).
--   Do đó LOGIC BỊ ĐẢO NGƯỢC so với kỳ vọng lập trình:
--     - SetDO(pin, 0) -> NPN dẫn, kéo GND -> Dòng chạy qua optocoupler -> PLC LED SÁNG (PLC đọc = 1)
--     - SetDO(pin, 1) -> NPN khoá, hở mạch  -> Không có dòng           -> PLC LED TẮT  (PLC đọc = 0)
--   => Dùng hàm SafeSetDO() để tự động bù đảo mức, KHÔNG gọi SetDO() trực tiếp.
-- =========================================================================
--
-- ⚠️  GHI CHÚ QUỸ ĐẠO CHUYỂN ĐỘNG (PICK / PLACE TRAJECTORIES):
--   Mỗi ô kho có quỹ đạo GẮP (Pick) và THẢ (Place) RIÊNG BIỆT,
--   được tuỳ biến theo kết cấu cơ khí thực tế (xà gồ, chân kệ, cáp điện...).
--   Mỗi quỹ đạo bao gồm chuỗi điểm trung gian tuỳ ý (HOME_A, A1_P1, A1_P2, ...)
--   và hỗ trợ offset 10 tham số PTP(point, spd, ovl, blend, dx, dy, dz, rx, ry, rz).
--
--   Cấu trúc hàm:
--     PickFromSlot(slot)  : Quỹ đạo vào GẮP hàng tại ô -> rút ra an toàn
--     PlaceToSlot(slot)   : Quỹ đạo vào THẢ hàng tại ô -> rút ra an toàn
--
--   Các điểm cần teach trên Controller (tuỳ biến mỗi ô):
--     HOME_A, HOME_B                 (điểm an toàn tầng A/B)
--     A1_P1, A1_P2, ..., B3_P1, ...  (điểm tránh vật cản, tuỳ cơ khí)
--     HOME_N1, HOME_O1               (điểm an toàn trạm drone / băng tải)
--     A1..B3, N1, O1                 (toạ độ tâm ô gốc hoạt động; C1..C3 là ô tượng trưng/dự phòng)
--
--   Luồng OUTBOUND: PickFromSlot(slot) -> HOME -> PlaceToSlot("O1") -> HOME -> DO1
--   Luồng INBOUND:  PickFromSlot("O1") -> HOME -> PlaceToSlot(slot) -> HOME -> DO2
-- =========================================================================

-- Cấu hình Socket ID (0 hoặc 1 tùy cổng trên Controller Fairino)
local socket_id = 1

-- =========================================================================
-- 1. QUẢN LÝ MÁY TRẠNG THÁI (STATE MACHINE)
-- =========================================================================
local ROBOT_STATE    = "IDLE"    -- "IDLE", "WAITING_SLOT", "MOVING", "ERROR", "ESTOP"
local CURRENT_POS    = "HOME"    -- Lưu vị trí hiện tại của Robot
local STOP_REQUESTED = false     -- Cờ yêu cầu dừng khẩn cấp

-- Cờ chờ Backend chỉ định ô (non-blocking, thay thế SocketReceive timeout 3000ms)
-- Giá trị: nil | "OUTBOUND" | "INBOUND"
local PENDING_OPERATION = nil

print("==================================================")
print("🚀 FAIRINO Robot Warehouse Controller v2.0")
print("📍 Active Points: A1..B3, N1 (Dock), O1 (Conveyor), HOME (C1..C3 Reserved)")
print("📍 Approach Points: HOME_A1..HOME_C3, HOME_N1, HOME_O1")
print("⚡ Hardware I/O (NPN/Active-Low): DI0/DO0 (Home), DI1 (O1 Empty), DI2 (O1 Has Item)")
print("⚡ Output Pulses: DO1 (Outbound Done), DO2 (Inbound Done)")
print("🔧 SafeSetDO: Logic inverted for NPN->Source PLC wiring")
print("🔄 Non-blocking socket: PENDING_OPERATION state machine active")
print("==================================================")

-- =========================================================================
-- 2. HÀM BỌC DO AN TOÀN (ĐẢO MỨC LOGIC NPN -> SOURCE PLC)
-- =========================================================================
-- SafeSetDO(pin, logic_state):
--   logic_state = 1  => Kỳ vọng PLC đọc = 1 (LED sáng) => Gửi hw_val = 0 (NPN dẫn, kéo GND)
--   logic_state = 0  => Kỳ vọng PLC đọc = 0 (LED tắt)  => Gửi hw_val = 1 (NPN khoá, hở mạch)
function SafeSetDO(pin, logic_state)
    local hw_val = (logic_state == 1) and 0 or 1
    SetDO(pin, hw_val, 0, 0)
end

-- Khởi tạo: Robot chưa về HOME -> DO0 logic=0 (Chờ lệnh Home từ PLC)
SafeSetDO(0, 0)   -- DO0 = Logic 0 (Chưa Home OK)
SafeSetDO(1, 0)   -- DO1 = Logic 0 (không xung)
SafeSetDO(2, 0)   -- DO2 = Logic 0 (không xung)

-- =========================================================================
-- 3. CÁC HÀM ĐIỀU KHIỂN CHUYỂN ĐỘNG & THIẾT BỊ
-- =========================================================================

-- Kích xung báo PLC đã đặt hàng tại O1 xong (DO1) -> PLC chạy băng tải
function PulseOutboundO1CompleteToPLC()
    print("⚡ Pulse DO1 -> PLC: Robot đã hoàn tất O1 -> PLC chạy băng tải & đếm số lượng")
    SafeSetDO(1, 1)    -- Logic 1: xung lên
    sleep_ms(250)
    SafeSetDO(1, 0)    -- Logic 0: trả về mức nghỉ
end

-- Kích xung báo PLC đã cất hàng vào kho xong (DO2) -> PLC xác nhận hoàn thành Inbound
function PulseInboundStoreCompleteToPLC(slot)
    print("⚡ Pulse DO2 -> PLC: Robot đã hoàn tất cất vào kho [" .. tostring(slot) .. "] -> PLC đếm nạp")
    SafeSetDO(2, 1)    -- Logic 1: xung lên
    sleep_ms(300)
    SafeSetDO(2, 0)    -- Logic 0: trả về mức nghỉ
end

-- Dừng khẩn cấp / Hủy chu trình chuyển động
function Execute_Stop()
    print("🛑 EMERGENCY STOP TRIGGERED")
    STOP_REQUESTED    = true
    ROBOT_STATE       = "ESTOP"
    PENDING_OPERATION = nil
    StopMotion()
    SafeSetDO(0, 0)   -- Xóa HOME OK
    SafeSetDO(1, 0)   -- Tắt xung DO1
    SafeSetDO(2, 0)   -- Tắt xung DO2
    sleep_ms(100)
    return true
end

-- Reset trạng thái sau E-Stop / Lỗi
function Execute_ResetFault()
    print("🔄 Resetting Robot Fault / E-Stop...")
    STOP_REQUESTED    = false
    PENDING_OPERATION = nil
    ROBOT_STATE       = "IDLE"
    return true
end

-- =========================================================================
-- 3A. QUỸ ĐẠO GẮP HÀNG TẠI Ô CHỈ ĐỊNH (PickFromSlot)
-- =========================================================================
-- Mỗi ô kho có quỹ đạo GẮP riêng biệt, tuỳ biến theo kết cấu cơ khí.
-- Chuỗi điểm trung gian (HOME_A, A1_P1, A1_P2, ...) và offset PTP 10 tham số
-- được điều chỉnh thực tế trên hiện trường cho từng ô.
--
-- ⚠️ QUY ƯỚC OFFSET KHI GẮP:
--   PTP(Ax, spd, -1, 1, -50, 0, 0, 0, 0, 0)  -> Tiếp cận LÙI 50mm trước miệng ô
--   PTP(Ax, spd, -1, 0)                        -> Tiến vào tâm ô (gắp)
--   PTP(Ax, spd, -1, 1, -50, 0, 0, 0, 0, 0)  -> Rút lùi thẳng ra 50mm (đang giữ hàng)
--
-- Hàm trả về true nếu thành công, false nếu slot không hợp lệ hoặc bị STOP.
function PickFromSlot(slot)
    if slot == "DOCK" or slot == "PAD" or slot == "PAD_N1" then slot = "N1" end
    if slot == "CONVEYOR" or slot == "BANG_TAI" or slot == "O_1" then slot = "O1" end

    ROBOT_STATE = "MOVING"
    SafeSetDO(0, 0)
    print("📍 [PICK] Bat dau quy dao GAP hang tai -> " .. slot)

    if slot == "A1" then
        PTP(HOME_A, 25, -1, 0)
        PTP(A1_P1, 30, -1, 0)
        PTP(A1_P2, 30, -1, 0)
        PTP(A1, 30, -1, 1, -50, 0, 0, 0, 0, 0)   -- Tiep can truoc mieng o 50mm
        PTP(A1, 20, -1, 0)                         -- Tien vao tam o (gap)
        sleep_ms(300)
        -- (Thao tac dong kep neu co)
        PTP(A1, 25, -1, 1, -50, 0, 0, 0, 0, 0)   -- Rut lui thang ra 50mm
        PTP(A1_P2, 30, -1, 0)
        PTP(HOME_A, 25, -1, 0)

    elseif slot == "A2" then
        PTP(HOME_A, 25, -1, 0)
        PTP(A2, 30, -1, 1, -50, 0, 0, 0, 0, 0)
        PTP(A2, 20, -1, 0)
        sleep_ms(300)
        PTP(A2, 25, -1, 1, -50, 0, 0, 0, 0, 0)
        PTP(HOME_A, 25, -1, 0)

    elseif slot == "A3" then
        PTP(HOME_A, 25, -1, 0)
        PTP(A3, 30, -1, 1, -50, 0, 0, 0, 0, 0)
        PTP(A3, 20, -1, 0)
        sleep_ms(300)
        PTP(A3, 25, -1, 1, -50, 0, 0, 0, 0, 0)
        PTP(HOME_A, 25, -1, 0)

    elseif slot == "B1" then
        PTP(HOME_B, 25, -1, 0)
        PTP(B1, 30, -1, 1, -50, 0, 0, 0, 0, 0)
        PTP(B1, 20, -1, 0)
        sleep_ms(300)
        PTP(B1, 25, -1, 1, -50, 0, 0, 0, 0, 0)
        PTP(HOME_B, 25, -1, 0)

    elseif slot == "B2" then
        PTP(HOME_B, 25, -1, 0)
        PTP(B2, 30, -1, 1, -50, 0, 0, 0, 0, 0)
        PTP(B2, 20, -1, 0)
        sleep_ms(300)
        PTP(B2, 25, -1, 1, -50, 0, 0, 0, 0, 0)
        PTP(HOME_B, 25, -1, 0)

    elseif slot == "B3" then
        PTP(HOME_B, 25, -1, 0)
        PTP(B3, 30, -1, 1, -50, 0, 0, 0, 0, 0)
        PTP(B3, 20, -1, 0)
        sleep_ms(300)
        PTP(B3, 25, -1, 1, -50, 0, 0, 0, 0, 0)
        PTP(HOME_B, 25, -1, 0)

    elseif slot == "C1" or slot == "C2" or slot == "C3" then
        print("⚠️ [PICK] O kho " .. tostring(slot) .. " la o du phong (Khong teach toa do)!")
        ROBOT_STATE = "IDLE"
        return false

    elseif slot == "N1" then
        PTP(HOME_N1, 25, -1, 0)
        PTP(N1, 30, -1, 1, -50, 0, 0, 0, 0, 0)
        PTP(N1, 20, -1, 0)
        sleep_ms(300)
        PTP(N1, 25, -1, 1, -50, 0, 0, 0, 0, 0)
        PTP(HOME_N1, 25, -1, 0)

    elseif slot == "O1" then
        PTP(HOME_O1, 25, -1, 0)
        PTP(O1, 30, -1, 1, -50, 0, 0, 0, 0, 0)
        PTP(O1, 20, -1, 0)
        sleep_ms(300)
        PTP(O1, 25, -1, 1, -50, 0, 0, 0, 0, 0)
        -- Đã gắp xong tại O1, nhấc lên thoát mặt băng tải, sẵn sàng quét QR hoặc nâng Z

    else
        print("❌ [PICK] Slot khong hop le: " .. tostring(slot))
        ROBOT_STATE = "IDLE"
        return false
    end

    if STOP_REQUESTED then return false end
    CURRENT_POS = slot
    ROBOT_STATE = "IDLE"
    print("✅ [PICK] Hoan tat gap hang tai o: " .. slot)
    return true
end

-- =========================================================================
-- 3B. QUỸ ĐẠO THẢ HÀNG TẠI Ô CHỈ ĐỊNH (PlaceToSlot)
-- =========================================================================
-- Mỗi ô kho có quỹ đạo THẢ riêng biệt.
-- Offset khi thả thường NGƯỢC CHIỀU so với khi gắp (nhấc lên thay vì lùi ra)
-- để tránh quẹt hàng vừa đặt xuống.
--
-- ⚠️ QUY ƯỚC OFFSET KHI THẢ:
--   PTP(Ax, spd, -1, 1, 50, 0, 0, 0, 0, 0)   -> Tiếp cận NÂNG 50mm phía trên ô
--   PTP(Ax, spd, -1, 0)                        -> Hạ xuống tâm ô (thả)
--   PTP(Ax, spd, -1, 1, 50, 0, 0, 0, 0, 0)   -> Nhấc lên 50mm tránh quẹt hàng
function PlaceToSlot(slot)
    if slot == "DOCK" or slot == "PAD" or slot == "PAD_N1" then slot = "N1" end
    if slot == "CONVEYOR" or slot == "BANG_TAI" or slot == "O_1" then slot = "O1" end

    ROBOT_STATE = "MOVING"
    SafeSetDO(0, 0)
    print("📍 [PLACE] Bat dau quy dao THA hang tai -> " .. slot)

    if slot == "A1" then
        PTP(HOME_A, 25, -1, 0)
        PTP(A1_P1, 30, -1, 0)
        PTP(A1_P2, 30, -1, 0)
        PTP(A1, 30, -1, 1, 50, 0, 0, 0, 0, 0)    -- Tiep can nang 50mm phia tren
        PTP(A1, 20, -1, 0)                         -- Ha xuong tam o (tha)
        sleep_ms(300)
        -- (Thao tac nha kep neu co)
        PTP(A1, 25, -1, 1, 50, 0, 0, 0, 0, 0)    -- Nhac len 50mm tranh quet hang
        PTP(A1_P2, 30, -1, 0)
        PTP(HOME_A, 25, -1, 0)

    elseif slot == "A2" then
        PTP(HOME_A, 25, -1, 0)
        PTP(A2, 30, -1, 1, 50, 0, 0, 0, 0, 0)
        PTP(A2, 20, -1, 0)
        sleep_ms(300)
        PTP(A2, 25, -1, 1, 50, 0, 0, 0, 0, 0)
        PTP(HOME_A, 25, -1, 0)

    elseif slot == "A3" then
        PTP(HOME_A, 25, -1, 0)
        PTP(A3, 30, -1, 1, 50, 0, 0, 0, 0, 0)
        PTP(A3, 20, -1, 0)
        sleep_ms(300)
        PTP(A3, 25, -1, 1, 50, 0, 0, 0, 0, 0)
        PTP(HOME_A, 25, -1, 0)

    elseif slot == "B1" then
        PTP(HOME_B, 25, -1, 0)
        PTP(B1, 30, -1, 1, 50, 0, 0, 0, 0, 0)
        PTP(B1, 20, -1, 0)
        sleep_ms(300)
        PTP(B1, 25, -1, 1, 50, 0, 0, 0, 0, 0)
        PTP(HOME_B, 25, -1, 0)

    elseif slot == "B2" then
        PTP(HOME_B, 25, -1, 0)
        PTP(B2, 30, -1, 1, 50, 0, 0, 0, 0, 0)
        PTP(B2, 20, -1, 0)
        sleep_ms(300)
        PTP(B2, 25, -1, 1, 50, 0, 0, 0, 0, 0)
        PTP(HOME_B, 25, -1, 0)

    elseif slot == "B3" then
        PTP(HOME_B, 25, -1, 0)
        PTP(B3, 30, -1, 1, 50, 0, 0, 0, 0, 0)
        PTP(B3, 20, -1, 0)
        sleep_ms(300)
        PTP(B3, 25, -1, 1, 50, 0, 0, 0, 0, 0)
        PTP(HOME_B, 25, -1, 0)

    elseif slot == "C1" or slot == "C2" or slot == "C3" then
        print("⚠️ [PLACE] O kho " .. tostring(slot) .. " la o du phong (Khong teach toa do)!")
        ROBOT_STATE = "IDLE"
        return false

    elseif slot == "N1" then
        PTP(HOME_N1, 25, -1, 0)
        PTP(N1, 30, -1, 1, 50, 0, 0, 0, 0, 0)
        PTP(N1, 20, -1, 0)
        sleep_ms(300)
        PTP(N1, 25, -1, 1, 50, 0, 0, 0, 0, 0)
        PTP(HOME_N1, 25, -1, 0)

    elseif slot == "O1" then
        PTP(HOME_O1, 25, -1, 0)
        PTP(O1, 30, -1, 1, 50, 0, 0, 0, 0, 0)
        PTP(O1, 20, -1, 0)
        sleep_ms(300)
        PTP(O1, 25, -1, 1, 50, 0, 0, 0, 0, 0)
        PTP(HOME_O1, 25, -1, 0)

    else
        print("❌ [PLACE] Slot khong hop le: " .. tostring(slot))
        ROBOT_STATE = "IDLE"
        return false
    end

    if STOP_REQUESTED then return false end
    CURRENT_POS = slot
    ROBOT_STATE = "IDLE"
    print("✅ [PLACE] Hoan tat tha hang tai o: " .. slot)
    return true
end

-- =========================================================================
-- 3C. DI CHUYỂN VỀ VỊ TRÍ HOME AN TOÀN
-- =========================================================================
-- Gọi SAU KHI PickFromSlot / PlaceToSlot đã rút tay ra vị trí an toàn
-- (HOME_A / HOME_B / HOME_C / HOME_N1 / HOME_O1).
-- Từ vùng thoáng, đi qua p1,p2,p3 về HOME một cách thẳng thớm.
function Execute_MoveHome()
    if ROBOT_STATE ~= "IDLE" and ROBOT_STATE ~= "MOVING"
       and ROBOT_STATE ~= "ESTOP" and ROBOT_STATE ~= "WAITING_SLOT" then
        return false
    end
    ROBOT_STATE    = "MOVING"
    STOP_REQUESTED = false
    SafeSetDO(0, 0)   -- Xóa cờ HOME OK trong khi di chuyển
    print("🏠 [HOME] Di chuyen ve vi tri HOME...")
    PTP(P1, 25, -1, 0)
    PTP(P2, 25, -1, 0)
    PTP(P3, 25, -1, 0)
    PTP(HOME, 25, -1, 0)
    CURRENT_POS = "HOME"
    ROBOT_STATE = "IDLE"
    SafeSetDO(0, 1)   -- Logic 1 -> PLC xác nhận HOME OK
    print("✅ [HOME] Robot tai HOME -> DO0 logic=1 (HOME OK)")
    return true
end

-- =========================================================================
-- 4. ĐIỀU PHỐI CHU TRÌNH PHỐI HỢP TRỤC Z ĐA TẦNG CỦA PLC
-- =========================================================================
-- ⚠️ NGUYÊN TẮC AN TOÀN TUYỆT ĐỐI:
-- Hệ thống sử dụng Trục Z nâng hạ nhiều tầng do PLC Siemens S7-1200 điều khiển.
-- Robot KHÔNG tự ý chạy chu trình gắp và thả liên tục (đã loại bỏ Outbound/Inbound cycle cũ)
-- để tránh va chạm cơ khí khi trục Z chưa đến đúng tầng.
--
-- Backend điều phối từng bước nguyên tử qua Socket TCP:
--   - OUTBOUND: PLC nâng Z lên tầng -> Robot: PICK <slot> -> PLC hạ Z xuống O1 -> Robot: STORE O1 (kích DO1)
--   - INBOUND:  PLC hạ Z xuống O1 -> Robot: PICK O1 -> Quét QR -> PLC nâng Z lên tầng -> Robot: STORE <slot> (kích DO2)
-- =========================================================================

-- =========================================================================
-- 5. BỘ TÁCH LỆNH CHUẨN (PATTERN PARSER NÂNG CAO)
-- =========================================================================
function ParseCommand(raw_data)
    if not raw_data or raw_data == "" then
        return "", "", ""
    end
    local clean_data = string.gsub(raw_data, "[%r%n]", "")
    clean_data = string.match(clean_data, "^%s*(.-)%s*$") or ""
    local cmd, param = string.match(clean_data, "^(%S+)%s*(%S*)$")
    cmd   = cmd   and string.upper(cmd)   or ""
    param = param and string.upper(param) or ""
    return cmd, param, clean_data
end

-- =========================================================================
-- 6. VÒNG LẶP NHẬN & PHÂN PHỐI LỆNH (HARDWARE I/O + SOCKET BACKEND)
-- =========================================================================
-- Kiến trúc NON-BLOCKING cho DI1/DI2:
--   - Khi DI1/DI2 kích hoạt, Robot gửi REQUEST và set PENDING_OPERATION (không block).
--   - Backend duy trì Persistent TCP Connection, phản hồi PICK/STORE <slot> bất cứ lúc nào.
--   - Section D đọc socket 100ms mỗi chu kỳ, dispatch lệnh phản hồi vào đúng handler.

-- Biến lưu trạng thái DI chu kỳ trước để bắt sườn lên (Rising Edge Detection)
local prev_di0 = 0
local prev_di1 = 0
local prev_di2 = 0

while true do
    -- Đọc trạng thái hiện tại của các chân Input từ PLC
    local current_di0 = GetDI(0, 0)
    local current_di1 = GetDI(1, 0)
    local current_di2 = GetDI(2, 0)

    -- =========================================================
    -- A. XỬ LÝ DI0: PLC yêu cầu về Home (Sườn lên)
    -- =========================================================
    if current_di0 == 1 and prev_di0 == 0 then
        if ROBOT_STATE == "IDLE" or ROBOT_STATE == "ESTOP" or ROBOT_STATE == "WAITING_SLOT" then
            print("⚡ DI0 = 1 (Sườn lên): PLC yeu cau Robot ve HOME an toan -> Execute_MoveHome()")
            PENDING_OPERATION = nil  -- Hủy yêu cầu đang chờ nếu có
            Execute_MoveHome()
        else
            print("⚠️ DI0 = 1 nhung Robot dang ban: " .. ROBOT_STATE)
        end
    end

    -- =========================================================
    -- B. XỬ LÝ DI1: PLC báo O1 TRỐNG -> NON-BLOCKING REQUEST
    -- =========================================================
    -- Bước 2 & 3: PLC kích DI1 = 1 -> Robot gửi ROBOT_READY về Backend
    if current_di1 == 1 and prev_di1 == 0 then
        if ROBOT_STATE == "IDLE" or ROBOT_STATE == "WAITING_SLOT" then
            print("⚡ Sườn lên DI1 = 1 (PLC sẵn sàng lấy hàng): Gửi ROBOT_READY về Backend...")
            PENDING_OPERATION = "OUTBOUND"
            ROBOT_STATE = "WAITING_SLOT"
            SocketSend(socket_id, "ROBOT_READY\n", 0)
            print("📤 Đã gửi ROBOT_READY -> Chờ Backend điều phối ô cần lấy...")
        else
            print(string.format("⚠️ DI1 kích hoạt nhưng Robot đang bận: %s (Pos: %s)", ROBOT_STATE, CURRENT_POS))
        end
    end

    -- =========================================================
    -- C. XỬ LÝ DI2: PLC báo O1 CÓ HÀNG -> NON-BLOCKING REQUEST
    -- =========================================================
    -- Bước 2 & 3: Cảm biến O1 có hàng -> PLC kích DI2 = 1 -> Robot gửi ROBOT_INBOUND_READY về Backend
    if current_di2 == 1 and prev_di2 == 0 then
        if ROBOT_STATE == "IDLE" or ROBOT_STATE == "WAITING_SLOT" then
            print("⚡ Sườn lên DI2 = 1 (PLC báo O1 CÓ HÀNG): Gửi ROBOT_INBOUND_READY về Backend...")
            PENDING_OPERATION = "INBOUND"
            ROBOT_STATE = "WAITING_SLOT"
            SocketSend(socket_id, "ROBOT_INBOUND_READY\n", 0)
            print("📤 Đã gửi ROBOT_INBOUND_READY -> Chờ Backend phân bổ ô và điều phối...")
        else
            print(string.format("⚠️ DI2 kích hoạt nhưng Robot đang bận (State: %s, Pos: %s)", ROBOT_STATE, CURRENT_POS))
        end
    end

    -- Cập nhật giá trị chu kỳ trước để bắt sườn lên ở vòng lặp sau
    prev_di0 = current_di0
    prev_di1 = current_di1
    prev_di2 = current_di2

    -- =========================================================
    -- D. XỬ LÝ LỆNH SOCKET TỪ BACKEND (100ms timeout)
    -- =========================================================
    local recv_time, recv_data = SocketReceive(socket_id, 100, 1)
    if recv_data and recv_data ~= "" then
        print("📥 RX: " .. recv_data)
        local cmd, param, raw = ParseCommand(recv_data)

        -- D.1: Phản hồi khi Backend báo HỦY thao tác / không có ô khả dụng (Kho đầy / hết đơn)
        if (cmd == "CANCEL" or cmd == "ABORT" or cmd == "NONE" or cmd == "NO_SLOT" or cmd == "FULL") then
            print("🛑 Backend báo HỦY thao tác / không có ô khả dụng: " .. tostring(cmd))
            PENDING_OPERATION = nil
            ROBOT_STATE = "IDLE"
            SocketSend(socket_id, "SUCCESS CANCEL STATE:IDLE\n", 0)

        -- D.2: Lệnh gắp hàng (PICK / PICK_PRODUCT / Lệnh SLOT khi đang chờ Outbound)
        elseif cmd == "PICK" or cmd == "PICK_PRODUCT" or (cmd == "SLOT" and PENDING_OPERATION == "OUTBOUND") then
            -- Cho phép thực thi khi Robot IDLE hoặc đang ở trạng thái WAITING_SLOT (khi DI1/DI2 vừa kích hoạt)
            if ROBOT_STATE ~= "IDLE" and ROBOT_STATE ~= "WAITING_SLOT" then
                SocketSend(socket_id, "BUSY STATE:" .. ROBOT_STATE .. " POSITION:" .. CURRENT_POS .. "\n", 0)
            else
                PENDING_OPERATION = nil
                if PickFromSlot(param) then
                    SocketSend(socket_id, "SUCCESS PICK " .. param .. "\n", 0)
                else
                    SocketSend(socket_id, "FAILED PICK " .. param .. "\n", 0)
                end
            end

        -- D.3: Lệnh thả / cất hàng (STORE / PLACE_PRODUCT / Lệnh SLOT khi đang chờ Inbound)
        elseif cmd == "STORE" or cmd == "PLACE_PRODUCT" or (cmd == "SLOT" and PENDING_OPERATION == "INBOUND") then
            if ROBOT_STATE ~= "IDLE" and ROBOT_STATE ~= "WAITING_SLOT" then
                SocketSend(socket_id, "BUSY STATE:" .. ROBOT_STATE .. " POSITION:" .. CURRENT_POS .. "\n", 0)
            else
                PENDING_OPERATION = nil
                if PlaceToSlot(param) then
                    if param == "O1" then
                        -- Thả xong tại O1 -> Kích xung DO1 báo PLC chạy băng tải đưa hàng ra
                        PulseOutboundO1CompleteToPLC()
                    elseif param ~= "N1" then
                        -- Cất xong vào ô kho (A1..B3) -> Kích xung DO2 báo PLC xác nhận Inbound
                        PulseInboundStoreCompleteToPLC(param)
                    end
                    SocketSend(socket_id, "SUCCESS STORE " .. param .. "\n", 0)
                else
                    SocketSend(socket_id, "FAILED STORE " .. param .. "\n", 0)
                end
            end

        -- D.4: Lệnh hỏi trạng thái Robot
        elseif cmd == "STATUS" or cmd == "GET_STATUS" then
            local is_busy = (ROBOT_STATE ~= "IDLE" and ROBOT_STATE ~= "WAITING_SLOT") and "TRUE" or "FALSE"
            local pend    = PENDING_OPERATION or "NONE"
            local status_resp = string.format("STATE:%s BUSY:%s POSITION:%s PENDING:%s\n",
                                              ROBOT_STATE, is_busy, CURRENT_POS, pend)
            SocketSend(socket_id, status_resp, 0)

        -- D.5: Lệnh dừng khẩn cấp (STOP / ESTOP)
        elseif cmd == "STOP" or cmd == "ESTOP" then
            Execute_Stop()
            SocketSend(socket_id, "STOP SUCCESS STATE:ESTOP\n", 0)

        -- D.6: Lệnh reset trạng thái sau sự cố
        elseif cmd == "RESET" or cmd == "RESET_ESTOP" or cmd == "CLEAR_FAULT" then
            Execute_ResetFault()
            SocketSend(socket_id, "RESET SUCCESS STATE:IDLE\n", 0)

        -- D.7: Lệnh di chuyển về vị trí HOME an toàn
        elseif cmd == "MOVE_HOME" or cmd == "REQUEST_Z_DOWN" then
            if ROBOT_STATE ~= "IDLE" and ROBOT_STATE ~= "ESTOP" and ROBOT_STATE ~= "WAITING_SLOT" then
                SocketSend(socket_id, "BUSY STATE:" .. ROBOT_STATE .. " POSITION:" .. CURRENT_POS .. "\n", 0)
            else
                PENDING_OPERATION = nil
                if Execute_MoveHome() then
                    SocketSend(socket_id, "SUCCESS MOVE_HOME\n", 0)
                else
                    SocketSend(socket_id, "FAILED MOVE_HOME\n", 0)
                end
            end

        -- D.8: Phản hồi lệnh tay kẹp (GRIPPER)
        elseif cmd == "GRIPPER_OPEN" or cmd == "OPEN_GRIPPER" or cmd == "GRIPPER_CLOSE" or cmd == "CLOSE_GRIPPER" then
            SocketSend(socket_id, "SUCCESS " .. cmd .. "\n", 0)

        else
            print("⚠️ Lệnh không xác định: " .. tostring(cmd))
            SocketSend(socket_id, "UNKNOWN COMMAND\n", 0)
        end
    end
    sleep_ms(50)
end

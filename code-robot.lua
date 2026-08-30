-- =========================================================================
-- FAIRINO FR3 INDUSTRIAL WAREHOUSE ROBOT CONTROLLER  v2.0
-- Firmware: V3.9.21 / FR3 V6.0 | Port: 8090 / 9100
-- Quản lý: Kho 3x3 (A1 -> C3), Trạm Drone (N1), Đầu Băng Tải (O1) & Vị trí HOME
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
-- ⚠️  GHI CHÚ ĐIỂM TRUNG GIAN (APPROACH / RETRACT WAYPOINTS):
--   Mỗi ô kho / trạm có một điểm tiếp cận HOME_xx nằm phía trước cửa ô,
--   cách miệng ô 150~200mm trong không gian thoáng, được teach sẵn trên Controller.
--   Thứ tự di chuyển cho mỗi ô:
--     HOME -> HOME_Ax (tiếp cận, 30%) -> Ax (vào tâm ô, 20%) -> HOME_Ax (rút ra, 25%) -> HOME
--   Các điểm cần teach trên Controller:
--     HOME_A1, HOME_A2, HOME_A3,
--     HOME_B1, HOME_B2, HOME_B3,
--     HOME_C1, HOME_C2, HOME_C3,
--     HOME_N1, HOME_O1
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
print("📍 Points: A1..C3, N1 (Dock), O1 (Conveyor), HOME")
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

-- Khởi tạo: Robot đang ở HOME -> DO0 logic=1 (PLC nhận HOME OK)
SafeSetDO(0, 1)   -- DO0 = Logic 1 (HOME OK)
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
-- 3A. HÀM TIẾP CẬN ĐIỂM TRUNG GIAN TRƯỚC Ô KHO (APPROACH - 30%)
-- =========================================================================
-- Di chuyển từ vị trí hiện tại đến điểm tiếp cận an toàn HOME_xx.
-- HOME_xx nằm phía trước miệng ô kho ~150-200mm trong không gian thoáng.
function MoveToApproach(slot)
    print("   [APPROACH] Di chuyen den diem tiep can -> HOME_" .. slot)
    if slot == "A1" then PTP(HOME_A1, 30, -1, 0)
    elseif slot == "A2" then PTP(HOME_A2, 30, -1, 0)
    elseif slot == "A3" then PTP(HOME_A3, 30, -1, 0)
    elseif slot == "B1" then PTP(HOME_B1, 30, -1, 0)
    elseif slot == "B2" then PTP(HOME_B2, 30, -1, 0)
    elseif slot == "B3" then PTP(HOME_B3, 30, -1, 0)
    elseif slot == "C1" then PTP(HOME_C1, 30, -1, 0)
    elseif slot == "C2" then PTP(HOME_C2, 30, -1, 0)
    elseif slot == "C3" then PTP(HOME_C3, 30, -1, 0)
    elseif slot == "N1" then PTP(HOME_N1, 30, -1, 0)
    elseif slot == "O1" then PTP(HOME_O1, 30, -1, 0)
    else
        print("❌ [APPROACH] Khong tim thay diem tiep can cho slot: " .. tostring(slot))
        return false
    end
    return true
end

-- =========================================================================
-- 3B. HÀM TIẾN VÀO TÂM Ô KHO (ENTER TARGET - 20%, chậm & chính xác)
-- =========================================================================
-- Di chuyển thẳng từ HOME_xx vào đúng tâm ô kho ở tốc độ thấp.
function MoveEnterTarget(slot)
    print("   [ENTER]    Tien vao tam o -> " .. slot .. " (toc do 20%)")
    if slot == "A1" then PTP(A1, 20, -1, 0)
    elseif slot == "A2" then PTP(A2, 20, -1, 0)
    elseif slot == "A3" then PTP(A3, 20, -1, 0)
    elseif slot == "B1" then PTP(B1, 20, -1, 0)
    elseif slot == "B2" then PTP(B2, 20, -1, 0)
    elseif slot == "B3" then PTP(B3, 20, -1, 0)
    elseif slot == "C1" then PTP(C1, 20, -1, 0)
    elseif slot == "C2" then PTP(C2, 20, -1, 0)
    elseif slot == "C3" then PTP(C3, 20, -1, 0)
    elseif slot == "N1" then PTP(N1, 20, -1, 0)
    elseif slot == "O1" then PTP(O1, 20, -1, 0)
    else
        print("❌ [ENTER] Slot khong hop le: " .. tostring(slot))
        return false
    end
    return true
end

-- =========================================================================
-- 3C. HÀM RÚT TAY MÁY RA KHỎI Ô KHO (RETRACT - 25%)
-- =========================================================================
-- Lùi thẳng từ tâm ô kho trở lại HOME_xx theo đúng đường vào.
-- Ngăn cánh tay bẻ góc va vào thành kệ sắt hoặc kiện hàng kế bên.
function MoveRetractFromSlot(slot)
    print("   [RETRACT]  Rut tay may an toan ra -> HOME_" .. slot)
    if slot == "A1" then PTP(HOME_A1, 25, -1, 0)
    elseif slot == "A2" then PTP(HOME_A2, 25, -1, 0)
    elseif slot == "A3" then PTP(HOME_A3, 25, -1, 0)
    elseif slot == "B1" then PTP(HOME_B1, 25, -1, 0)
    elseif slot == "B2" then PTP(HOME_B2, 25, -1, 0)
    elseif slot == "B3" then PTP(HOME_B3, 25, -1, 0)
    elseif slot == "C1" then PTP(HOME_C1, 25, -1, 0)
    elseif slot == "C2" then PTP(HOME_C2, 25, -1, 0)
    elseif slot == "C3" then PTP(HOME_C3, 25, -1, 0)
    elseif slot == "N1" then PTP(HOME_N1, 25, -1, 0)
    elseif slot == "O1" then PTP(HOME_O1, 25, -1, 0)
    else
        print("❌ [RETRACT] Slot khong hop le: " .. tostring(slot))
        return false
    end
    return true
end

-- =========================================================================
-- 3D. DI CHUYỂN TỚI VỊ TRÍ CHỈ ĐỊNH - CHU TRÌNH 4 PHA AN TOÀN
-- =========================================================================
-- Pha 1 (APPROACH): Di chuyển đến HOME_slot (không gian thoáng, 30%)
-- Pha 2 (ENTER):    Tiến vào tâm ô slot (tốc độ thấp 20%, chính xác)
-- Pha 3 (WAIT):     Dừng ổn định 500ms tại tâm ô (thao tác gripper nếu có)
-- Pha 4 (RETRACT):  Rút thẳng ra HOME_slot (không bẻ góc, 25%)
function MoveToSlotAndAct(slot)
    if slot == "DOCK" or slot == "PAD" or slot == "PAD_N1" then slot = "N1" end
    if slot == "CONVEYOR" or slot == "BANG_TAI" or slot == "O_1" then slot = "O1" end

    ROBOT_STATE = "MOVING"
    SafeSetDO(0, 0)   -- Xóa cờ HOME OK trong khi di chuyển
    print("📍 [MOVE] Bat dau chu trinh 4 pha -> " .. slot)

    -- Kiểm tra slot hợp lệ sớm
    if slot ~= "A1" and slot ~= "A2" and slot ~= "A3"
       and slot ~= "B1" and slot ~= "B2" and slot ~= "B3"
       and slot ~= "C1" and slot ~= "C2" and slot ~= "C3"
       and slot ~= "N1" and slot ~= "O1" then
        print("❌ [MOVE] Slot khong hop le: " .. tostring(slot))
        ROBOT_STATE = "ERROR"
        sleep_ms(100)
        ROBOT_STATE = "IDLE"
        return false
    end

    -- PHA 1: APPROACH -> di đến điểm tiếp cận HOME_slot
    if not MoveToApproach(slot) then
        ROBOT_STATE = "IDLE"
        return false
    end
    if STOP_REQUESTED then return false end

    -- PHA 2: ENTER -> tiến thẳng vào tâm ô, tốc độ thấp
    if not MoveEnterTarget(slot) then
        ROBOT_STATE = "IDLE"
        return false
    end
    if STOP_REQUESTED then return false end

    -- PHA 3: WAIT -> dừng ổn định (gripper action được thực hiện ở đây)
    sleep_ms(500)

    -- PHA 4: RETRACT -> rút thẳng ra HOME_slot (theo đúng đường vào)
    if not MoveRetractFromSlot(slot) then
        ROBOT_STATE = "IDLE"
        return false
    end
    if STOP_REQUESTED then return false end

    CURRENT_POS = slot
    ROBOT_STATE = "IDLE"
    print("✅ [MOVE] Hoan tat chu trinh 4 pha tai o: " .. slot)
    return true
end

-- =========================================================================
-- 3E. DI CHUYỂN VỀ VỊ TRÍ HOME AN TOÀN
-- =========================================================================
-- Chú ý: Hàm này gọi SAU KHI MoveToSlotAndAct đã RETRACT xong.
-- Cánh tay đang ở HOME_slot (ngoài thoáng), không còn trong kệ.
-- Chỉ cần đi qua p1,p2,p3 về HOME một cách thẳng thớm.
function Execute_MoveHome()
    if ROBOT_STATE ~= "IDLE" and ROBOT_STATE ~= "MOVING"
       and ROBOT_STATE ~= "ESTOP" and ROBOT_STATE ~= "WAITING_SLOT" then
        return false
    end
    ROBOT_STATE    = "MOVING"
    STOP_REQUESTED = false
    SafeSetDO(0, 0)   -- Xóa cờ HOME OK trong khi di chuyển
    print("🏠 [HOME] Di chuyen ve vi tri HOME...")
    PTP(p1, 25, -1, 0)
    PTP(p2, 25, -1, 0)
    PTP(p3, 25, -1, 0)
    PTP(HOME, 25, -1, 0)
    CURRENT_POS = "HOME"
    ROBOT_STATE = "IDLE"
    SafeSetDO(0, 1)   -- Logic 1 -> PLC xác nhận HOME OK
    print("✅ [HOME] Robot tai HOME -> DO0 logic=1 (HOME OK)")
    return true
end

-- Di chuyển trực tiếp tới vị trí chỉ định bằng lệnh PTP chuẩn 4 tham số (PTP(Point, Speed, -1, 0))
function MoveToSlotAndAct(slot)
    if slot == "DOCK" or slot == "PAD" or slot == "PAD_N1" then slot = "N1" end
    if slot == "CONVEYOR" or slot == "BANG_TAI" or slot == "O_1" then slot = "O1" end

    ROBOT_STATE = "MOVING"
    SetDO(0, 0, 0, 0)
    print("📍 Di chuyển tới vị trí -> " .. slot)

    -- Sử dụng cú pháp PTP 4 tham số chuẩn của Fairino: PTP(point, speed, ovl, blend)
    if slot == "A1" then PTP(A1, 30, -1, 0)
    elseif slot == "A2" then PTP(A2, 30, -1, 0)
    elseif slot == "A3" then PTP(A3, 30, -1, 0)
    elseif slot == "B1" then PTP(B1, 30, -1, 0)
    elseif slot == "B2" then PTP(B2, 30, -1, 0)
    elseif slot == "B3" then PTP(B3, 30, -1, 0)
    elseif slot == "C1" then PTP(C1, 30, -1, 0)
    elseif slot == "C2" then PTP(C2, 30, -1, 0)
    elseif slot == "C3" then PTP(C3, 30, -1, 0)
    elseif slot == "N1" then PTP(N1, 30, -1, 0)
    elseif slot == "O1" then PTP(O1, 30, -1, 0)
    else
        print("❌ Invalid slot: " .. tostring(slot))
        ROBOT_STATE = "ERROR"
        sleep_ms(100)
        ROBOT_STATE = "IDLE"
        return false
    end

    if STOP_REQUESTED then return false end
    WaitMs(2500)

    -- Dừng ổn định vị trí tại đích
    sleep_ms(500)
    CURRENT_POS = slot
    ROBOT_STATE = "IDLE"
    return true
end

-- =========================================================================
-- 4. CHU TRÌNH LẤY HÀNG (OUTBOUND) & THÊM HÀNG (INBOUND) TỰ ĐỘNG
-- =========================================================================

-- Chu trình Lấy hàng: slot -> HOME -> O1 -> HOME -> Kích DO1
function Execute_OutboundCycle(slot)
    print(string.format("🚀 [OUTBOUND] Bắt đầu di chuyển lấy hàng từ ô [%s] ra Băng tải O1...", slot))
    
    -- 1. Di chuyển tới ô chỉ định
    if not MoveToSlotAndAct(slot) then return false end
    
    -- 2. Về vị trí HOME an toàn
    Execute_MoveHome()
    
    -- 3. Di chuyển tới vị trí O1 trên băng tải
    if not MoveToSlotAndAct("O1") then return false end
    
    -- 4. Về vị trí HOME an toàn
    Execute_MoveHome()
    
    -- 5. Kích xung DO1 báo PLC đã hoàn tất vị trí O1 -> PLC chạy băng tải
    PulseOutboundO1CompleteToPLC()
    print(string.format("✅ [OUTBOUND] Hoàn tất chu trình di chuyển ô [%s] ra O1!", slot))
    return true
end

-- Chu trình Thêm hàng: Đi tới O1 -> Về HOME -> Đi tới slot -> Về HOME -> Kích DO2
function Execute_InboundCycle(slot)
    print(string.format("📥 [INBOUND] Bắt đầu di chuyển từ O1 cất vào ô [%s]...", slot))
    
    -- 1. Di chuyển tới vị trí O1 trên băng tải
    if not MoveToSlotAndAct("O1") then return false end
    
    -- 2. Về vị trí HOME an toàn
    Execute_MoveHome()
    
    -- 3. Di chuyển tới ô kho chỉ định
    if not MoveToSlotAndAct(slot) then return false end
    
    -- 4. Về vị trí HOME an toàn
    Execute_MoveHome()
    
    -- 5. Kích xung DO2 báo PLC đã cất vào kho xong
    PulseInboundStoreCompleteToPLC(slot)
    print(string.format("✅ [INBOUND] Hoàn tất chu trình nạp vào ô [%s]!", slot))
    return true
end

-- =========================================================================
-- 5. BỘ TÁCH LỆNH CHUẨN (PATTERN PARSER NÂNG CAO)
-- =========================================================================
function ParseCommand(raw_data)
    if not raw_data or raw_data == "" then
        return "", "", ""
    end
    local clean_data = string.gsub(raw_data, "[%r%n]", "")
    clean_data = string.gsub(clean_data, "\\r", "")
    clean_data = string.gsub(clean_data, "\\n", "")
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
            print("⚡ Suon len DI0 = 1: PLC yeu cau Robot ve HOME an toan")
            PENDING_OPERATION = nil  -- Hủy yêu cầu đang chờ nếu có
            Execute_MoveHome()
        else
            print("⚠️ DI0 kich hoat nhung Robot dang ban: " .. ROBOT_STATE)
        end
    end

    -- =========================================================
    -- B. XỬ LÝ DI1: PLC báo O1 TRỐNG -> NON-BLOCKING REQUEST
    -- =========================================================
    -- Không dùng SocketReceive(3000ms) block nữa.
    -- Chỉ gửi REQUEST và set cờ PENDING_OPERATION = "OUTBOUND".
    -- Section D sẽ nhận phản hồi PICK <slot> từ Backend và thực thi.
    if current_di1 == 1 and prev_di1 == 0 then
        if ROBOT_STATE == "IDLE" and CURRENT_POS == "HOME" then
            print("⚡ Suon len DI1 = 1 (PLC bao O1 TRONG): Gui REQUEST_PICK_SLOT toi Backend...")
            PENDING_OPERATION = "OUTBOUND"
            ROBOT_STATE = "WAITING_SLOT"
            SocketSend(socket_id, "REQUEST_PICK_SLOT\n", 0)
            print("📤 Da gui REQUEST_PICK_SLOT -> cho Backend phan hoi PICK <slot>...")
        else
            print(string.format("⚠️ DI1 kich hoat nhung Robot khong san sang (State: %s, Pos: %s)", ROBOT_STATE, CURRENT_POS))
        end
    end

    -- =========================================================
    -- C. XỬ LÝ DI2: PLC báo O1 CÓ HÀNG -> NON-BLOCKING REQUEST
    -- =========================================================
    if current_di2 == 1 and prev_di2 == 0 then
        if ROBOT_STATE == "IDLE" and CURRENT_POS == "HOME" then
            print("⚡ Suon len DI2 = 1 (PLC bao O1 CO HANG): Gui REQUEST_STORE_SLOT toi Backend...")
            PENDING_OPERATION = "INBOUND"
            ROBOT_STATE = "WAITING_SLOT"
            SocketSend(socket_id, "REQUEST_STORE_SLOT\n", 0)
            print("📤 Da gui REQUEST_STORE_SLOT -> cho Backend phan hoi STORE <slot>...")
        else
            print(string.format("⚠️ DI2 kich hoat nhung Robot khong san sang (State: %s, Pos: %s)", ROBOT_STATE, CURRENT_POS))
        end
    end

    -- Cập nhật giá trị chu kỳ trước để bắt sườn lên ở vòng lặp sau
    prev_di0 = current_di0
    prev_di1 = current_di1
    prev_di2 = current_di2

    -- =========================================================
    -- D. XỬ LÝ LỆNH SOCKET TỪ BACKEND (100ms timeout)
    -- =========================================================
    -- Xử lý cả: phản hồi PICK/STORE <slot> (cho PENDING_OPERATION)
    --          + lệnh điều khiển trực tiếp (STATUS, STOP, MOVE_HOME...)
    local recv_time, recv_data = SocketReceive(socket_id, 100, 1)
    if recv_data and recv_data ~= "" then
        print("📥 RX: " .. recv_data)
        local cmd, param, raw = ParseCommand(recv_data)

        -- D.1: Phản hồi PICK <slot> khi PENDING_OPERATION == "OUTBOUND"
        if PENDING_OPERATION == "OUTBOUND"
           and (cmd == "PICK" or cmd == "SLOT")
           and param ~= "" and param ~= "NONE" then
            print("🎯 [NON-BLOCK] Backend chi dinh lay o: " .. param)
            PENDING_OPERATION = nil
            ROBOT_STATE = "IDLE"
            if Execute_OutboundCycle(param) then
                SocketSend(socket_id, "DONE_PICK " .. param .. "\n", 0)
            else
                SocketSend(socket_id, "FAILED_PICK " .. param .. "\n", 0)
            end

        -- D.2: Phản hồi STORE <slot> khi PENDING_OPERATION == "INBOUND"
        elseif PENDING_OPERATION == "INBOUND"
           and (cmd == "STORE" or cmd == "SLOT")
           and param ~= "" and param ~= "NONE" and param ~= "FULL" then
            print("🎯 [NON-BLOCK] Backend chi dinh cat vao o: " .. param)
            PENDING_OPERATION = nil
            ROBOT_STATE = "IDLE"
            if Execute_InboundCycle(param) then
                SocketSend(socket_id, "DONE_STORE " .. param .. "\n", 0)
            else
                SocketSend(socket_id, "FAILED_STORE " .. param .. "\n", 0)
            end

        -- D.3: Backend báo không có ô khả dụng (kho đầy / không có đơn)
        elseif PENDING_OPERATION ~= nil
           and (cmd == "NONE" or cmd == "NO_SLOT" or cmd == "FULL") then
            print("⚠️ Backend bao khong co o kha dung: " .. tostring(param))
            PENDING_OPERATION = nil
            ROBOT_STATE = "IDLE"

        -- D.4: Lệnh điều khiển trực tiếp
        elseif cmd == "STATUS" or cmd == "GET_STATUS" then
            local is_busy = (ROBOT_STATE ~= "IDLE") and "TRUE" or "FALSE"
            local pend    = PENDING_OPERATION or "NONE"
            local status_resp = string.format("STATE:%s BUSY:%s POSITION:%s PENDING:%s\n",
                                              ROBOT_STATE, is_busy, CURRENT_POS, pend)
            SocketSend(socket_id, status_resp, 0)

        elseif cmd == "STOP" or cmd == "ESTOP" then
            Execute_Stop()
            SocketSend(socket_id, "STOP SUCCESS STATE:ESTOP\n", 0)

        elseif cmd == "RESET" or cmd == "RESET_ESTOP" or cmd == "CLEAR_FAULT" then
            Execute_ResetFault()
            SocketSend(socket_id, "RESET SUCCESS STATE:IDLE\n", 0)

        elseif cmd == "MOVE_HOME" then
            if ROBOT_STATE ~= "IDLE" and ROBOT_STATE ~= "ESTOP" and ROBOT_STATE ~= "WAITING_SLOT" then
                SocketSend(socket_id, "BUSY STATE:" .. ROBOT_STATE .. " POSITION:" .. CURRENT_POS .. "\n", 0)
            else
                if Execute_MoveHome() then
                    SocketSend(socket_id, "SUCCESS MOVE_HOME\n", 0)
                else
                    SocketSend(socket_id, "FAILED MOVE_HOME\n", 0)
                end
            end

        elseif cmd == "OUTBOUND_CYCLE" or cmd == "PICK_TO_O1" then
            if ROBOT_STATE ~= "IDLE" then
                SocketSend(socket_id, "BUSY STATE:" .. ROBOT_STATE .. " POSITION:" .. CURRENT_POS .. "\n", 0)
            else
                if Execute_OutboundCycle(param) then
                    SocketSend(socket_id, "SUCCESS OUTBOUND " .. param .. "\n", 0)
                else
                    SocketSend(socket_id, "FAILED OUTBOUND " .. param .. "\n", 0)
                end
            end

        elseif cmd == "INBOUND_CYCLE" or cmd == "STORE_FROM_O1" then
            if ROBOT_STATE ~= "IDLE" then
                SocketSend(socket_id, "BUSY STATE:" .. ROBOT_STATE .. " POSITION:" .. CURRENT_POS .. "\n", 0)
            else
                if Execute_InboundCycle(param) then
                    SocketSend(socket_id, "SUCCESS INBOUND " .. param .. "\n", 0)
                else
                    SocketSend(socket_id, "FAILED INBOUND " .. param .. "\n", 0)
                end
            end

        elseif cmd == "PICK" or cmd == "PICK_PRODUCT" then
            if ROBOT_STATE ~= "IDLE" then
                SocketSend(socket_id, "BUSY STATE:" .. ROBOT_STATE .. " POSITION:" .. CURRENT_POS .. "\n", 0)
            else
                if MoveToSlotAndAct(param) then
                    SocketSend(socket_id, "SUCCESS PICK " .. param .. "\n", 0)
                else
                    SocketSend(socket_id, "FAILED INVALID_SLOT " .. param .. "\n", 0)
                end
            end

        elseif cmd == "STORE" or cmd == "PLACE_PRODUCT" then
            if ROBOT_STATE ~= "IDLE" then
                SocketSend(socket_id, "BUSY STATE:" .. ROBOT_STATE .. " POSITION:" .. CURRENT_POS .. "\n", 0)
            else
                if MoveToSlotAndAct(param) then
                    SocketSend(socket_id, "SUCCESS STORE " .. param .. "\n", 0)
                else
                    SocketSend(socket_id, "FAILED INVALID_SLOT " .. param .. "\n", 0)
                end
            end

        elseif cmd == "GRIPPER_OPEN" or cmd == "OPEN_GRIPPER" or cmd == "GRIPPER_CLOSE" or cmd == "CLOSE_GRIPPER" then
            print("ℹ️ Lệnh tay kẹp DO1 đã được gỡ bỏ -> Bỏ qua lệnh " .. cmd)
            SocketSend(socket_id, "SUCCESS " .. cmd .. "\n", 0)

        else
            print("⚠️ Lệnh không xác định: " .. tostring(cmd))
            SocketSend(socket_id, "UNKNOWN COMMAND\n", 0)
        end
    end
    sleep_ms(50)
end

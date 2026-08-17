-- =========================================================================
-- FAIRINO FR3 INDUSTRIAL WAREHOUSE SOCKET SERVER
-- Firmware: V3.9.21 / FR3 V6.0 | Port: 8090 (Socket 1)
-- Quản lý: A1 -> C3, N1 và HOME
-- =========================================================================

local socket_id = 1

-- 1. QUẢN LÝ MÁY TRẠNG THÁI (STATE MACHINE)
local ROBOT_STATE = "IDLE"       -- "IDLE", "MOVING", "GRIPPING", "ERROR", "ESTOP"
local CURRENT_POS = "HOME"       -- Lưu vị trí hiện tại của Robot
local STOP_REQUESTED = false     -- Cờ yêu cầu dừng

print("FAIRINO Industrial Socket Server Ready on Socket 1")

-- =========================================================================
-- CÁC HÀM ĐIỀU KHIỂN CHUYỂN ĐỘNG & THIẾT BỊ
-- =========================================================================

-- Điều khiển tay kẹp và cập nhật trạng thái
function SetGripper(close)
    ROBOT_STATE = "GRIPPING"
    SetDO(1, close and 1 or 0, 0, 0)
    sleep_ms(500)
end

-- Lệnh dừng khẩn cấp / Dừng tác vụ
function Execute_Stop()
    print("EMERGENCY STOP TRIGGERED")
    STOP_REQUESTED = true
    ROBOT_STATE = "ESTOP"
    
    -- Dừng chuyển động robot & Tắt van kẹp
    StopMotion()
    SetDO(1, 0, 0, 0)
    sleep_ms(200)
    
    ROBOT_STATE = "IDLE"
    STOP_REQUESTED = false
    return true
end

-- Về vị trí Home an toàn
function Execute_MoveHome()
    if ROBOT_STATE ~= "IDLE" then return false end

    ROBOT_STATE = "MOVING"
    print("Moving to HOME...")
    
    PTP(HOME, 20, -1, 0)
    
    CURRENT_POS = "HOME"
    ROBOT_STATE = "IDLE"
    return true
end

-- Chu trình gắp/thả ô kho (Approach -> Wait -> Target -> Grip -> Wait -> Retract)
function Execute_SlotMotion(slot, is_pick)
    if ROBOT_STATE ~= "IDLE" then return false end
    STOP_REQUESTED = false

    -- BƯỚC 1: TIẾP CẬN (Approach Offset -100mm)
    ROBOT_STATE = "MOVING"
    print("Approaching slot -> " .. slot)

    if slot == "A1" then PTP(A1, 30, -1, 1, 0, -100, 0, 0, 0, 0)
    elseif slot == "A2" then PTP(A2, 30, -1, 1, 0, -100, 0, 0, 0, 0)
    elseif slot == "A3" then PTP(A3, 30, -1, 1, 0, -100, 0, 0, 0, 0)
    elseif slot == "B1" then PTP(B1, 30, -1, 1, 0, -100, 0, 0, 0, 0)
    elseif slot == "B2" then PTP(B2, 30, -1, 1, 0, -100, 0, 0, 0, 0)
    elseif slot == "B3" then PTP(B3, 30, -1, 1, 0, -100, 0, 0, 0, 0)
    elseif slot == "C1" then PTP(C1, 30, -1, 1, 0, -100, 0, 0, 0, 0)
    elseif slot == "C2" then PTP(C2, 30, -1, 1, 0, -100, 0, 0, 0, 0)
    elseif slot == "C3" then PTP(C3, 30, -1, 1, 0, -100, 0, 0, 0, 0)
    elseif slot == "N1" then PTP(N1, 30, -1, 1, 0, -100, 0, 0, 0, 0)
    else
        ROBOT_STATE = "ERROR"
        sleep_ms(100)
        ROBOT_STATE = "IDLE"
        return false
    end

    if STOP_REQUESTED then return false end
    WaitMs(3000)

    -- BƯỚC 2: TIẾN VÀO VỊ TRÍ CHÍNH
    print("Moving into target -> " .. slot)
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
    end

    if STOP_REQUESTED then return false end
    WaitMs(3000)

    -- BƯỚC 3: ĐIỀU KHIỂN TAY KẸP
    SetGripper(is_pick)

    -- BƯỚC 4: RÚT TAY MÁY LÊN OFFSET AN TOÀN
    ROBOT_STATE = "MOVING"
    if slot == "A1" then PTP(A1, 30, -1, 1, 0, -100, 0, 0, 0, 0)
    elseif slot == "A2" then PTP(A2, 30, -1, 1, 0, -100, 0, 0, 0, 0)
    elseif slot == "A3" then PTP(A3, 30, -1, 1, 0, -100, 0, 0, 0, 0)
    elseif slot == "B1" then PTP(B1, 30, -1, 1, 0, -100, 0, 0, 0, 0)
    elseif slot == "B2" then PTP(B2, 30, -1, 1, 0, -100, 0, 0, 0, 0)
    elseif slot == "B3" then PTP(B3, 30, -1, 1, 0, -100, 0, 0, 0, 0)
    elseif slot == "C1" then PTP(C1, 30, -1, 1, 0, -100, 0, 0, 0, 0)
    elseif slot == "C2" then PTP(C2, 30, -1, 1, 0, -100, 0, 0, 0, 0)
    elseif slot == "C3" then PTP(C3, 30, -1, 1, 0, -100, 0, 0, 0, 0)
    elseif slot == "N1" then PTP(N1, 30, -1, 1, 0, -100, 0, 0, 0, 0)
    end

    CURRENT_POS = slot
    ROBOT_STATE = "IDLE"
    return true
end

-- =========================================================================
-- BỘ TÁCH LỆNH CHUẨN (PATTERN PARSER NÂNG CAO)
-- =========================================================================
function ParseCommand(raw_data)
    if not raw_data or raw_data == "" then
        return "", "", ""
    end

    -- 1. Loại bỏ ký tự xuống dòng thực tế (\r = 0x0D, \n = 0x0A)
    local clean_data = string.gsub(raw_data, "[%r%n]", "")
    
    -- 2. Loại bỏ chuỗi ký tự thô "\\r" và "\\n" (nếu client gửi dính string literal)
    clean_data = string.gsub(clean_data, "\\r", "")
    clean_data = string.gsub(clean_data, "\\n", "")
    
    -- 3. Xóa khoảng trắng thừa ở đầu và cuối chuỗi
    clean_data = string.match(clean_data, "^%s*(.-)%s*$") or ""

    -- 4. Tách Command và Parameter (tự động gom nhóm theo khoảng trắng)
    local cmd, param = string.match(clean_data, "^(%S+)%s*(%S*)$")
    
    -- 5. Tự động chuyển toàn bộ về CHỮ HOA (tránh lỗi case-sensitive)
    cmd = cmd and string.upper(cmd) or ""
    param = param and string.upper(param) or ""
    
    return cmd, param, clean_data
end
-- =========================================================================
-- VÒNG LẬP NHẬN & PHÂN PHỐI LỆNH SOCKET
-- =========================================================================
while true do
    local recv_time, recv_data = SocketReceive(socket_id, 100, 1)

    if recv_data and recv_data ~= "" then
        print("RX: " .. recv_data)
        local cmd, param, raw = ParseCommand(recv_data)

        -- 1. LỆNH TRUY VẤN TRẠNG THÁI (Không bị chặn bởi trạng thái Busy)
        if cmd == "STATUS" or cmd == "GET_STATUS" then
            local is_busy = (ROBOT_STATE ~= "IDLE") and "TRUE" or "FALSE"
            local status_resp = string.format("STATE:%s BUSY:%s POSITION:%s\n", ROBOT_STATE, is_busy, CURRENT_POS)
            SocketSend(socket_id, status_resp, 0)

        -- 2. LỆNH DỪNG KHẨN CẤP (Luôn ưu tiên thực thi)
        elseif cmd == "STOP" or cmd == "ESTOP" then
            Execute_Stop()
            SocketSend(socket_id, "STOP SUCCESS STATE:IDLE\n", 0)

        -- 3. CÁC LỆNH ĐIỀU KHIỂN CHUYỂN ĐỘNG
        elseif cmd == "MOVE_HOME" then
            if ROBOT_STATE ~= "IDLE" then
                SocketSend(socket_id, "BUSY STATE:" .. ROBOT_STATE .. " POSITION:" .. CURRENT_POS .. "\n", 0)
            else
                if Execute_MoveHome() then
                    SocketSend(socket_id, "SUCCESS MOVE_HOME\n", 0)
                else
                    SocketSend(socket_id, "FAILED MOVE_HOME\n", 0)
                end
            end

        elseif cmd == "PICK" or cmd == "PICK_PRODUCT" then
            if ROBOT_STATE ~= "IDLE" then
                SocketSend(socket_id, "BUSY STATE:" .. ROBOT_STATE .. " POSITION:" .. CURRENT_POS .. "\n", 0)
            else
                if Execute_SlotMotion(param, true) then
                    SocketSend(socket_id, "SUCCESS PICK " .. param .. "\n", 0)
                else
                    SocketSend(socket_id, "FAILED INVALID_SLOT " .. param .. "\n", 0)
                end
            end

        elseif cmd == "STORE" or cmd == "PLACE_PRODUCT" then
            if ROBOT_STATE ~= "IDLE" then
                SocketSend(socket_id, "BUSY STATE:" .. ROBOT_STATE .. " POSITION:" .. CURRENT_POS .. "\n", 0)
            else
                if Execute_SlotMotion(param, false) then
                    SocketSend(socket_id, "SUCCESS STORE " .. param .. "\n", 0)
                else
                    SocketSend(socket_id, "FAILED INVALID_SLOT " .. param .. "\n", 0)
                end
            end

        else
            SocketSend(socket_id, "UNKNOWN COMMAND\n", 0)
        end
    end

    sleep_ms(50)
end

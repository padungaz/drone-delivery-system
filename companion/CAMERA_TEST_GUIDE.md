# Test USB Camera Guide

## 1. Test Camera Cơ Bản (Không ArUco)

Kiểm tra camera hoạt động hay không:

```bash
cd companion

# Scan tất cả cameras
python test_usb_camera.py all

# Test camera 0
python test_usb_camera.py 0

# Test camera 1
python test_usb_camera.py 1
```

**Output:**
```
[*] Scanning cameras (0-4)...

[✓] Camera 0: 1280x720
[✗] Camera 1: không kết nối
[✗] Camera 2: không kết nối
```

Ghi nhớ camera index (0, 1, v.v.) và cập nhật `CAMERA_WEBCAM_INDEX` trong `config.py` nếu cần.

## 2. Chuẩn Bị ArUco Marker

Sinh marker ArUco ID=0:

```bash
python generate_aruco_marker.py 0
```

**Output:**
- File: `aruco_marker_0.png`
- Hình ảnh này có thể:
  - In ra giấy A4 (khuyên 15cm x 15cm)
  - Hiển thị trên một thiết bị khác (iPad, laptop, điện thoại)

## 3. Test Camera Với ArUco Detection

### Step 1: Đổi config để dùng webcam

Edit `companion/config.py`:

```python
if RUN_MODE == "sim":
    CAMERA_BACKEND = "synthetic"  # ← Đổi thành "webcam"
    CAMERA_WEBCAM_INDEX = 0  # Camera index
```

Thay đổi thành:

```python
if RUN_MODE == "sim":
    CAMERA_BACKEND = "webcam"  # ← Đây
    CAMERA_WEBCAM_INDEX = 0
```

### Step 2: Chạy test

```bash
python test_usb_camera_aruco.py 0
```

Cửa sổ sẽ hiển thị:
- Live feed từ camera
- Trạng thái detection: "ArUco detected!" (xanh) hoặc "No ArUco detected" (đỏ)
- Distance, angle nếu marker được nhận dạng

### Step 3: Test detection

- Đặt ArUco marker trước camera
- Di chuyển marker gần/xa, xoay quanh để test
- Nhấn SPACE để chụp ảnh (save `aruco_capture_N.jpg`)
- Nhấn ESC để thoát

## 4. Tuning Detection (Nếu Không Detect)

Nếu camera không detect marker:

1. **Kiểm tra ánh sáng** — cần ánh sáng đủ
2. **Di chuyển marker** — phải trong khung hình
3. **Khoảng cách** — thử khoảng 30cm - 2m
4. **Marker ID** — kiểm tra `config.ARUCO_MARKER_ID` khớp với marker in ra

```python
# Trong config.py
ARUCO_MARKER_ID = 0  # Phải khớp với marker được in
ARUCO_MARKER_SIZE_M = 0.15  # 15cm (nếu in giấy A4)
```

## 5. Chuyển Lại Sang Synthetic (Test Hoàn tất)

Khi test xong, đổi lại `config.py`:

```python
if RUN_MODE == "sim":
    CAMERA_BACKEND = "synthetic"  # ← Quay lại synthetic
    CAMERA_WEBCAM_INDEX = 0
```

Và chạy companion app như bình thường:

```bash
python main.py
```

## 6. Trên Raspberry Pi (Production)

Khi deploy lên Pi với CSI camera:

1. Đổi `config.py`:
   ```python
   RUN_MODE = "pi"  # ← Đổi sang "pi"
   ```

2. Bật picamera2 trong `requirements.txt`:
   ```
   picamera2==0.3.25  # ← Bỏ dấu #
   ```

3. Cài đặt:
   ```bash
   pip install -r requirements.txt
   python main.py
   ```

CSI camera sẽ tự động init mà không cần test riêng.

---

## Troubleshooting

| Vấn đề | Giải pháp |
|-------|----------|
| Camera không mở | Kiểm tra chỉ số camera, thử `test_usb_camera.py all` |
| ArUco không detect | Kiểm tra ánh sáng, marker ID, khoảng cách |
| Frame rate chậm | Giảm resolution trong `config.py` hoặc dùng camera tốt hơn |
| "No module named 'cv2'" | `pip install opencv-python==4.10.0.84` |


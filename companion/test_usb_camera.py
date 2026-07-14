#!/usr/bin/env python3
"""Test USB camera — kiểm tra camera hoạt động hay không."""

import cv2
import sys

def test_camera(camera_index: int = 0, display: bool = True) -> bool:
    """
    Test USB camera.
    
    Args:
        camera_index: index camera (0 = default, 1 = second camera, etc.)
        display: show live feed (yêu cầu đổi CAMERA_BACKEND="webcam" trong config.py)
    
    Returns:
        True nếu camera hoạt động
    """
    print(f"[*] Mở camera index {camera_index}...")
    cap = cv2.VideoCapture(camera_index)
    
    if not cap.isOpened():
        print(f"[✗] Không thể mở camera {camera_index}")
        return False
    
    print(f"[✓] Camera {camera_index} mở thành công")
    
    # Lấy properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"  Resolution: {width}x{height}")
    print(f"  FPS: {fps}")
    
    # Capture một frame để test
    print("[*] Capturing frame...")
    ret, frame = cap.read()
    
    if not ret or frame is None:
        print("[✗] Không thể capture frame")
        cap.release()
        return False
    
    print(f"[✓] Frame capture thành công: {frame.shape}")
    
    # Nếu muốn display
    if display:
        print("[*] Nhấn ESC để thoát, SPACE để chụp ảnh...")
        frame_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            cv2.putText(
                frame, 
                f"Frame {frame_count} | Press ESC to exit, SPACE to capture", 
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 
                0.7, 
                (0, 255, 0), 
                2
            )
            
            cv2.imshow("USB Camera Test", frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                print("[*] Thoát...")
                break
            elif key == 32:  # SPACE
                filename = f"camera_capture_{frame_count}.jpg"
                cv2.imwrite(filename, frame)
                print(f"[✓] Lưu ảnh: {filename}")
        
        cv2.destroyAllWindows()
    
    cap.release()
    print("[✓] Camera test hoàn tất")
    return True


def test_all_cameras(max_cameras: int = 5) -> list[int]:
    """Test tất cả camera có sẵn."""
    print(f"[*] Scanning cameras (0-{max_cameras-1})...\n")
    available = []
    
    for i in range(max_cameras):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available.append(i)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"[✓] Camera {i}: {width}x{height}")
            cap.release()
        else:
            print(f"[✗] Camera {i}: không kết nối")
    
    return available


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "all":
            available = test_all_cameras()
            print(f"\n[*] Available cameras: {available}")
        else:
            cam_idx = int(sys.argv[1])
            test_camera(camera_index=cam_idx, display=True)
    else:
        print("Usage:")
        print("  python test_usb_camera.py all          # Scan tất cả cameras")
        print("  python test_usb_camera.py 0            # Test camera 0 (default)")
        print("  python test_usb_camera.py 1            # Test camera 1")
        print()
        test_all_cameras()

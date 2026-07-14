#!/usr/bin/env python3
"""Sinh ArUco marker để in ra hoặc test."""

import cv2
import numpy as np

def generate_aruco_marker(marker_id: int = 0, size: int = 200, filename: str = None):
    """
    Generate ArUco marker.
    
    Args:
        marker_id: ID của marker
        size: kích thước marker (px)
        filename: nếu có, save vào file
    """
    dict_id = cv2.aruco.DICT_4X4_50
    aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
    
    print(f"[*] Generating ArUco marker ID={marker_id}, size={size}x{size}")
    
    # Generate marker image
    marker_image = cv2.aruco.generateImageMarker(aruco_dict, marker_id, size, borderBits=1)
    
    # Add white border (để dễ nhận dạng)
    border = 20
    marker_with_border = cv2.copyMakeBorder(
        marker_image,
        border, border, border, border,
        cv2.BORDER_CONSTANT,
        value=255
    )
    
    if filename:
        cv2.imwrite(filename, marker_with_border)
        print(f"[✓] Lưu vào: {filename}")
    
    # Display
    cv2.imshow(f"ArUco Marker ID={marker_id}", marker_with_border)
    print("[*] Nhấn phím bất kỳ để đóng...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    return marker_with_border


def generate_aruco_with_text(marker_id: int = 0, filename: str = None):
    """Generate ArUco marker với text ghi ID."""
    size = 400
    dict_id = cv2.aruco.DICT_4X4_50
    aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
    
    marker_image = cv2.aruco.generateImageMarker(aruco_dict, marker_id, size, borderBits=1)
    
    # Add border
    border = 40
    h, w = marker_image.shape
    result = np.ones((h + 2*border + 60, w + 2*border), dtype=np.uint8) * 255
    result[border:border+h, border:border+w] = marker_image
    
    # Add text
    cv2.putText(
        result,
        f"ID={marker_id}",
        (border + 50, border + h + 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.5,
        0,
        3
    )
    
    if filename:
        cv2.imwrite(filename, result)
        print(f"[✓] Lưu vào: {filename}")
    
    return result


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        marker_id = int(sys.argv[1])
    else:
        marker_id = 0
    
    print(f"\n=== ArUco Marker Generator ===")
    print(f"Generating marker ID={marker_id}\n")
    
    # Generate và save
    marker = generate_aruco_with_text(
        marker_id=marker_id,
        filename=f"aruco_marker_{marker_id}.png"
    )
    
    print(f"\n[*] Hướng dùng:")
    print(f"    - In ảnh 'aruco_marker_{marker_id}.png' ra giấy A4 hoặc trên máy tính")
    print(f"    - Để camera nhìn thấy marker")
    print(f"    - Chạy: python test_usb_camera_aruco.py")

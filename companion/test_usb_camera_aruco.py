# #!/usr/bin/env python3
# """Test USB camera với ArUco detection — test camera + detect ArUco markers (dùng OpenCV trực tiếp)."""

# import cv2
# import cv2.aruco as aruco
# import sys
# import logging

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # Import từ companion (chỉ lấy config)
# import config


# def test_camera_with_aruco(camera_index: int = 0):
#     """
#     Test USB camera + ArUco detection.
    
#     Yêu cầu: đổi CAMERA_BACKEND="webcam" trong config.py (không bắt buộc, chỉ để nhắc nhở)
#     """
#     print(f"[*] Mở camera {camera_index}...")
#     cap = cv2.VideoCapture(camera_index)
    
#     if not cap.isOpened():
#         print(f"[✗] Không thể mở camera {camera_index}")
#         return
    
#     width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
#     height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
#     print(f"[✓] Camera mở: {width}x{height}")
    
#     # --- Khởi tạo ArUco detector (trực tiếp OpenCV) ---
#     print("[*] Khởi tạo ArUco detector (OpenCV)...")
#     # Sử dụng dictionary 5x5_100 (phổ biến cho landing)
#     aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_5X5_100)
#     parameters = aruco.DetectorParameters()
    
#     # Hỗ trợ cả OpenCV phiên bản >= 4.7 và cũ hơn
#     if hasattr(aruco, 'ArucoDetector'):
#         detector = aruco.ArucoDetector(aruco_dict, parameters)
#     else:
#         detector = None
    
#     print("[*] Nhấn ESC hoặc 'q' để thoát, SPACE để chụp ảnh...")
#     frame_count = 0
#     detected_count = 0
    
#     while True:
#         ret, frame = cap.read()
#         if not ret:
#             break
        
#         frame_count += 1
        
#         # Chuyển sang ảnh xám để detect tốt hơn
#         gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
#         # Detect markers
#         if detector:
#             corners, ids, rejected = detector.detectMarkers(gray)
#         else:
#             corners, ids, rejected = aruco.detectMarkers(gray, aruco_dict, parameters=parameters)
        
#         # Vẽ crosshair ở tâm màn hình
#         h, w = frame.shape[:2]
#         center_x, center_y = w // 2, h // 2
#         cv2.line(frame, (center_x - 20, center_y), (center_x + 20, center_y), (255, 0, 0), 2)
#         cv2.line(frame, (center_x, center_y - 20), (center_x, center_y + 20), (255, 0, 0), 2)
        
#         # Xử lý khi phát hiện marker
#         if ids is not None and len(ids) > 0:
#             detected_count += 1
#             # Vẽ đường bao quanh marker (nếu có nhiều marker thì vẽ tất cả)
#             cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            
#             # Lấy marker đầu tiên (nếu có nhiều, bạn có thể xử lý tất cả)
#             for i in range(len(ids)):
#                 c = corners[i][0]
#                 # Tính tâm marker
#                 mx = int((c[0][0] + c[1][0] + c[2][0] + c[3][0]) / 4)
#                 my = int((c[0][1] + c[1][1] + c[2][1] + c[3][1]) / 4)
#                 cv2.circle(frame, (mx, my), 5, (0, 0, 255), -1)
                
#                 # Tính offset so với tâm camera
#                 offset_x = mx - center_x
#                 offset_y = my - center_y
                
#                 # Vẽ đường nối từ tâm camera đến marker
#                 cv2.line(frame, (center_x, center_y), (mx, my), (0, 255, 255), 2)
                
#                 # Hiển thị thông tin
#                 info = f"ID:{ids[i][0]} dx:{offset_x} dy:{offset_y}"
#                 cv2.putText(frame, info, (mx - 40, my - 20),
#                             cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
#             # Trạng thái chung
#             status_text = f"ArUco detected! ({len(ids)} marker(s))"
#             color = (0, 255, 0)
#         else:
#             status_text = "No ArUco detected"
#             color = (0, 0, 255)
        
#         # Hiển thị thông tin trạng thái chung
#         cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
#         cv2.putText(
#             frame,
#             f"Frame {frame_count} (Detected: {detected_count}) | ESC/q=exit SPACE=capture",
#             (10, 70),
#             cv2.FONT_HERSHEY_SIMPLEX,
#             0.6,
#             (200, 200, 0),
#             2
#         )
        
#         cv2.imshow("USB Camera + ArUco Test (OpenCV direct)", frame)
        
#         key = cv2.waitKey(1) & 0xFF
#         if key == 27 or key == ord('q'):  # ESC hoặc q
#             print(f"[*] Thoát... (Detected {detected_count}/{frame_count} frames)")
#             break
#         elif key == 32:  # SPACE
#             filename = f"aruco_capture_{frame_count}.jpg"
#             cv2.imwrite(filename, frame)
#             print(f"[✓] Lưu: {filename}")
    
#     cap.release()
#     cv2.destroyAllWindows()
#     print("[✓] Test hoàn tất")


# if __name__ == "__main__":
#     if len(sys.argv) > 1:
#         cam_idx = int(sys.argv[1])
#     else:
#         cam_idx = config.CAMERA_WEBCAM_INDEX
    
#     print(f"Config: CAMERA_BACKEND={config.CAMERA_BACKEND}, CAMERA_WEBCAM_INDEX={cam_idx}")
    
#     if config.CAMERA_BACKEND != "webcam":
#         print("[!] Cảnh báo: config.CAMERA_BACKEND != 'webcam'")
#         print("[!] Hãy đổi CAMERA_BACKEND='webcam' trong config.py nếu dùng webcam")
#         print()
    
#     test_camera_with_aruco(camera_index=cam_idx)

#!/usr/bin/env python3

"""
USB Camera + ArUco detection test

Raspberry Pi 5
OpenCV 4.10+
"""


import cv2
import cv2.aruco as aruco

import sys
import time

import config



# =====================================================
# ArUco dictionary mapping
# =====================================================

ARUCO_DICT = {

    "DICT_4X4_50":
        aruco.DICT_4X4_50,

    "DICT_5X5_100":
        aruco.DICT_5X5_100,

    "DICT_6X6_250":
        aruco.DICT_6X6_250
}



def create_detector():

    name = config.ARUCO_DICTIONARY

    dictionary = aruco.getPredefinedDictionary(
        ARUCO_DICT[name]
    )


    parameters = aruco.DetectorParameters()


    if hasattr(
        aruco,
        "ArucoDetector"
    ):

        detector = aruco.ArucoDetector(
            dictionary,
            parameters
        )

    else:

        detector = None


    return (
        dictionary,
        parameters,
        detector
    )




def test_camera(camera_index):


    print(
        f"[INFO] Camera index = {camera_index}"
    )


    cap = cv2.VideoCapture(
        camera_index,
        cv2.CAP_V4L2
    )


    if not cap.isOpened():

        print(
            "[ERROR] Cannot open camera"
        )

        return



    # Camera setting

    cap.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        config.CAMERA_WIDTH
    )

    cap.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        config.CAMERA_HEIGHT
    )

    cap.set(
        cv2.CAP_PROP_FPS,
        config.CAMERA_FPS
    )



    width = int(
        cap.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )
    )


    height = int(
        cap.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
    )


    fps = cap.get(
        cv2.CAP_PROP_FPS
    )


    print(
        f"[OK] Camera {width}x{height} FPS={fps}"
    )



    dictionary, parameters, detector = create_detector()



    print(
        "[INFO] ArUco dictionary:",
        config.ARUCO_DICTIONARY
    )


    print(
        "Press q or ESC to exit"
    )


    frame_count = 0
    detect_count = 0


    last_time = time.time()



    while True:


        ret, frame = cap.read()


        if not ret:

            print(
                "[ERROR] Frame failed"
            )

            break



        frame_count += 1



        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY
        )



        # Detect

        if detector:


            corners, ids, rejected = (
                detector.detectMarkers(
                    gray
                )
            )


        else:


            corners, ids, rejected = (
                aruco.detectMarkers(
                    gray,
                    dictionary,
                    parameters=parameters
                )
            )



        h,w = frame.shape[:2]


        cx = w//2
        cy = h//2



        cv2.drawMarker(
            frame,
            (cx,cy),
            (255,0,0),
            cv2.MARKER_CROSS,
            30,
            2
        )



        if ids is not None:


            detect_count += 1


            aruco.drawDetectedMarkers(
                frame,
                corners,
                ids
            )


            for i, marker_id in enumerate(ids):


                c = corners[i][0]


                mx = int(
                    sum(
                        p[0]
                        for p in c
                    ) / 4
                )


                my = int(
                    sum(
                        p[1]
                        for p in c
                    ) / 4
                )



                dx = mx-cx

                dy = my-cy



                cv2.circle(
                    frame,
                    (mx,my),
                    5,
                    (0,0,255),
                    -1
                )



                text = (
                    f"ID:{marker_id[0]}"
                    f" dx:{dx}"
                    f" dy:{dy}"
                )


                cv2.putText(
                    frame,
                    text,
                    (20,40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0,255,0),
                    2
                )



        else:


            cv2.putText(
                frame,
                "No ArUco",
                (20,40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0,0,255),
                2
            )



        now = time.time()


        fps_now = (
            1/(now-last_time)
        )

        last_time = now



        cv2.putText(
            frame,
            f"FPS:{fps_now:.1f}",
            (20,80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255,255,255),
            2
        )



        cv2.imshow(
            "Drone Landing Camera Test",
            frame
        )



        key = cv2.waitKey(1)&0xff


        if key == 27 or key == ord('q'):

            break



    print(
        f"Detected {detect_count}/{frame_count}"
    )


    cap.release()

    cv2.destroyAllWindows()




if __name__ == "__main__":


    cam = config.CAMERA_WEBCAM_INDEX


    if len(sys.argv)>1:

        cam=int(sys.argv[1])


    print(
        "Backend:",
        config.CAMERA_BACKEND
    )


    test_camera(cam)
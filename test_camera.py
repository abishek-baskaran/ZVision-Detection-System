import cv2; import time; for dev in [0, 1, "/dev/video0", "/dev/video1"]: print(f"\nTrying {dev}"); cap = cv2.VideoCapture(dev); print(f"Is opened: {cap.isOpened()}"); if cap.isOpened(): ret, frame = cap.read(); print(f"Read frame: {ret}, shape: {frame.shape if ret else None}"); cap.release(); time.sleep(1)

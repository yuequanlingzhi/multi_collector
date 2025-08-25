# test.py
from BaseDevice.MilliWaveDevice import MilliWaveDevice
import cv2
import numpy as np
import time

def main():
    mill = MilliWaveDevice(**{"device_name":"milliwave", "port":"COM8", "frame_rate":10, "baud_rate":2000000})
    mill.start()
    cnt = 0
    start = time.time()
    while True:
        frame = mill.get_current_data()
        if frame is None:
            continue
        cv2.imshow("milliwave", frame)
        cnt += 1
        if time.time() - start > 1:
            print(f"FPS: {cnt}")
            cnt = 0
            start = time.time()
        key = cv2.waitKey(1)
        if key == ord('q'):
            break

    mill.stop()
    cv2.destroyAllWindows()

# 这是关键！
if __name__ == '__main__':
    main()
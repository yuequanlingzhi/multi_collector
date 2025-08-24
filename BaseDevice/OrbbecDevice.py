import time
import cv2
import numpy as np
from openni import openni2
from BaseDevice.BaseDevice import BaseDevice


class OrbbecDevice(BaseDevice):
    def __init__(self, **kwargs):
        device_name = kwargs.get("device_name")
        frame_rate = kwargs.get("frame_rate")
        meta_info = kwargs.get("meta_info")
        frame_type = kwargs.get("frame_type")
        super().__init__(device_name,frame_rate=frame_rate)
        self.frame_rate = frame_rate
        self.meta_info = meta_info if meta_info else {}
        self.frame_interval = 1.0 / frame_rate
        self.running = True
        self.current = None
        self.frame_type = frame_type

    def _collect_loop(self):
        openni2.initialize()
        self.dev = openni2.Device.open_any()
        if self.frame_type == "depth":
            self.frame_stream = self.dev.create_depth_stream()
        elif self.frame_type == "ir":
            self.frame_stream = self.dev.create_ir_stream()

        self.frame_stream.start()
        
        while self.running:
            try:
                frame = self.frame_stream.read_frame()

                timestamp = time.time()
                if frame is None:
                    print(f"[{self.device_name}] 读取帧失败")
                    continue
            except Exception:
                print(f"[{self.device_name}] 读取帧失败")
            finally:
                pass

                self.current, frame_data = self.get_current_help(frame)
                if self.one_frame is None:
                    self.one_frame = frame_data
                if BaseDevice.recording:
                    self.put_data_to_buffer((frame_data, timestamp))

    def get_current_help(self,frame: openni2.VideoFrame):
        data = np.array(frame.get_buffer_as_uint16()).reshape(480, 640)
        #左右翻转
        data = cv2.flip(data, 1)
        image = cv2.normalize(data, None, 0, 255, cv2.NORM_MINMAX)
        image = image.astype(np.uint8)
        return image,data
    
    def get_current_data(self):
        if self.current is not None:
            return self.current
        return None

    def release(self):
        self.frame_stream.stop()
        self.dev.close()
        openni2.unload()
import time
import cv2
import numpy as np
from BaseDevice.util.xep import xep
from BaseDevice.BaseDevice import BaseDevice
class UwbDevice(BaseDevice):
    def __init__(self, **kwargs):
        device_name = kwargs.get("device_name")
        frame_rate = kwargs.get("frame_rate", 200)
        meta_info = kwargs.get("meta_info")
        port = kwargs.get("port")
        super().__init__(device_name, frame_rate=frame_rate)
        self.config = {
            "FPS": frame_rate,
            "RANGE_START": 0.0,
            "RANGE_END": 2.5,
            "STEP": 360,
            "OFFSET": 0
        }
        self.meta_info = meta_info
        self.port = port
        self.data_show = []
        self.show_time = 5
        self.show_window = self.show_time * self.frame_rate
    
    def _collect_loop(self):
        self.uwb_radar = xep(self.port)
        self.uwb_radar.configure(dac_min=950, 
                                 dac_max=1050, 
                                 frame_offset=0.25, 
                                 frame_start=self.config["RANGE_START"], 
                                 frame_end=self.config["RANGE_END"], 
                                 baseband=True, 
                                 fps=self.config["FPS"]
                                 ) 
        self.uwb_radar.start_streaming()
        while self.running:
            frame = self.uwb_radar.read_frame()
            timestamp = time.time()
            if frame is None:
                continue
            if self.one_frame is None:
                self.one_frame = np.array(frame)
            self.data_show.append(np.abs(frame))
            if len(self.data_show) > self.show_window:
                self.data_show.pop(0)
            if BaseDevice.recording:
                self.put_data_to_buffer((frame, timestamp))
    
    def get_current_data(self):
        return self.get_current_data_help()
    
    def get_current_data_help(self):
        width, height = 560, 420
        # data_show形状为[frame_nums, 50]
        data = np.array(self.data_show) 
        if data.size == 0:
            return np.zeros((height, width), dtype=np.uint8)

        # 归一化到0~255
        min_val = np.min(data)
        max_val = np.max(data)
        if max_val == min_val:
            max_val = min_val + 1  # 防止除零

        norm_data = (data - min_val) / (max_val - min_val)
        #gamma校正
        norm_data = np.power(norm_data, 0.5)
        norm_data = (norm_data * 255).astype(np.uint8)

        img = cv2.resize(norm_data.T, (width, height), interpolation=cv2.INTER_LINEAR)
        return img
    
    def release(self):
        self.uwb_radar.stop_streaming()
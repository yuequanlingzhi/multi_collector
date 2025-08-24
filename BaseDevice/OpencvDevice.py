import cv2
import numpy as np
import time
import os
from pygrabber.dshow_graph import FilterGraph
from BaseDevice.BaseDevice import BaseDevice

class OpencvDevice(BaseDevice):
    
    def __init__(self, **kwargs):
        device_name = kwargs.get("device_name")
        camera_name = kwargs.get("camera_name")
        frame_rate = kwargs.get("frame_rate", 30)
        frame_size = kwargs.get("frame_size", (1080, 1920, 3))
        exposure = kwargs.get("exposure")
        quality = kwargs.get("quality", 95)
        meta_info = kwargs.get("meta_info")
        super().__init__(device_name, frame_rate=frame_rate)
        self.device_name = device_name
        self.frame_size = frame_size
        self.meta_info = meta_info
        self.camera_name = camera_name
        self.exposure = exposure
        self.quality = quality
        self.h,self.w,self.c = self.frame_size
        self.n_frames = []
        self.current = None
        graph = FilterGraph()
        camera_list = graph.get_input_devices()
        if camera_name not in camera_list:
            print(f"设备 {device_name} 不存在")
            return
        else:
            self.idx = camera_list.index(self.camera_name)

    def _collect_loop(self):
        
        self.cap = cv2.VideoCapture(self.idx)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.w)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.h)
        self.cap.set(cv2.CAP_PROP_FPS, self.frame_rate)
        #设置曝光和焦距
        if self.exposure is not None:
            self.cap.set(cv2.CAP_PROP_EXPOSURE, self.exposure)
        start = time.time()
        cnt = 0
        while self.running:
            ret, frame = self.cap.read()
            timestamp = time.time()
            if not ret or frame is None:
                continue
            
            if not BaseDevice.recording:
                self.n_frames.append(self.encode(frame))
                if len(self.n_frames) > 10:
                    self.n_frames.pop(0)
            self.current = np.array(frame)
            if BaseDevice.recording:
                cnt += 1
                if time.time() - start > 1:
                    print(f"fps: {cnt}")
                    start = time.time()
                    cnt = 0
                self.put_data_to_buffer((frame, timestamp))


    def encode(self, frame):
        if frame is None:
            return None
        else:
            return cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality])[1]
        
    def get_current_data(self):
        if self.current is None:
            return np.zeros((self.h, self.w), dtype=np.uint8)
        else:
            return self.current
    
    def release(self):
        self.cap.release()
        return 
    
    def ini_data_buffer(self, index=None):
        self.frame_count = 0
        self.frame_dtype, self.frame_size= self.get_type_and_data()
        self.frame_max_size = int(self.frame_size*1.5)
        self.data = np.zeros((self.frame_rate*self.buffer_len, self.frame_max_size), dtype=self.frame_dtype)
        self.timestamps = []
        self.frame_lens = []

    def get_type_and_data(self):
        dtype = self.n_frames[0].dtype
        size = 0
        for frame in self.n_frames:
            size_ = len(frame)
            if size_ > size:
                size = size_
        return dtype, size
    
    def record(self):
        self.reading_buffer = True
        while BaseDevice.recording:
            try:
                frame, timestamp = self.buffer.get(timeout=1)
                
                frame_bytes = self.encode(frame)
                frame_len = len(frame_bytes)
                self.data[self.frame_count, :frame_len] = frame_bytes
                self.frame_lens.append(frame_len)
                self.timestamps.append(timestamp)
                self.frame_count += 1
            except Exception as e:
                print(f'{e}')
                continue
        self.reading_buffer = False

    def _save_data_all(self):
        while self.reading_buffer:
            time.sleep(0.1)
        if self.data is None:
            print(f"[{self.device_name}] 无数据保存")
            return
        folder = os.path.join(BaseDevice.save_floder,self.device_name)
        os.makedirs(folder, exist_ok=True)
        start = time.time()
        print(f"[{self.device_name}]转换数据格式耗时：{time.time() - start:.4f}s")
        l = len(self.timestamps)
        filename = os.path.join(folder, f"{self.timestamps[0]}f{self.frame_rate}c{l}.npz")

        # 保存多个变量
        np.savez(
            filename,
            device_name=self.device_name,
            frame_rate=self.frame_rate,
            timestamp=self.timestamps,
            frames=self.data[:l],
            frame_lens = self.frame_lens,
            meta_info=self.meta_info
        )
        print(f"[{self.device_name}] 数据保存到 {filename}, 帧长度为{l}，整体耗时：{time.time() - start:.4f}s")
        del self.data
        del self.timestamps
        self.ini_data_buffer()
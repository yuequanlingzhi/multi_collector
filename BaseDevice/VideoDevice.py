import os
import time
import numpy as np
import av
from BaseDevice.BaseDevice import BaseDevice
av.logging.set_level(av.logging.ERROR)

class VideoDevice(BaseDevice):
    def __init__(self, **kwargs):
        device_name = kwargs.get("device_name")
        camera_name = kwargs.get("camera_name")
        frame_size = kwargs.get("frame_size")
        frame_rate = kwargs.get("frame_rate")
        encode_type = kwargs.get("encode_type")
        meta_info = kwargs.get("meta_info",{})
        rtbufsize = kwargs.get("rtbufsize")
        super().__init__(device_name, frame_rate=frame_rate)
        self.frame_rate = round(frame_rate)
        self.meta_info = meta_info
        self.frame_interval = 1.0 / frame_rate
        self.meta_info['camera_name'] = camera_name
        self.current = None
        self.running = True
        self.n_frames = []
        h,w,c = frame_size
        # self.capture_area = (w//3,h//4,w//3,h//2)
        self.camera_name = f'video={camera_name}'
        self.options = {
            "rtbufsize": f"{rtbufsize}",
            "video_size": f"{w}x{h}",
            "framerate": f"{frame_rate}",
            **encode_type,
                        }
        print(self.options)

    def read(self, container):
        for packet in container.demux(video=0):
            return packet
        
    def _collect_loop(self):

        """
        这是一个循环采集视频帧的方法，用于在录制过程中持续从摄像头捕获图像帧。
        该方法会持续运行直到录制或运行状态被终止。
        """
        
        show_interval = 1/10
        self.container = av.open(self.camera_name, format='dshow',options=self.options)
        uselowfps = False
        if self.camera_name != "video=HD USB Camera":
            uselowfps = True
        cnt = 0
        start_real = time.time()
        show_fps = False
        show_cnt = 0
        while self.running:
            packet = self.read(self.container)
            timestamp = time.time()
            if packet is None:
                continue
            cnt = cnt+1
            if show_fps and time.time() - start_real > 1 and show_cnt<10:
                print(f"device:{self.device_name},fps:{cnt}")
                start_real = time.time()
                cnt = 0
                show_cnt += 1
            if uselowfps or timestamp - start > show_interval:
                start = timestamp
                img = packet.decode()[0]
                img = img.to_ndarray(format='bgr24')
                self.current = img
            if not BaseDevice.recording:
                self.n_frames.append(bytes(packet))
                if len(self.n_frames) > 10:
                    self.n_frames.pop(0)
            if BaseDevice.recording:
                self.put_data_to_buffer((bytes(packet), timestamp))
    

    def get_current_data(self):
        # 使用self.capture_area来标注区域，矩形红框
        # a,b = self.capture_area[0],self.capture_area[1]
        # w,h = self.capture_area[2],self.capture_area[3]
        if self.current is None:
            return None
        return self.current
    
    def release(self):
        self.container.close()

    #特异性重载
    def ini_data_buffer(self, index=None):
        self.frame_count = 0
        self.frame_size= self.get_size()
        self.frame_max_size = int(self.frame_size*2)
        self.data = []
        self.timestamps = []
        self.frame_lens = []

    def get_size(self):
        if self.camera_name == "video=HD Pro Webcam C920":
            return 100000
        size = 0
        for frame in self.n_frames:
            size_ = len(frame)
            if size_ > size:
                size = size_
        return size
    
    def decode_to_frame(self, packet):
        decode = packet.decode()[0]
        return decode.to_ndarray(format='bgr24')
    
    def record(self):
        self.reading_buffer = True
        while BaseDevice.recording:
            try:
                frame_bytes, timestamp = self.buffer.get(timeout=1)
                frame_len = len(frame_bytes)
                frame_pad = frame_bytes.ljust(self.frame_max_size, b'\x00')
                self.data.append(frame_pad)
                self.frame_lens.append(frame_len)
                self.timestamps.append(timestamp)
                self.frame_count += 1
            except:
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

        if self.camera_name == "video=HD Pro Webcam C920":
            for i in range(10):
                print(len(self.data[i]),self.frame_lens[i])
        # 保存多个变量
        np.savez(
            filename,
            device_name=self.device_name,
            frame_rate=self.frame_rate,
            timestamp=self.timestamps,
            frames=self.data,
            frame_lens = self.frame_lens,
            meta_info=self.meta_info
        )
        print(f"[{self.device_name}] 数据保存到 {filename}, 帧长度为{l}，整体耗时：{time.time() - start:.4f}s")
        del self.data
        del self.timestamps
        self.ini_data_buffer()
    
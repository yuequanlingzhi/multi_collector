import subprocess
import threading
import queue
import time
import av
import os
import numpy as np
from BaseDevice.BaseDevice import BaseDevice
av.logging.set_level(av.logging.ERROR)
class FFmpegDevice(BaseDevice):
    def __init__(self, **kwargs):
        device_name = kwargs.get('device_name')
        camera_name = kwargs.get('camera_name')
        frame_size = kwargs.get('frame_size')
        frame_rate = kwargs.get('frame_rate')
        encode_type = kwargs.get("encode_type", "mjpeg")
        meta_info = kwargs.get('meta_info',{})
        super().__init__(device_name=device_name,frame_rate=frame_rate)
        self.camera_name = camera_name
        self.frame_size = frame_size
        self.meta_info = meta_info
        self.meta_info['camera_name'] = camera_name
        self.encode_type = encode_type
        self.show_fps = False
        self.current = None
        self.running = True
        self.decode_stream = None
        self.n_frames = []
        h,w,c = self.frame_size
        self.codec = av.codec.CodecContext.create(self.encode_type, 'r')
        self.option_list = [
            'ffmpeg',
            '-f', 'dshow',
            '-video_size', f'{w}x{h}',
            '-framerate', f'{self.frame_rate}',
            '-vcodec', 'mjpeg',
            '-i', f'video={self.camera_name}',
            '-f', 'mjpeg',
            '-q:v', '1',
            '-'
        ]
        self.frame_buffer = queue.Queue(maxsize=1)

    def decode(self, frame_bty):
        try:
            packet = av.packet.Packet(frame_bty)
            frames = self.codec.decode(packet)
            if frames:
                frame = frames[0]
                img = frame.to_ndarray(format='bgr24')
                return img
            else:
                return None
        except Exception as e:
            print(f"Decode error: {e}")
            return None
    
    def reader(self,pipe,btys_queue):
        while self.running:
            data = pipe.read(1024*1)
            if not data:
                break
            btys_queue.put(data)
        pipe.close()

    def stderr_reader(self, pipe):
        while True:
            if pipe.read(1024) == b'':
                break

    def start_ffmpeg(self, option_list):
        self.bty_buffer = b''
        btys_queue = queue.Queue()
        self.process = subprocess.Popen(option_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE,bufsize=10**8)
        threading.Thread(target=self.reader, args=(self.process.stdout, btys_queue), daemon=True).start()
        threading.Thread(target=self.stderr_reader, args=(self.process.stderr,), daemon=True).start()
        while self.running:
            try:
                chunk = btys_queue.get(timeout=1)
            except queue.Empty:
                if not self.running:
                    break
                else:
                    continue
            
            self.bty_buffer += chunk

            while True:
                start_marker = self.bty_buffer.find(b'\xff\xd8')
                end_marker = self.bty_buffer.find(b'\xff\xd9')
                if start_marker != -1 and end_marker != -1 and start_marker < end_marker:
                    frame_data = self.bty_buffer[start_marker:end_marker + 2]
                    self.bty_buffer = self.bty_buffer[end_marker + 2:]
                    if self.frame_buffer.full():
                        self.frame_buffer.get()
                    self.frame_buffer.put((frame_data, time.time()))
                else:
                    break
    

    def _collect_loop(self):
        threading.Thread(target=self.start_ffmpeg, args=(self.option_list,)).start()
        start = time.time()
        cnt = 0
        
        while self.running:
            try:
                frame_bty, timestamp = self.frame_buffer.get(timeout=1)
                self.current = frame_bty
                cnt += 1
                if self.show_fps and time.time() - start > 1:
                    print(f"device:{self.device_name},FPS: {cnt}")
                    start = time.time()
                    cnt = 0
                if not BaseDevice.recording:
                    self.n_frames.append(frame_bty)
                    if len(self.n_frames) > self.frame_rate:
                        self.n_frames.pop(0)
                if BaseDevice.recording:
                    self.put_data_to_buffer((frame_bty, timestamp))
            except queue.Empty:
                pass
    
    def get_size(self):
        size = 0
        for frame in self.n_frames:
            size_ = len(frame)
            if size_ > size:
                size = size_
        return size
    
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
    
    def ini_data_buffer(self, index=None):
        self.frame_count = 0
        self.frame_size= self.get_size()
        self.frame_max_size = int(self.frame_size*2)
        self.data = []
        self.timestamps = []
        self.frame_lens = []

    def get_current_data(self):
        if self.current is None:
            return None
        frame = self.decode(self.current)
        return frame

    def release(self):
        self.process.terminate()



import os
import time
import threading
import numpy as np
import cv2
import av
import serial
import minireader
from queue import Queue
from openni import openni2
from RppgCollector import RppgCollector
from xep import xep
from typing import List, Tuple, Dict
from pygrabber.dshow_graph import FilterGraph
av.logging.set_level(av.logging.ERROR)

class BaseDevice:
    devices : Dict[str, 'BaseDevice'] = {}
    devices_start_timestamp : Dict[str, float] = {}
    recording : bool = False
    write_thread : threading.Thread = None
    save_dir : str = None
    def __init__(self, device_name, frame_rate = 30):
        self.device_name = device_name
        self.frame_rate = frame_rate
        self.meta_info = None
        self.frame_count = 0
        self.one_frame = None
        self.buffer_size = frame_rate
        self.buffer = Queue(maxsize=self.buffer_size)
        self.buffer_len = 90
        self.thread = None
        self.running = False  # 线程运行标志
        BaseDevice.devices[device_name] = self

    def start(self):
        """启动采集线程，采集数据不断进行"""
        print(f"[{self.device_name}] 开始采集...")
        self.running = True
        self.thread = threading.Thread(target=self._collect_loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        """停止采集线程"""
        self.running = False
        if self.thread:
            self.thread.join()
        try:
            self.release()
        except:
            pass
    
    def record(self):
        self.reading_buffer = True
        while BaseDevice.recording:
            try:
                frame, timestamp = self.buffer.get(timeout=1)
                self.data[self.frame_count] = frame
                self.timestamps.append(timestamp)
                self.frame_count += 1
            except:
                continue
        self.reading_buffer = False

    @staticmethod
    def start_record(record_duration : float = 5):
        """开始保存数据"""
        for device in BaseDevice.devices.values():
            device.ini_data_buffer()
            print(f"[{device.device_name}] 开始录制...")
        BaseDevice.recording = True
        for device in BaseDevice.devices.values():
            threading.Thread(target=lambda: device.record(), daemon=True).start()
        # time.sleep(2)
        # BaseDevice.write_thread = threading.Thread(target=BaseDevice.save_data_block, args=(record_duration,), daemon=True)
        # BaseDevice.write_thread.start()

    @staticmethod
    def stop_record():
        """停止保存数据并写入文件"""
        BaseDevice.recording = False
        for device in BaseDevice.devices.values():
            print(f"[{device.device_name}] 停止录制...")

    @staticmethod
    def get_latest_start_timestamp():
        all_start_timestamp = [BaseDevice.devices_start_timestamp[device_name] for device_name in BaseDevice.devices.keys()]
        latest_start_timestamp = max(all_start_timestamp)
        return latest_start_timestamp

    @staticmethod
    def register_user_meta_data(save_dir,user_name,user_state):
        BaseDevice.save_floder = os.path.join(save_dir,user_name,user_state)
        print(f"保存路径为：{BaseDevice.save_floder}")
        os.makedirs(BaseDevice.save_floder, exist_ok=True)

    @staticmethod
    def stop_all():
        for device in BaseDevice.devices.values():
            device.stop()

    def save_data_block(duration):
        latest_start_timestamp = BaseDevice.get_latest_start_timestamp()
        while True:
            if time.time() - latest_start_timestamp < duration:
                continue
            else:
                end_timestamp = time.time()
                for device in BaseDevice.devices.values():
                    print(device.device_name)
                    device.save_data(latest_start_timestamp, end_timestamp)
                BaseDevice.devices_start_timestamp = {}
                time.sleep(2)
                latest_start_timestamp = BaseDevice.get_latest_start_timestamp()

    def save_data(self, start_timestamp = None , end_timestamp = None):
        if start_timestamp is None:
            threading.Thread(target=lambda: self._save_data_all(), daemon=True).start()
        else:
            threading.Thread(target=lambda: self._save_data(start_timestamp,end_timestamp), daemon=True).start()

    def _save_data(self, start_timestamp = None, end_timestamp = None):

        start = time.time()
        if not self.data:
            print(f"[{self.device_name}] 无数据保存")
            return
        print(BaseDevice.save_floder)
        print(BaseDevice.save_dir)
        folder = os.path.join(BaseDevice.save_floder,self.device_name)
        folder = os.path.join(BaseDevice.save_dir, folder)
        os.makedirs(folder, exist_ok=True)

        data_array = np.stack(self.data)
        # 找到最近的起始时间戳
        if start_timestamp is None:
            start_index = 0
            end_index = len(data_array)
        else:
            start_index = np.searchsorted(self.timestamps, start_timestamp)
            end_index = np.searchsorted(self.timestamps, end_timestamp)
        data_array = data_array[start_index:end_index]
        self.ini_data_buffer(end_index)
        filename = os.path.join(folder, f"{start_timestamp}f{self.frame_rate}c{end_index-start_index}.npz")
        # 保存多个变量
        np.savez_compressed(
            filename,
            frames=data_array,
        )
        print(f"[{self.device_name}] 数据保存到 {filename}, 帧长度为{len(data_array)}，整体耗时：{time.time() - start:.4f}s")

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
            begin = self.timestamps[0],
            frames=self.data[:l],
            meta_info=self.meta_info
        )
        print(f"[{self.device_name}] 数据保存到 {filename}, 帧长度为{l}，整体耗时：{time.time() - start:.4f}s")
        del self.data
        del self.timestamps
        self.ini_data_buffer()

    def register_start_timestamp(self,timestamp):
        if self.device_name not in BaseDevice.devices_start_timestamp.keys():
            BaseDevice.devices_start_timestamp[self.device_name] = timestamp
        return 
    
    def ini_data_buffer(self, index = None):
        self.frame_count = 0
        self.frame_size = self.one_frame.shape
        self.frame_dtype = self.one_frame.dtype
        if index:
            if len(self.data) > index+1:
                self.data = self.data[index+1:]
                self.timestamps = self.timestamps[index+1:]
                return
        self.data = np.zeros((self.frame_rate*self.buffer_len, *self.frame_size), dtype=self.frame_dtype)
        self.timestamps = []
        
    def put_data_to_buffer(self, data_tuple):
        if self.buffer.qsize() == self.buffer.maxsize:
            print(f"[{self.device_name}] buffer is full, drop one frame")
            self.buffer.get()
        self.buffer.put(data_tuple)

    def set_save_dir(self, save_dir):
        self.save_dir = save_dir

    def _collect_loop(self) -> any:
        raise NotImplementedError
    
    def get_current_data(self) -> np.array:
        raise NotImplementedError
    
    def release(self) -> any:
        raise NotImplementedError

class VideoDevice(BaseDevice):
    def __init__(self, **kwargs):
        device_name = kwargs.get("device_name")
        camera_name = kwargs.get("camera_name")
        frame_size = kwargs.get("frame_size")
        frame_rate = kwargs.get("frame_rate")
        encode_type = kwargs.get("encode_type")
        meta_info = kwargs.get("meta_info")
        rtbufsize = kwargs.get("rtbufsize")
        super().__init__(device_name, frame_rate=frame_rate)
        self.frame_rate = round(frame_rate)
        self.meta_info = meta_info if meta_info else {}
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
        self.start()

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
        self.frame_max_size = int(self.frame_size*1.5)
        self.data = []
        self.timestamps = []
        self.frame_lens = []

    def get_size(self):
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
                self.data.append(frame_bytes.ljust(self.frame_max_size, b'\x00'))
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
        self.start()

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

class PPGDevice(BaseDevice):
    def __init__(self, **kwargs):
        device_name = kwargs.get("device_name")
        frame_rate = kwargs.get("frame_rate", 1000)
        meta_info = kwargs.get("meta_info")
        port = kwargs.get("port")
        super().__init__(device_name, frame_rate=frame_rate)
        self.ch1_show = []
        self.ch2_show = []
        self.meta_info = meta_info if meta_info else {}
        self.port = port
        self.show_time = 3
        self.show_window = self.show_time * self.frame_rate
        self.rppg_collector = None
        self.start()

    def _collect_loop(self):
        self.rppg_collector = RppgCollector(self.port)
        while self.running:
            try:
                data = self.rppg_collector.read()  # 返回[(ch1,ch2,ch3,timestamp),(ch1,ch2,ch3,timestamp),(ch1,ch2,ch3,timestamp),(ch1,ch2,ch3,timestamp)] 长度为4
                if data is None:
                    print(f"[{self.device_name}] 读取帧失败")
                    continue
                if self.one_frame is None:
                    self.one_frame = np.array([data[0][0],data[0][1]])
                ch1 = [d[0] for d in data]
                ch2 = [d[1] for d in data]
                ch = [[d[0],d[1]] for d in data]
                timestamp = [d[3] for d in data]
                self.ch1_show.extend(ch1)
                self.ch2_show.extend(ch2)
                if len(self.ch1_show) > self.show_window:
                    self.ch1_show = self.ch1_show[-self.show_window:]
                    self.ch2_show = self.ch2_show[-self.show_window:]
            except Exception:
                print(f"[{self.device_name}] 读取帧失败")
            finally:
                if BaseDevice.recording:
                    self.put_data_to_buffer((ch,timestamp))
    
    def record(self):
        self.reading_buffer = True
        while BaseDevice.recording:
            try:
                frame, timestamp = self.buffer.get(timeout=1)
                self.data[self.frame_count:self.frame_count+len(frame)] = frame
                self.timestamps.extend(timestamp)
                self.frame_count += len(frame)
            except:
                continue
        self.reading_buffer = False

    def get_current_data(self):
        return self.get_current_data_help()
    
    def get_current_data_help(self):
        width, height = 560, 420
        img = np.zeros((height, width, 3), dtype=np.uint8) 
        length = len(self.ch1_show)
        if length == 0:
            return img 

        ch1_data = np.array(self.ch1_show[::5])
        ch2_data = np.array(self.ch2_show[::5])

        min_val1, max_val1 = np.min(ch1_data), np.max(ch1_data)
        min_val2, max_val2 = np.min(ch2_data), np.max(ch2_data)
        if max_val1 == min_val1:
            max_val += 1  # 防止除零
        if max_val2 == min_val2:
            max_val += 1  # 防止除零

        scale1 = (height * 0.8) / (max_val1 - min_val1)
        offset1 = height * 0.1

        scale2 = (height * 0.8) / (max_val2 - min_val2)
        offset2 = height * 0.1


        ch1_y = height - ((ch1_data - min_val1) * scale1 + offset1).astype(np.int32)
        ch2_y = height - ((ch2_data - min_val2) * scale2 + offset2).astype(np.int32)

        x = np.arange(length//5)

        for i in range(length//5 - 1):
            cv2.line(img, (x[i], ch1_y[i]), (x[i+1], ch1_y[i+1]), (0, 255, 0), 1) 
            cv2.line(img, (x[i], ch2_y[i]), (x[i+1], ch2_y[i+1]), (0, 0, 255), 1)  

        cv2.putText(img, 'CH1', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)
        cv2.putText(img, 'CH2', (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)

        return img
        
    def release(self):
        self.rppg_collector.close()
        
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
        self.start()
    
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
        
class MilliWaveDevice(BaseDevice):
    def __init__(self, **kwargs):
        device_name = kwargs.get("device_name")
        frame_rate = kwargs.get("frame_rate", 10)
        meta_info = kwargs.get("meta_info")
        port = kwargs.get("port")
        baud_rate = kwargs.get("baud_rate", 2000000)
        super().__init__(device_name, frame_rate=frame_rate)
        self.device_name = device_name
        self.meta_info = meta_info
        self.port = port
        self.baud_rate = baud_rate
        self.start()
    
    def ini_serial(self):
        self.ser = ser = serial.Serial(self.port, self.baud_rate, timeout=1) 
        time.sleep(2) 

        self.ser.write(b"AT+RESET\n")
        print(f"发送 AT+RESET\\n 命令到 {self.port}...")
        time.sleep(10)  # 等待设备重置
        while 1:
            response2 = ser.read(ser.in_waiting)
            print(f"串口响应: {response2.decode('utf-8')}")
            if response2:
                break
            else:
                time.sleep(1)

        ser.write(b"AT+START\n")
        print(f"发送 AT+START\\n 命令到 {self.port}...")
        time.sleep(10)  # 等待设备启动
        while 1:
            response3 = ser.read(ser.in_waiting)
            print(f"串口响应: {response3.decode('utf-8')}")
            if response3:
                break
            else:
                time.sleep(1)
        print(f"AT命令发送完成")
        
    def _collect_loop(self):
        self.ini_serial()
        self.collector =minireader.DataCollector()
        if self.collector.init():
            print("初始化成功")
        else:
            print("初始化失败")
            return
        self.collector.start()
        while self.running:
            frame = self.collector.getData()
            timestamp = time.time()
            if frame is None:
                continue
            if self.one_frame is None:
                self.one_frame = np.array(frame)
            self.current = np.array(frame)
            if BaseDevice.recording:
                self.put_data_to_buffer((frame, timestamp))
    
    def get_current_data(self):
        return self.get_current_data_help()

    def get_current_data_help(self):
        if self.current is None:
            return np.zeros((420, 560), dtype=np.uint8)
        else:
            # (1024x1024,) -> (1024, 1024)
            frame = self.current.reshape((1024, 1024))
            # 标注字样“MilliWave”在图片
            frame = cv2.putText(frame, "MilliWave", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            return self.current.reshape((1024, 1024))

    def release(self):
        while 1:
            self.ser.write(b"AT\n")
            time.sleep(2)
            response = self.ser.read(self.ser.in_waiting)
            print(f"串口响应: {response.decode('utf-8')}")
            if response:
                break
        self.collector.stop()
        self.ser.close()

class IRDevice(BaseDevice):
    
    def __init__(self, **kwargs):
        device_name = kwargs.get("device_name")
        camera_name = kwargs.get("camera_name")
        frame_rate = kwargs.get("frame_rate", 30)
        frame_size = kwargs.get("frame_size", (1080, 1920, 3))
        meta_info = kwargs.get("meta_info")
        super().__init__(device_name, frame_rate=frame_rate)
        self.device_name = device_name
        self.frame_size = frame_size
        self.meta_info = meta_info
        self.camera_name = camera_name
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
        self.start()

    def _collect_loop(self):
        
        self.cap = cv2.VideoCapture(self.idx)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.w)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.h)
        self.cap.set(cv2.CAP_PROP_FPS, self.frame_rate)
        #设置曝光和焦距
        self.cap.set(cv2.CAP_PROP_EXPOSURE, -6)
        self.cap.set(cv2.CAP_PROP_FOCUS, 0)
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
            return cv2.imencode('.jpg', frame[:,:,0], [cv2.IMWRITE_JPEG_QUALITY, 95])[1]
        
    def get_current_data(self):
        if self.current is None:
            return np.zeros((self.h, self.w), dtype=np.uint8)
        else:
            return self.current[:,:,0]
    
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
    

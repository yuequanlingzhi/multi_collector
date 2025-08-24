import os
import time
import threading
import numpy as np
from queue import Queue
from typing import List, Tuple, Dict

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
    def start_devices():
        for device in BaseDevice.devices.values():
            device.start()

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
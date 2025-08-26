import time
# import minireader
import cv2
import threading
import numpy as np
from BaseDevice.BaseDevice import BaseDevice
from multiprocessing import Process, Queue
import minireader  
import serial

class MilliWaveDevice(BaseDevice):
    def __init__(self, **kwargs):
        device_name = kwargs.get("device_name")
        frame_rate = kwargs.get("frame_rate", 10)
        port = kwargs.get("port")
        baud_rate = kwargs.get("baud_rate", 2000000)
        super().__init__(device_name, frame_rate=frame_rate)
        self.device_name = device_name
        self.port = port
        self.baud_rate = baud_rate
        self.current = None
        self.running = True

        self.data_queue = Queue(maxsize=1)
        self.command_queue = Queue(maxsize=1)
        self.worker_process = None
        
            
    def _collect_loop(self):
        print(f"[{self.device_name}] 开始采集线程...")
        self.init_serial()
        self.collector = minireader.DataCollector()
        self.collector.set_frame_size(65536)
        if self.collector.init():
            print("设备初始化成功")
        else:
            print("设备初始化失败")
        self.collector.start()
        # time.sleep(2)        
        while self.running:
            try:
                frame = self.collector.getData()
                timestamp = time.time()
                if frame is None or len(frame) < 10:
                    continue
                if self.one_frame is None:
                    self.one_frame = np.array(frame, dtype=np.uint8)
                    
                self.current = frame[:280*210]
                if BaseDevice.recording:
                    self.put_data_to_buffer((frame, timestamp))
            except Exception as e:
                pass
    
    def init_serial(self):
        self.ser = serial.Serial(self.port, self.baud_rate, timeout=1) 
        time.sleep(2) 

        self.ser.write(b"AT+RESET\n")
        print(f"发送 AT+RESET\\n 命令到 {self.port}...")
        time.sleep(2)  # 等待设备重置
        while 1:
            response2 = self.ser.read(self.ser.in_waiting)
            print(f"串口响应: {response2.decode('utf-8')}")
            if response2:
                break
            else:
                time.sleep(1)

        self.ser.write(b"AT+START\n")
        print(f"发送 AT+START\\n 命令到 {self.port}...")
        time.sleep(2)  # 等待设备启动
        print(f"AT命令发送完成")

    def get_current_data(self):
        if self.current is None:
            return np.zeros((210, 280), dtype=np.uint8)
        else:
            frame = np.fromiter(self.current, dtype=np.uint8, count=210*280)
            frame = frame.reshape((210,280))
            return frame

    def release(self):
        while 1:
            self.ser.write(b"AT\n")
            time.sleep(2)
            response = self.ser.read(self.ser.in_waiting)
            print(f"串口响应: {response.decode('utf-8')}")
            if response:
                break
        # 向子进程发送停止命令
        if self.worker_process and self.worker_process.is_alive():
            print(f"[{self.device_name}] 向子进程发送停止命令...")
            self.command_queue.put("STOP")
            self.worker_process.join(timeout=5)  # 等待最多5秒
            if self.worker_process.is_alive():
                print(f"[{self.device_name}] 子进程未正常退出，强制终止...")
                self.worker_process.terminate()  # 强制终止
                self.worker_process.join()
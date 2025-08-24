import serial
import time
import minireader
import cv2
import numpy as np
from BaseDevice.BaseDevice import BaseDevice

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
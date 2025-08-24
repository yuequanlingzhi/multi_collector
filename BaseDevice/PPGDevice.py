import cv2
import numpy as np
from BaseDevice.util.RppgCollector import RppgCollector
from BaseDevice.BaseDevice import BaseDevice

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
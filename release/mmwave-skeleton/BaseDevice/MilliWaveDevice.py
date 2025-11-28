import numpy as np
import time
import threading
from queue import Queue, Empty
from .BaseDevice import BaseDevice
from .util.MilliWaveReader import MilliWaveReader
from .util.PointCloudVisualizer import PointCloudVisualizer

class MilliWaveDevice(BaseDevice):
    def __init__(self, device_name, frame_rate = 5, port = "COM3", baudrate = 3000000, save_points_len = 200, max_save_time = 120):
        super().__init__(device_name, frame_rate)
        self.reader = MilliWaveReader(port, baudrate, radar_inclination=0)
        self.save_points_len = save_points_len
        self.max_save_time = max_save_time
        self.current = None  # 存储当前渲染的图片（RGB图像）
        self.current_points = None  # 存储当前点云数据（用于录制）
        self.released = False  # 标志位：是否已释放资源
        
        # 点云数据缓冲区，用于图像生成线程（增大缓冲区，减少丢帧）
        self.points_buffer = Queue(maxsize=10)
        
        # 图像生成线程相关
        self.image_thread = None
        self.image_thread_running = False
        self.visualizer = None  # 将在图像生成线程中初始化

    def _collect_loop(self):
        self.reader.start()
        # 启动图像生成线程
        self._start_image_thread()
        
        while self.running:
            data = self.reader.read()
            if data is None:
                if not self.running:
                    break
                time.sleep(0.1) 
                continue
            tmp = np.zeros((6, self.save_points_len, 5), dtype=data[0].dtype)
            timestamp = time.time()
            for i in range(6):
                point_len = data[i].shape[0]
                tmp[i, :min(point_len, self.save_points_len), :] = data[i][:min(point_len, self.save_points_len), :]
            
            # 保存点云数据用于录制
            self.current_points = tmp
            if self.one_frame is None:
                self.one_frame = tmp
            
            # 将点云数据放入缓冲区，供图像生成线程使用
            if not self.points_buffer.full():
                self.points_buffer.put(tmp)
            else:
                # 缓冲区满时，丢弃最旧的数据，放入新数据
                try:
                    self.points_buffer.get_nowait()
                    self.points_buffer.put(tmp)
                except:
                    pass
            
            if BaseDevice.recording and self.allow_record:
                self.put_data_to_buffer((tmp, timestamp))

    def _start_image_thread(self):
        """启动图像生成线程"""
        if self.image_thread_running:
            return
        self.image_thread_running = True
        self.image_thread = threading.Thread(target=self._image_generation_loop, daemon=True)
        self.image_thread.start()
    
    def _image_generation_loop(self):
        """
        图像生成线程的主循环
        在该线程中初始化visualizer，确保所有Open3D操作都在同一线程中执行
        """
        # 在该线程中初始化可视化器
        self.visualizer = PointCloudVisualizer()
        
        while self.image_thread_running and not self.released:
            try:
                # 从缓冲区获取点云数据（优先处理最新数据）
                # 如果缓冲区有多个数据，快速清空旧数据，只处理最新的
                points_data = None
                # 先尝试非阻塞获取，丢弃旧数据
                while True:
                    try:
                        points_data = self.points_buffer.get_nowait()
                    except Empty:
                        # 缓冲区为空，跳出循环，处理最后一个获取到的数据
                        break
                
                # 如果没有获取到数据（缓冲区为空），等待新数据
                if points_data is None:
                    try:
                        points_data = self.points_buffer.get(timeout=0.1)
                    except Empty:
                        # 超时，继续外层循环
                        continue
                
                # 生成图像
                image = self._generate_image(points_data)
                
                # 更新current（线程安全，因为只有一个线程写入）
                if image is not None:
                    self.current = image
                    
            except Exception as e:
                # 其他异常，记录但继续循环
                print(f"[{self.device_name}] 图像生成异常: {e}")
                continue
        
        # 线程结束时释放可视化器
        if self.visualizer is not None:
            self.visualizer.release()
            self.visualizer = None
    
    def get_current_data(self):
        """获取当前数据，直接返回current"""
        # 如果已释放，直接返回None
        if self.released:
            return None
        return self.current
    
    def _generate_image(self, points_data):
        """
        从点云数据生成RGB图像
        points_data: shape (6, save_points_len, 5) - [x, y, z, snr, velocity]
        只显示 points_data[0] (dynamic_high) 和 points_data[4] (short_micro_high)
        注意：此方法在图像生成线程中执行
        """
        if self.visualizer is None:
            return None
        
        # 提取需要显示的点云数据
        dynamic_high = points_data[0]  # shape: (save_points_len, 5)
        short_micro_high = points_data[4]  # shape: (save_points_len, 5)
        
        # 过滤掉补零点（全为0的点）
        def filter_zero_points(points):
            """过滤掉全为0的点"""
            valid_mask = np.any(points[:, :3] != 0, axis=1)  # 检查x,y,z是否不全为0
            return points[valid_mask]
        
        dynamic_high = filter_zero_points(dynamic_high)
        short_micro_high = filter_zero_points(short_micro_high)
        
        # 转换坐标：从毫米(0.001m)转换为米，并提取x,y,z
        points_dynamic = None
        points_short = None
        
        if len(dynamic_high) > 0:
            points_dynamic = dynamic_high[:, :3].astype(np.float64) / 1000.0  # 转换为米
        
        if len(short_micro_high) > 0:
            points_short = short_micro_high[:, :3].astype(np.float64) / 1000.0  # 转换为米
        
        # 更新点云
        self.visualizer.update_points(points_dynamic=points_dynamic, points_short=points_short)
        
        # 获取图像
        image_rgb = self.visualizer.get_image()
        
        return image_rgb

    def release(self):
        # 设置释放标志，防止后续调用
        self.released = True
        
        # 停止图像生成线程
        self.image_thread_running = False
        if self.image_thread is not None:
            self.image_thread.join(timeout=2.0)
        
        # 释放可视化器资源（如果还在，说明线程可能异常退出）
        if self.visualizer is not None:
            self.visualizer.release()
            self.visualizer = None
        
        # 释放reader资源
        if self.reader is not None:
            self.reader.release()

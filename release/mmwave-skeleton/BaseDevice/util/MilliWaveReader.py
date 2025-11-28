import threading
import serial
import time
import queue
import struct
import numpy as np
class MilliWaveReader():
    # 帧头常量（小端序接收）
    FRAME_HEADER_MAGIC = b'\xDC\xFF\xEE\xFF'      # 0xFFEEFFDC 小端
    POINTCLOUD_HEADER_MAGIC = b'\xCB\xFE\xDD\xFF'  # 0xFFDDFECB 小端
    TRACK_HEADER_MAGIC = b'\xBA\xFD\xCC\xFF'       # 0xFFCCFDBA 小端

    FRAME_FOOTER_MAGIC = b'\xD3\xFF\xEE\xFF'       # 0xFFEEFFD3 小端
    POINTCLOUD_FOOTER_MAGIC = b'\xC4\xFE\xDD\xFF'  # 0xFFDDFEC4 小端
    TRACK_FOOTER_MAGIC = b'\xB5\xFD\xCC\xFF'       # 0xFFCCFDB5 小端
    def __init__(self,port,baudrate=3000000,log=False,sleep_time=0.1,
                 radar_height=None, radar_inclination=None, boundary=None,
                 mms_interval=None, cfar_coeff=None):
        try:
            self.ser = serial.Serial(port,baudrate,timeout=0.1)
            self.port = port
        except Exception as e:
            print(f"串口打开失败: {e}")
            return None
        self.log = log
        self.buffer = b''
        self.data_queue = queue.Queue(maxsize=3)
        self.running = False
        self.sleep_time = sleep_time
        
        # 保存配置参数
        self.radar_height = radar_height
        self.radar_inclination = radar_inclination
        self.boundary = boundary  # (x_min, x_max, y_min, y_max, z_min, z_max)
        self.mms_interval = mms_interval  # (long_interval, short_interval)
        self.cfar_coeff = cfar_coeff  # (dynamic_coeff, short_micro_coeff, long_micro_coeff)
    
    def send_command(self, command):
        """发送命令到雷达"""
        try:
            cmd_bytes = (command + "\r\n").encode('utf-8')
            self.ser.write(cmd_bytes)
            print(f"发送命令到 {self.port}: {command}")
            time.sleep(0.1)  # 等待命令执行
            return True
        except Exception as e:
            print(f"发送命令失败: {e}")
            return False
    
    def configure(self, radar_height=None, radar_inclination=None, boundary=None,
                  mms_interval=None, cfar_coeff=None):
        """
        配置雷达参数
        
        参数:
            radar_height: 雷达安装距离地面的高度（米）
            radar_inclination: 安装倾斜角度（度）
            boundary: 点云输出范围，元组 (x_min, x_max, y_min, y_max, z_min, z_max)（米）
            mms_interval: 微动点处理间隔，元组 (long_interval, short_interval)（帧）
            cfar_coeff: 检测门限系数，元组 (dynamic_coeff, short_micro_coeff, long_micro_coeff)
        """
        # 使用传入的参数，如果没有则使用实例变量中的默认值
        radar_height = radar_height if radar_height is not None else self.radar_height
        radar_inclination = radar_inclination if radar_inclination is not None else self.radar_inclination
        boundary = boundary if boundary is not None else self.boundary
        mms_interval = mms_interval if mms_interval is not None else self.mms_interval
        cfar_coeff = cfar_coeff if cfar_coeff is not None else self.cfar_coeff
        
        # 1. 设置雷达安装高度
        if radar_height is not None:
            self.send_command(f"set radar_height {radar_height}")
        
        # 2. 设置安装倾斜角度
        if radar_inclination is not None:
            self.send_command(f"set radar_inclination {radar_inclination}")
        
        # 3. 设置点云输出范围
        if boundary is not None:
            x_min, x_max, y_min, y_max, z_min, z_max = boundary
            self.send_command(f"set boundary {x_min} {x_max} {y_min} {y_max} {z_min} {z_max}")
        
        # 4. 设置微动点处理间隔
        if mms_interval is not None:
            long_interval, short_interval = mms_interval
            self.send_command(f"set_mmsinterval {long_interval} {short_interval}")
        
        # 5. 设置检测门限系数
        if cfar_coeff is not None:
            dynamic_coeff, short_micro_coeff, long_micro_coeff = cfar_coeff
            self.send_command(f"set_cfar_coeff {dynamic_coeff} {short_micro_coeff} {long_micro_coeff}")
    
    def start(self, auto_configure=True):
        """
        启动雷达数据采集
        
        参数:
            auto_configure: 是否自动应用配置参数（默认True）
        """
        # 如果启用自动配置，先发送配置命令
        if auto_configure:
            self.configure()
        
        self.running = True
        threading.Thread(target=self.read_loop).start()
        threading.Thread(target=self.parse_loop).start()
        self.send_command("scan start")
        
    
    def stop(self):
        self.ser.write(b"scan stop\r\n")
        print(f"发送 scan stop\\n 命令到 {self.port}...")
        self.running = False
    
    def read_loop(self):
        while self.running:
            try:
                data = self.ser.read(self.ser.in_waiting)
                if not data:
                    time.sleep(self.sleep_time)
                    continue
                if self.log:
                    print(f"读取数据: {data.hex()}")
                self.buffer += data
                if self.log:
                    print(f"buffer:{self.buffer.hex()}")
            except Exception as e:
                print(f"读取数据失败: {e}")

    def parse_loop(self):
        while self.running:
            if not self.buffer:
                time.sleep(self.sleep_time)
                if self.log:
                    print("没有数据")
                continue

            # 查找帧头
            frame_header_idx = self.buffer.find(self.FRAME_HEADER_MAGIC)
            if frame_header_idx == -1:
                # 没找到帧头，保留最后可能的部分数据
                if len(self.buffer) > 100:
                    self.buffer = self.buffer[-100:]
                time.sleep(self.sleep_time)
                if self.log:
                    print(f"没有帧头在buffer:{self.buffer.hex()}中")
                continue
            
            # 丢弃帧头前的数据
            if frame_header_idx > 0:
                self.buffer = self.buffer[frame_header_idx:]
            
            # 检查是否有足够的数据解析帧头包（至少需要帧头+帧头包数据+帧尾）
            # 帧头包：包头(4) + 数据(16) + 包尾(4) = 24字节
            if len(self.buffer) < 24:
                time.sleep(self.sleep_time)
                if self.log:
                    print("没有足够的数据解析帧头包")
                continue
            
            try:
                # 解析帧头包
                # 跳过帧头(4字节)
                offset = 4
                
                # 第1个32位字：帧周期(bit0~9), 动态高置信度点数(bit10~19), Reserved(bit20~31)
                word1 = struct.unpack('<I', self.buffer[offset:offset+4])[0]
                offset += 4
                frame_period = word1 & 0x3FF  # bit0~9
                dynamic_high_count = (word1 >> 10) & 0x3FF  # bit10~19
                
                # 帧号：32位
                frame_number = struct.unpack('<I', self.buffer[offset:offset+4])[0]
                offset += 4
                
                # 第2个32位字：动态低置信度点数(bit0~9), 跟踪航迹数(bit10~19), 长时微动高置信度点数(bit20~29), Reserved(bit30~31)
                word2 = struct.unpack('<I', self.buffer[offset:offset+4])[0]
                offset += 4
                dynamic_low_count = word2 & 0x3FF  # bit0~9
                track_count = (word2 >> 10) & 0x3FF  # bit10~19
                long_micro_high_count = (word2 >> 20) & 0x3FF  # bit20~29
                
                # 第3个32位字：长时微动低置信度点数(bit0~9), 短时微动高置信度点数(bit10~19), 短时微动低置信度点数(bit20~29), Reserved(bit30~31)
                word3 = struct.unpack('<I', self.buffer[offset:offset+4])[0]
                offset += 4
                long_micro_low_count = word3 & 0x3FF  # bit0~9
                short_micro_high_count = (word3 >> 10) & 0x3FF  # bit10~19
                short_micro_low_count = (word3 >> 20) & 0x3FF  # bit20~29
                
                # 第4个32位字：处理时间等（跳过）
                offset += 4
                
                # 检查帧尾
                if self.buffer[offset:offset+4] != self.FRAME_FOOTER_MAGIC:
                    # 帧尾不匹配，可能是数据错误，丢弃帧头
                    self.buffer = self.buffer[4:]
                    if self.log:
                        print("帧尾不匹配，丢弃帧头")
                    continue
                
                # 跳过帧头包
                frame_header_size = offset + 4
                self.buffer = self.buffer[frame_header_size:]
                
                # 查找点云包头
                pointcloud_header_idx = self.buffer.find(self.POINTCLOUD_HEADER_MAGIC)
                if pointcloud_header_idx == -1:
                    time.sleep(self.sleep_time)
                    if self.log:
                        print("没有点云包头")
                    continue
                
                # 丢弃点云包头前的数据
                if pointcloud_header_idx > 0:
                    self.buffer = self.buffer[pointcloud_header_idx:]
                
                # 计算点云包总大小
                # 点云包头(4) + 所有点数据 + 点云包尾(4)
                # 每个点：X(2) + Y(2) + Z(2) + SNR(2) + 速度(2) = 10字节
                total_points = (dynamic_high_count + dynamic_low_count + 
                               long_micro_high_count + long_micro_low_count + 
                               short_micro_high_count + short_micro_low_count)
                pointcloud_packet_size = 4 + total_points * 10 + 4
                
                if len(self.buffer) < pointcloud_packet_size:
                    time.sleep(self.sleep_time)
                    if self.log:
                        print("没有足够的数据解析点云包")
                    continue
                
                # 跳过点云包头
                offset = 4
                
                # 解析各种点云数据
                def parse_points(count):
                    nonlocal offset
                    points = []
                    for _ in range(count):
                        if offset + 10 > len(self.buffer):
                            if self.log:
                                print(f"数据不足，需要{offset+10}字节，但只有{len(self.buffer)}字节")
                            break
                        x = struct.unpack('<h', self.buffer[offset:offset+2])[0]  # int16, 单位0.001m
                        y = struct.unpack('<h', self.buffer[offset+2:offset+4])[0]  # int16, 单位0.001m
                        z = struct.unpack('<h', self.buffer[offset+4:offset+6])[0]  # int16, 单位0.001m
                        snr = struct.unpack('<H', self.buffer[offset+6:offset+8])[0]  # uint16
                        velocity = struct.unpack('<h', self.buffer[offset+8:offset+10])[0]  # int16, 单位0.1m/s
                        points.append([x, y, z, snr, velocity])
                        offset += 10
                    return np.array(points) if points else np.empty((0, 5))
                
                dynamic_high = parse_points(dynamic_high_count)
                dynamic_low = parse_points(dynamic_low_count)
                long_micro_high = parse_points(long_micro_high_count)
                long_micro_low = parse_points(long_micro_low_count)
                short_micro_high = parse_points(short_micro_high_count)
                short_micro_low = parse_points(short_micro_low_count)
                
                # 检查点云包尾
                if offset + 8 <= len(self.buffer):
                    if self.buffer[offset+4:offset+8] == self.POINTCLOUD_FOOTER_MAGIC:
                        # 解析成功，跳过点云包
                        self.buffer = self.buffer[offset+8:]
                        
                        # 将数据放入队列
                        data = (dynamic_high, dynamic_low, long_micro_high, 
                               long_micro_low, short_micro_high, short_micro_low)
                        if not self.data_queue.full():
                            self.data_queue.put(data)
                            if self.log:
                                print(f"成功解析一帧数据: 动态高={len(dynamic_high)}, 动态低={len(dynamic_low)}, "
                                      f"长微动高={len(long_micro_high)}, 长微动低={len(long_micro_low)}, "
                                      f"短微动高={len(short_micro_high)}, 短微动低={len(short_micro_low)}")
                    else:
                        # 包尾不匹配，丢弃点云包头，重新查找
                        if self.log:
                            print(f"点云包尾不匹配，期望{self.POINTCLOUD_FOOTER_MAGIC.hex()}，"
                                  f"实际{self.buffer[offset:offset+4].hex()}")
                        self.buffer = self.buffer[4:]
                else:
                    time.sleep(self.sleep_time)
                    if self.log:
                        print(f"数据不足检查包尾，需要{offset+4}字节，但只有{len(self.buffer)}字节")
                    continue
                    
            except (struct.error, IndexError) as e:
                # 解析错误，丢弃帧头
                if self.log:
                    print(f"解析错误: {e}, 丢弃帧头，buffer长度: {len(self.buffer)}")
                if len(self.buffer) > 4:
                    self.buffer = self.buffer[4:]
                else:
                    self.buffer = b''
                continue
            except Exception as e:
                # 其他未知错误
                if self.log:
                    print(f"未知错误: {e}, 类型: {type(e).__name__}")
                if len(self.buffer) > 4:
                    self.buffer = self.buffer[4:]
                else:
                    self.buffer = b''
                continue
    
    def read(self, timeout=None):
        try:
            if timeout is None:
                data = self.data_queue.get_nowait()
            else:
                # 使用超时等待，但在等待期间检查running状态
                data = self.data_queue.get(timeout=timeout)
            return data
        except queue.Empty:
            return None

    def release(self):
        self.running = False
        self.stop()
        if hasattr(self, 'ser') and self.ser.is_open:
            self.ser.close()

import serial
import struct
import threading
import time
import queue
from typing import Tuple, Optional

class RppgCollector:
    SERIAL_PORT = 'COM3'
    BAUD_RATE = 256000
    FRAME_HEADER = b'\xCC\xCC'
    FRAME_SIZE = 8  # 2字节头 + 6字节数据 (3个short)
    MAX_QUEUE_SIZE = 30  # 最大缓存帧数，避免内存堆积

    def __init__(self, port=None, baudrate=None, max_queue_size=None):
        self.port = port or self.SERIAL_PORT
        self.baudrate = baudrate or self.BAUD_RATE
        self.ser = None
        self.buffer = bytearray()
        self.data_queue = queue.Queue(maxsize=max_queue_size or self.MAX_QUEUE_SIZE)
        self.running = True
        self.thread = None
        self.base_time = time.time()-time.perf_counter()

        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
            print(f"已连接到 {self.port} @ {self.baudrate}")
        except Exception as e:
            raise RuntimeError(f"无法打开串口 {self.port}: {e}")

        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()

    def _read_loop(self):
        while self.running:
            try:
                # 尝试读取可用数据，最小读1字节避免空循环
                data = self.ser.read(8)
                if data:
                    self.buffer.extend(data)

                if len(self.buffer) < self.FRAME_SIZE:
                    continue

                else:
                    idx = self.buffer.find(self.FRAME_HEADER)
                    if idx == -1:
                        self.buffer.clear()
                        continue
                    if idx > 0:
                        self.buffer = self.buffer[idx:]
                    while len(self.buffer) >= self.FRAME_SIZE:
                        frame_data = self.buffer[:self.FRAME_SIZE]
                        timestamp = time.perf_counter()
                        self.buffer = self.buffer[self.FRAME_SIZE:]
                        ch1, ch2, ch3 = struct.unpack('>hhh', frame_data[2:8])
                        # print(ch1, ch2, ch3, frame_data[2:4], frame_data[4:6], frame_data[6:8])
                        frame = (ch1, ch2, ch3, timestamp+self.base_time)
                        if self.data_queue.full():
                            self.data_queue.get()
                        self.data_queue.put(frame)

                # 尝试解析帧
                # while len(self.buffer) >= self.FRAME_SIZE:
                #     # 查找帧头
                #     idx = self.buffer.find(self.FRAME_HEADER)
                #     if idx == -1:
                #         # 没找到帧头，保留最后 FRAME_SIZE-1 字节继续等待
                #         if len(self.buffer) > self.FRAME_SIZE:
                #             self.buffer = self.buffer[-(self.FRAME_SIZE-1):]
                #         break

                #     if idx > 0:
                #         # 丢弃帧头前的乱码
                #         print(f"丢弃 {idx} 字节乱码数据")
                #         self.buffer = self.buffer[idx:]

                #     if len(self.buffer) < self.FRAME_SIZE:
                #         break  # 数据不足，等待下一次读取

                #     # 现在 buffer 以 FRAME_HEADER 开头，且长度足够
                #     frame_data = self.buffer[:self.FRAME_SIZE]
                #     self.buffer = self.buffer[self.FRAME_SIZE:]

                #     # 解析三个通道
                #     try:
                #         ch1, ch2, ch3 = struct.unpack('>hhh', frame_data[2:8])  # 大端 short
                #         timestamp = time.perf_counter()
                #         frame = (ch1, ch2, ch3, timestamp+self.base_time)

                #         # 如果队列满，丢弃最老的一帧（可选：也可阻塞）
                #         if self.data_queue.full():
                #             self.data_queue.get()
                #         self.data_queue.put(frame)

                #     except struct.error as e:
                #         print(f"帧解析失败: {e}, 数据: {frame_data.hex()}")
                #         continue

            except Exception as e:
                print(f"读取线程异常: {e}")
                time.sleep(0.001)

    def read(self, len=4, timeout: Optional[float] = None) -> Optional[Tuple[int, int, int, float]]:
        """
        从队列中读取一个帧数据。
        :param timeout: 超时时间，None 表示无限等待
        :return: (ch1, ch2, ch3, timestamp) 或 None（超时）
        """
        return [self.data_queue.get(timeout=timeout) for _ in range(len)]

    def read_batch(self, n: int, timeout: float = 1.0) -> list:
        """
        读取最多 n 个帧，带超时
        """
        batch = []
        start_time = time.time()
        while len(batch) < n and (time.time() - start_time) < timeout:
            frame = self.read(timeout=0.1)
            if frame is not None:
                batch.append(frame)
        return batch

    def qsize(self) -> int:
        """返回当前队列中的帧数量"""
        return self.data_queue.qsize()

    def close(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        if self.ser and self.ser.is_open:
            self.ser.close()
        print("串口已关闭，读取线程已停止")

    def __del__(self):
        self.close()


# ================== 测试代码 ==================
if __name__ == "__main__":
    collector = RppgCollector(port="COM4", baudrate=256000)

    try:
        cnt = 0
        start = time.time()
        while True:
            frame = collector.read(len=6)  # 每次读一个帧
            if frame is None:
                continue

            # ch1, ch2, ch3, timestamp = frame
            # print(f"帧: {ch1}, {ch2}, {ch3}, 时间: {timestamp:.4f}")

            cnt += 6
            if time.time() - start > 1.0:
                print(f"FPS: {cnt} fps")
                cnt = 0
                start = time.time()

    except KeyboardInterrupt:
        print("停止采集")
    finally:
        collector.close()
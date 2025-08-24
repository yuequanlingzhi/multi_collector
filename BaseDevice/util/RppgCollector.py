import serial
import struct
import threading
import time
import queue

class RppgCollector:
    SERIAL_PORT = 'COM3'  # 你可以修改为你的串口
    BAUD_RATE = 256000
    FRAME_HEADER = b'\xCC\xCC'
    FRAME_SIZE = 8  # 2字节帧头 + 6字节数据
    BATCH_SIZE = 4  # 每批读取帧数

    def __init__(self, port=None, baudrate=None):
        self.port = port or self.SERIAL_PORT
        self.baudrate = baudrate or self.BAUD_RATE
        self.ser = None
        self.buffer = bytearray()
        self.data_queue = queue.Queue(maxsize=1)  # 最大长度为1的队列，存放批量数据列表
        self.running = True
        self.thread = None

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
                data = self.ser.read(self.ser.in_waiting or 1)
                if data:
                    self.buffer.extend(data)

                frames = []
                while True:
                    idx = self.buffer.find(self.FRAME_HEADER)
                    if idx == -1:
                        if len(self.buffer) > 2 * self.FRAME_SIZE:
                            self.buffer = self.buffer[-2 * self.FRAME_SIZE:]
                        break

                    if len(self.buffer) < idx + self.FRAME_SIZE:
                        break

                    frame = self.buffer[idx:idx + self.FRAME_SIZE]
                    self.buffer = self.buffer[idx + self.FRAME_SIZE:]

                    ch1, ch2, ch3 = struct.unpack('>hhh', frame[2:8])
                    timestamp = time.time()
                    frames.append((ch1, ch2, ch3, timestamp))

                    if len(frames) >= self.BATCH_SIZE:
                        break

                if frames:
                    # 队列满则先清空旧数据，再放入新批次
                    if self.data_queue.full():
                        try:
                            self.data_queue.get_nowait()
                        except queue.Empty:
                            pass
                    self.data_queue.put(frames)

            except Exception as e:
                print(f"读取线程异常: {e}")
                time.sleep(0.001)

    def read(self, timeout=None):
        """
        阻塞读取一批数据，返回列表[(ch1,ch2,ch3,timestamp), ...]
        timeout=None表示无限等待
        """
        return self.data_queue.get()

    def close(self):
        self.running = False
        if self.thread:
            self.thread.join()
        if self.ser and self.ser.is_open:
            self.ser.close()
        print("串口已关闭，读取线程已停止")

    def __del__(self):
        self.close()

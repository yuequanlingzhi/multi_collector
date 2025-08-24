
import os
import sys
import asyncio
import time
import cv2
import scipy.io as sio
from typing import List, Dict, Tuple, Any, Type
from openni import openni2

# from BaseDevice import BaseDevice, VideoDevice, OrbbecDevice, PPGDevice, UwbDevice, MilliWaveDevice, OpencvDevice
from BaseDevice.BaseDevice import BaseDevice
from BaseDevice.VideoDevice import VideoDevice
from BaseDevice.OrbbecDevice import OrbbecDevice
from BaseDevice.PPGDevice import PPGDevice
from BaseDevice.UwbDevice import UwbDevice
from BaseDevice.MilliWaveDevice import MilliWaveDevice
from BaseDevice.OpencvDevice import OpencvDevice
from BaseDevice.FFmpegDevice import FFmpegDevice

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QFileDialog, QMessageBox, QGridLayout, QGroupBox, QComboBox
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap
from pygrabber.dshow_graph import FilterGraph

camera_params={
    "Logitech StreamCam": {
        "frame_size":(1080, 1920, 3),
        "frame_rate": 30,
        "encode_type":"mjpeg",
    },
    "USB Camera":{
        "frame_size":(1080, 1920, 3),
        "frame_rate": 30,
        "encode_type":"mjpeg",
    },
    "HD USB Camera":{
        "frame_size":(1080, 1920, 3),
        "frame_rate": 120,
        "encode_type":"mjpeg",
    },
    "HD Pro Webcam C920":{
        "frame_size":(1080, 1920, 3),
        "frame_rate": 30,
        "encode_type":"mjpeg",
    },
    "LRCP  USB2.0":{
        "frame_size":(1080, 1920, 3),
        "frame_rate": 30,
        "encode_type":"mjpeg",
    }
}

class MainWindow(QWidget):
    def __init__(self): 
        super().__init__()
        self.setWindowTitle("多设备多模态数据采集")
        self.resize(1200, 700)

        base_dir = os.path.abspath(os.path.dirname(sys.argv[0]))  # 获取运行目录
        data_dir = os.path.join(base_dir, "data")
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        self.save_dir = data_dir
        print('开始初始化')
        self.init_devices()
        BaseDevice.start_devices()
        print("所有设备初始化完成")
        self.device_list : List[BaseDevice] = BaseDevice.devices.values()
        print(self.device_list)
        self.recording = False

        self.timer_label = QLabel("录制时间: 00:00")
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.timer_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.record_seconds = 0
        self.record_timer = QTimer()
        self.record_timer.timeout.connect(self.update_record_time)
        self.init_ui()
        print('ui初始化完成')
        # 定时器刷新摄像头画面
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frames)
        self.timer.start(33)  # 约33fps刷新

    def init_ui(self):
        layout = QVBoxLayout()
        # 元数据输入区
        meta_group = QGroupBox("元数据输入")
        meta_layout = QGridLayout()

        self.meta_fields = {
            "姓名": QLineEdit(),
            "年龄": QLineEdit(),
            "身高(cm)": QLineEdit(),
            "体重(kg)": QLineEdit(),
            "状态": QComboBox(),    #(平静/运动/运动后/休息)四选一
            "备注": QLineEdit()
        }

        self.meta_fields["状态"].addItems(["平静", "运动", "运动后", "休息"])
        row = 0
        for label, widget in self.meta_fields.items():
            meta_layout.addWidget(QLabel(label), row, 0)
            meta_layout.addWidget(widget, row, 1)
            row += 1

        meta_group.setLayout(meta_layout)
        layout.addWidget(meta_group)

        # 保存路径选择
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit(self.save_dir)
        self.path_edit.setReadOnly(True)
        path_btn = QPushButton("选择保存路径")
        path_btn.clicked.connect(self.select_save_path)
        path_layout.addWidget(QLabel("保存路径:"))
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(path_btn)
        layout.addLayout(path_layout)

        self.labels : Dict[str, QLabel] = {}
        # 显示区
        video_layout = None
        for i,device in enumerate(self.device_list):
            if i%4==0:
                if video_layout is not None:
                    layout.addLayout(video_layout)
                video_layout = QHBoxLayout()
            device_name = device.device_name
            self.labels[device_name] = QLabel(device_name)
            self.labels[device_name].setFixedSize(560, 420)
            self.labels[device_name].setStyleSheet("background-color: black;")
            video_layout.addWidget(self.labels[device.device_name])
        layout.addLayout(video_layout)

        layout.addWidget(self.timer_label)
        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("开始录制")
        self.btn_stop = QPushButton("停止录制")
        self.btn_stop.setEnabled(False)

        self.btn_start.clicked.connect(self.start_record)
        self.btn_stop.clicked.connect(self.stop_record)

        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def select_save_path(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择保存路径", self.save_dir)
        if dir_path:
            self.save_dir = dir_path
            self.path_edit.setText(dir_path)
            # 更新设备保存路径
            BaseDevice.save_dir = dir_path

    def update_frames(self):
        frames = [device.get_current_data() for device in self.device_list]
        try:
            
            for label_name, frame in zip(self.labels.keys(), frames):
                if frame is not None:
                    if label_name in ["orbbec_depth_camera","uwb","milliwave"]:
                        self.show_frame_gray(self.labels[label_name], frame)
                    else:

                        self.show_frame(self.labels[label_name], frame)
        except Exception as e:
            pass

    def show_frame(self, label, frame):
        # BGR转RGB
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image).scaled(label.width(), label.height(), Qt.KeepAspectRatio)
        label.setPixmap(pixmap)

    def show_frame_gray(self, label, frame):
        h, w = frame.shape

        bytes_per_line = w
        qt_image = QImage(frame.data, w, h, bytes_per_line, QImage.Format_Grayscale8)
        pixmap = QPixmap.fromImage(qt_image).scaled(label.width(), label.height(), Qt.KeepAspectRatio)
        label.setPixmap(pixmap)

    def start_record(self):
        self.record_seconds = 0
        self.update_record_time()  # 立即刷新显示
        self.record_timer.start(1000)  # 每秒更新一次
        # 通过meta_fileds获取元数据
        user_name = self.meta_fields["姓名"].text()
        user_state = self.meta_fields["状态"].currentText()
        if user_name is None:
            user_name = "unknown"
        BaseDevice.register_user_meta_data(self.save_dir,user_name, user_state)
        # 先保存元数据到txt
        meta_path = os.path.join(self.save_dir, user_name ,f"metadata.txt")
        with open(meta_path, 'w', encoding='utf-8') as f:
            for k, widget in self.meta_fields.items():
                if k == "状态":
                    continue
                f.write(f"{k}: {widget.text()}\n")
        print(f"元数据保存到 {meta_path}")
        record_duration = 5
        BaseDevice.start_record(record_duration=record_duration)
        self.recording = True
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

    def stop_record(self):
        # 定义每个设备停止录制并保存的线程函数
        BaseDevice.stop_record()
        self.recording = False
        self.record_timer.stop()
        self.record_seconds = 0
        self.update_record_time() 
        for device in self.device_list:
            device.save_data()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def update_record_time(self):
        self.record_seconds += 1
        mins = self.record_seconds // 60
        secs = self.record_seconds % 60
        self.timer_label.setText(f"录制时间: {mins:02d}:{secs:02d}")
        
    def closeEvent(self, event):
        # 关闭程序时释放摄像头资源
        BaseDevice.stop_all()
        cv2.destroyAllWindows()
        event.accept()
        print("程序已关闭")
    
    def init_devices(self):
        # 初始化设备 
        graph = FilterGraph()
        camera_devices_list = graph.get_input_devices()
        devices_configs : Dict[Type[BaseDevice], List[Dict[str, Any]]]
        devices_configs = {
            FFmpegDevice:[
                {
                "device_name":f"rgb_camera{i}-{camera_name}", 
                "camera_name":camera_name, 
                **camera_params[camera_name]
                } for i, camera_name in enumerate(camera_devices_list) if camera_name in camera_params.keys() 
            ],
            OrbbecDevice: [
            #    {"device_name":"orbbec_depth_camera", "frame_type":"depth", "frame_rate":30},
            ],
            PPGDevice: [
               # {"device_name":"ppg", "port":"COM6", "frame_rate":1000}
            ],
            UwbDevice: [
               # {"device_name":"uwb", "port":"COM7", "frame_rate":200}
            ],
            MilliWaveDevice: [
               # {"device_name":"milliwave", "port":"COM13", "frame_rate":10, "baud_rate":2000000}
            ],
            # OpencvDevice:[
            #     #  {"device_name":"IR_camera", "camera_name": "LRCP  USB2.0", "frame_size":(1080, 1920, 3), "frame_rate": 30, 'exposure':-6},
            #     # {"device_name":"Logitech_cam", "camera_name": "HD Pro Webcam C920", "frame_size":(1080, 1900, 3), "frame_rate": 30},
            # ]
            # FFmpegDevice:[
            #     {"device_name":"Logitech_cam", "camera_name": "HD Pro Webcam C920", "frame_size":(1080, 1920, 3), "frame_rate": 30, "encode_type":"mjpeg"},
            # ]

        }

        for device_class, device_configs in devices_configs.items():
            for device_config in device_configs:
                device_class(**device_config)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_()) 
    



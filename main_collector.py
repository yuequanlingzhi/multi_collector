
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
    QHBoxLayout, QFileDialog, QMessageBox, QGridLayout, QGroupBox, QComboBox, QCheckBox
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap
from pygrabber.dshow_graph import FilterGraph

QUALITY = 10
camera_params={
    "Logitech StreamCam": {
        "frame_size":(1080, 1920, 3),
        "frame_rate": 30,
        "encode_type":"mjpeg",
        "quality": QUALITY,
    },
    "USB Camera":{
        "frame_size":(1080, 1920, 3),
        "frame_rate": 30,
        "encode_type":"mjpeg",
        "quality": QUALITY,
    },
    "HD USB Camera":{
        "frame_size":(1080, 1920, 3),
        "frame_rate": 120,
        "encode_type":"mjpeg",
        "quality": QUALITY,
    },
    "HD Pro Webcam C920":{
        "ID1": r"@device_pnp_\\?\usb#vid_046d&pid_082d&mi_00#6&8d48e5e&0&0000#{65e8773d-8f56-11d0-a3b9-00a0c9223196}\global",
        "ID2": r"@device_pnp_\\?\usb#vid_046d&pid_082d&mi_00#6&103b5be6&0&0000#{65e8773d-8f56-11d0-a3b9-00a0c9223196}\global",
        "frame_size":(1080, 1920, 3),
        "frame_rate": 30,
        "encode_type":"mjpeg",
        "quality": QUALITY,
    },
    "LRCP  USB2.0":{
        "frame_size":(1080, 1920, 3),
        "frame_rate": 30,
        "encode_type":"mjpeg",
        "quality": QUALITY,
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
        self.devices : Dict[str, BaseDevice] = BaseDevice.devices
        print(self.device_list)
        print(self.devices)
        self.recording = False

        self.timer_label = QLabel("录制时间: 00:00")
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.timer_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.record_seconds = 0
        self.record_timer = QTimer()
        self.record_timer.timeout.connect(self.update_record_time)

        self.checkboxes : Dict[str, QCheckBox] = {}
        self.init_ui()
        print('ui初始化完成')
        # 定时器刷新摄像头画面
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frames)
        self.timer.start(50)  # 约33fps刷新

    def init_ui(self):
        layout = QVBoxLayout()
        # 元数据输入区
        meta_group = QGroupBox("元数据输入")
        meta_layout = QGridLayout()

        self.meta_fields = {
            "姓名": QLineEdit(),
            "年龄": QLineEdit(),
            "性别": QComboBox(),  #(男/女)两选一
            "身高(cm)": QLineEdit(),
            "体重(kg)": QLineEdit(),
            "心率": QLineEdit(),
            "血压（高压）": QLineEdit(),
            "血压（低压）": QLineEdit(),
            "状态": QComboBox(),    #(平静/运动/运动后/休息)四选一
            "备注": QLineEdit()
        }

        self.meta_fields["状态"].addItems(["平静", "运动", "运动后", "休息"])
        self.meta_fields["性别"].addItems(["男", "女"])
        row = 0
        col = 0
        for label_text, widget in self.meta_fields.items():
            # 创建水平布局存放“标签 + 控件”
            field_layout = QHBoxLayout()
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.addWidget(QLabel(label_text))
            field_layout.addWidget(widget, 1)  # 1 表示伸缩系数

            # 创建容器 widget 包裹这个 layout
            container = QWidget()
            container.setLayout(field_layout)

            # 放入 grid 的对应位置
            meta_layout.addWidget(container, row, col)

            # 每行最多两个，col 0 -> 1，然后换行
            col += 1
            if col == 2:
                col = 0
                row += 1

        # 如果最后一个 row 只有一个字段，右边留空
        if col == 1:
            meta_layout.addWidget(QWidget(), row, 1)  # 占位空白

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

        
        # 显示区
        self.labels : Dict[str, QLabel] = {}
        self.checkboxes : Dict[str, QLabel]= {}

        video_layout = None
        for i, device in enumerate(self.device_list):
            if i % 4 == 0:
                if video_layout is not None:
                    layout.addLayout(video_layout)
                video_layout = QHBoxLayout()

            device_name = device.device_name

            vbox = QVBoxLayout()

            label = QLabel(device_name)
            label.setFixedSize(560, 420)
            label.setStyleSheet("background-color: black;")
            self.labels[device_name] = label

            # 水平布局包裹勾选框，实现居中
            hbox = QHBoxLayout()
            checkbox = QCheckBox(f"{device_name}")
            checkbox.setChecked(False)
            checkbox.stateChanged.connect(lambda state, dn=device_name: self.on_checkbox_state_changed(dn, state))
            self.checkboxes[device_name] = checkbox

            hbox.addWidget(checkbox)
            hbox.setAlignment(Qt.AlignHCenter)

            vbox.addWidget(label)
            vbox.addLayout(hbox)
            vbox.setAlignment(Qt.AlignHCenter)
            video_layout.addLayout(vbox)

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

    def on_checkbox_state_changed(self, device_name, state):
        if self.recording:
            return
        
        allow = (state == Qt.Checked)
        device = self.devices[device_name]
        device.allow_record = allow
        print(f"Device {device_name} allow record: {allow}")
    
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
        for checkbox in self.chekcboxes.values():
            checkbox.setEnabled(False)
        self.record_seconds = -1
        self.update_record_time()  # 立即刷新显示
        self.record_timer.start(1000)  # 每秒更新一次
        # 通过meta_fileds获取元数据
        user_name = self.meta_fields["姓名"].text()
        user_age = self.meta_fields["年龄"].text()
        user_gender = self.meta_fields["性别"].currentText()
        user_blood_pressure_high = self.meta_fields["血压（高压）"].text()
        user_blood_pressure_low = self.meta_fields["血压（低压）"].text()
        user_heart_rate = self.meta_fields["心率"].text()
        user_state = self.meta_fields["状态"].currentText()
        meta_data = {
            "姓名": user_name,
            "年龄": user_age,
            "性别": user_gender,
            "血压（高压）": user_blood_pressure_high,
            "血压（低压）": user_blood_pressure_low,
            "心率": user_heart_rate,
            "状态": user_state
        }
        if user_name is None:
            user_name = "unknown"
        BaseDevice.register_user_meta_data(self.save_dir,meta_data)
        # 先保存元数据到txt
        # meta_path = os.path.join(self.save_dir, user_name ,f"metadata.txt")
        # with open(meta_path, 'w', encoding='utf-8') as f:
        #     for k, widget in self.meta_fields.items():
        #         if k == "状态" or k == "性别":
        #             continue
        #         f.write(f"{k}: {widget.text()}\n")
        # print(f"元数据保存到 {meta_path}")
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
        self.record_seconds = -1
        self.update_record_time() 
        for device in self.device_list:
            if device.allow_record:
                device.save_data()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        for checkbox in self.chekcboxes.values():
            checkbox.setEnabled(True)

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
        try:
            camera_devices_list = graph.get_input_devices()
        except Exception as e:
            camera_devices_list = []
        devices_configs : Dict[Type[BaseDevice], List[Dict[str, Any]]]
        devices_configs = {
            FFmpegDevice:[
                {
                "device_name":f"camera{i}_{camera_name}", 
                "camera_name":camera_name, 
                **camera_params[camera_name]
                } for i, camera_name in enumerate(camera_devices_list) if camera_name in camera_params.keys() 
            ],
            OrbbecDevice: [
            #    {"device_name":"orbbec_depth_camera", "frame_type":"depth", "frame_rate":30},
            ],
            PPGDevice: [
            #    {"device_name":"ppg", "port":"COM4", "frame_rate":1000}  
            ],
            UwbDevice: [
            #    {"device_name":"uwb", "port":"COM6", "frame_rate":200}
            ],
            MilliWaveDevice: [
            #    {"device_name":"milliwave", "port":"COM5", "frame_rate":110, "baud_rate":2000000}
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
    



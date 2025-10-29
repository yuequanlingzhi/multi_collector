# -*- coding: utf-8 -*-
"""
@created on: 2019-07-01
@author: Markus Scholz
@license: MIT
"""

# xep interface adapted based on XEP_plot_record_playback.py example by xethru
from __future__ import print_function, division

import numpy as np
from time import sleep
from queue import Queue
import pymoduleconnector
from pymoduleconnector import DataType
from pymoduleconnector.ids import *
import threading

__version__ = 3


class xep():

    def __init__(self, device_name):

        self.reset(device_name)
        self.mc = pymoduleconnector.ModuleConnector(device_name)
        self.buffer = Queue(maxsize=3)
        # Assume an X4M300/X4M200 module and try to enter XEP mode
        self.app = self.mc.get_x4m300()
        # Stop running application and set module in manual mode.
        try:
            self.app.set_sensor_mode(0x13, 0) # Make sure no profile is running.
        except RuntimeError:
            # Profile not running, OK
            pass

        try:
            self.app.set_sensor_mode(0x12, 0) # Manual mode.
        except RuntimeError:
            # Maybe running XEP firmware only?
            pass

    def configure(self, dac_min, dac_max, frame_offset, frame_start, frame_end, baseband, fps, iterations=16, pulses_per_step=26):
        
        self.baseband = baseband
        self.FPS = fps
        self.xep = self.mc.get_xep()
        
        # based on the manual
        self.xep.x4driver_set_dac_min(dac_min)
        self.xep.x4driver_set_dac_max(dac_max)

        # Set integration
        self.xep.x4driver_set_iterations(iterations)
        self.xep.x4driver_set_pulses_per_step(pulses_per_step)
        
        # hw specific offset (as stated in xep manual)
        self.xep.x4driver_set_frame_area_offset(frame_offset)
        self.xep.x4driver_set_frame_area(start=frame_start, end=frame_end)

        # set baseband or not
        self.xep.x4driver_set_downconversion(int(baseband))

        # set number to keep at max in internal queue
        #print(self.xep.peek_message_system())


    def get_sensor_configuration(self):
        sensor_config = (
        f"frame area start: {self.xep.x4driver_get_frame_area().start} \n"
        f"frame area end: {self.xep.x4driver_get_frame_area().end} \n"
        f"frame offset: {self.xep.x4driver_get_frame_area_offset()} \n"
        f"dac max: {self.xep.x4driver_get_dac_max()} \n"
        f"dac min: {self.xep.x4driver_get_dac_min()} \n"
        f"fps: {self.xep.x4driver_get_fps()} \n"
        f"pulses per step: {self.xep.x4driver_get_pulses_per_step()}"
        )
        
        return sensor_config


    def reset(self, device_name):
        mc = pymoduleconnector.ModuleConnector(device_name)
        xep = mc.get_xep()
        xep.module_reset()
        mc.close()
        sleep(3)

    def clear_buffer(self):
        """Clears the frame buffer"""
        xep = self.mc.get_xep()
        while xep.peek_message_data_float():
            xep.read_message_data_float()


    def start_streaming(self):
        # Start streaming of data
        self.xep.x4driver_set_fps(self.FPS)
        self.recording = True
        threading.Thread(target=self.read_frame_loop, daemon=True).start()

    def stop_streaming(self):
        self.xep.x4driver_set_fps(0)
        self.recording = False

    def read_frame_loop(self):
        while self.recording:
            while not self.xep.peek_message_data_float():
                pass
            
            while self.xep.peek_message_data_float() > 0:
                d = self.xep.read_message_data_float()
                break
            frame = np.array(d.data)
            n = len(frame)
            frame = frame[:n//2] + 1j*frame[n//2:]
            self.buffer.put(frame)

    def read_frame(self):
        """Gets frame data from module"""
        return self.buffer.get()

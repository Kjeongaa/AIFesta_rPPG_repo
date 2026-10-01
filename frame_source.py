#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" 
FrameSource 클래스
RealSense 카메라 입력 
"""

import numpy as np

__all__ = ["FrameSource"]

class FrameSource:
    def __init__(self, width, height, fps):
        self.width = width
        self.height = height
        self.fps = fps
        self.pipeline = None
        self.rs = None

    def open(self):
        try:
            import pyrealsense2 as rs
        except ImportError as exc:
            raise RuntimeError("pyrealsense2 is required to use the RealSense camera.") from exc

        self.rs = rs
        self.pipeline = rs.pipeline()
        cfg = rs.config()
        cfg.enable_stream(rs.stream.color, self.width, self.height, rs.format.bgr8, self.fps)
        self.pipeline.start(cfg)

    def read(self):
        frames = self.pipeline.wait_for_frames()
        color_frame = frames.get_color_frame()
        if not color_frame:
            return False, None
        img = np.asanyarray(color_frame.get_data())
        return True, img

    def close(self):
        if self.pipeline is not None:
            self.pipeline.stop()

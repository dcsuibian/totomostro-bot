from typing import Any

import cv2
import mss
import numpy as np
import win32gui


class WindowCapturer:
    """
    捕获 PS Remote Play 窗口画面
    """

    def __init__(self):
        self.window_title = 'PS Remote Play'
        self.screen = mss.mss()
        self.window_handle = None
        self.crop_margins = {'top': 32}

    def detect_window(self) -> bool:
        """
        检测窗口是否存在，存在则设置 handle
        """
        windows = []
        win32gui.EnumWindows(
            lambda handle, lst: lst.append(handle) if self.window_title in win32gui.GetWindowText(handle) else None,
            windows,
        )
        self.window_handle = windows[0] if windows else None
        return self.window_handle is not None

    def get_rect(self) -> dict[str, Any] | None:
        if not self.window_handle:
            return None
        left, top, right, bottom = win32gui.GetWindowRect(self.window_handle)
        return {'left': left, 'top': top, 'width': right - left, 'height': bottom - top}

    def capture(self) -> np.ndarray | None:
        rect = self.get_rect()
        if not rect:
            return None
        image = np.array(self.screen.grab(rect))
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)


if '__main__' == __name__:
    capturer = WindowCapturer()
    if not capturer.detect_window():
        print('未检测到 PS Remote Play 窗口')
        exit(1)
    print(f'PS Remote Play 窗口已找到 (handle={capturer.window_handle})')

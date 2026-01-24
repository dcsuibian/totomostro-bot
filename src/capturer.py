import time
from typing import Any

import cv2
import mss
import numpy as np
import win32con
import win32gui


class WindowCapturer:
    """
    捕获 chiaki-ng 窗口画面
    """

    def __init__(self, window_title: str = 'chiaki-ng'):
        self.window_title = window_title
        self.screen = mss.mss()
        self.window_handle = None

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

    def setup_window(self, width: int = 1920, height: int = 1080, topmost: bool = True):
        """
        一键设置窗口：移到左上角 + 设置大小 + 置顶
        """
        if not self.window_handle:
            raise RuntimeError('窗口未检测到')
        # 移动到左上角并设置大小
        win32gui.MoveWindow(self.window_handle, 0, 0, width, height, True)
        # 置顶
        if topmost:
            self.set_topmost(True)

    def set_topmost(self, topmost: bool = True):
        """
        置顶/取消置顶窗口
        """
        if not self.window_handle:
            raise RuntimeError('窗口未检测到')
        flag = win32con.HWND_TOPMOST if topmost else win32con.HWND_NOTOPMOST
        win32gui.SetWindowPos(
            self.window_handle,
            flag,
            0, 0, 0, 0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
        )

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
    time.sleep(1)
    capturer.setup_window()
    print('窗口已调整')

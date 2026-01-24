"""虚拟 DS4 手柄控制器控制 PS 主机"""

import logging
import time
from typing import Literal

import vgamepad as vg
from vgamepad import DS4_DPAD_DIRECTIONS

logger = logging.getLogger(__name__)


class GamepadController:
    """
    通过 ViGEmBus 虚拟 DS4 手柄控制 PS 主机
    """

    def __init__(self, confirm_button: Literal['circle', 'cross'] = 'circle'):
        """
        初始化虚拟手柄
        :param confirm_button: FF15游戏中的确认键，'circle' 或 'cross'。注意是游戏中而不是PS系统的。
        """
        self.gamepad = vg.VDS4Gamepad()
        self.press_duration = 0.1
        self.press_interval = 0.15
        self.confirm_button = confirm_button
        self.cancel_button = 'cross' if confirm_button == 'circle' else 'circle'

    def _press_button(self, button):
        """按下并释放按钮"""
        self.gamepad.press_button(button)
        self.gamepad.update()
        time.sleep(self.press_duration)
        self.gamepad.release_button(button)
        self.gamepad.update()
        time.sleep(self.press_interval)

    def _press_dpad(self, direction: DS4_DPAD_DIRECTIONS):
        """按下并释放方向键"""
        self.gamepad.directional_pad(direction)
        self.gamepad.update()
        time.sleep(self.press_duration)
        self.gamepad.directional_pad(DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NONE)
        self.gamepad.update()
        time.sleep(self.press_interval)

    # 方向键
    def up(self):
        logger.debug('按下 上 按钮')
        self._press_dpad(DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTH)

    def down(self):
        logger.debug('按下 下 按钮')
        self._press_dpad(DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTH)

    def left(self):
        logger.debug('按下 左 按钮')
        self._press_dpad(DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_WEST)

    def right(self):
        logger.debug('按下 右 按钮')
        self._press_dpad(DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_EAST)

    # 基础按键
    def cross(self):
        """✕"""
        logger.debug('按下 ✕ 按钮')
        self._press_button(vg.DS4_BUTTONS.DS4_BUTTON_CROSS)

    def circle(self):
        """○"""
        logger.debug('按下 ○ 按钮')
        self._press_button(vg.DS4_BUTTONS.DS4_BUTTON_CIRCLE)

    def square(self):
        """□"""
        logger.debug('按下 □ 按钮')
        self._press_button(vg.DS4_BUTTONS.DS4_BUTTON_SQUARE)

    def triangle(self):
        """△"""
        logger.debug('按下 △ 按钮')
        self._press_button(vg.DS4_BUTTONS.DS4_BUTTON_TRIANGLE)

    # 肩键
    def l1(self):
        logger.debug('按下 L1 按钮')
        self._press_button(vg.DS4_BUTTONS.DS4_BUTTON_SHOULDER_LEFT)

    def r1(self):
        logger.debug('按下 R1 按钮')
        self._press_button(vg.DS4_BUTTONS.DS4_BUTTON_SHOULDER_RIGHT)

    def l2(self):
        logger.debug('按下 L2 按钮')
        self._press_button(vg.DS4_BUTTONS.DS4_BUTTON_TRIGGER_LEFT)

    def r2(self):
        logger.debug('按下 R2 按钮')
        self._press_button(vg.DS4_BUTTONS.DS4_BUTTON_TRIGGER_RIGHT)

    # 功能键
    def options(self):
        logger.debug('按下 Options 按钮')
        self._press_button(vg.DS4_BUTTONS.DS4_BUTTON_OPTIONS)

    def share(self):
        logger.debug('按下 Share 按钮')
        self._press_button(vg.DS4_BUTTONS.DS4_BUTTON_SHARE)

    def confirm(self):
        """确认键"""
        if self.confirm_button == 'circle':
            self.circle()
        else:
            self.cross()

    def cancel(self):
        """取消键"""
        if self.cancel_button == 'circle':
            self.circle()
        else:
            self.cross()


if __name__ == '__main__':
    print('初始化虚拟 DS4 手柄...')
    controller = GamepadController()

    print('3 秒后开始测试，请确保 chiaki-ng 窗口已激活...')
    time.sleep(3)

    controller.up()
    controller.down()

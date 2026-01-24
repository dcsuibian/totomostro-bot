"""游戏状态识别"""
import logging
import re
from dataclasses import dataclass
from typing import Literal

import cv2
import easyocr
import numpy as np

logger = logging.getLogger(__name__)

READER = easyocr.Reader(['ch_sim', 'en'], verbose=False)


@dataclass
class RecognizedTeam:
    """识别出的队伍信息"""
    name: str
    odds: float
    index: int


class GameRecognizer:
    """游戏状态识别"""

    STATE_UNKNOWN = 'unknown'
    STATE_MENU = 'menu'
    STATE_SELECT_TEAM = 'select_team'
    STATE_READY_TO_START = 'ready_to_start'
    STATE_INPUT_AMOUNT = 'input_amount'
    STATE_CONFIRM_DIALOG = 'confirm_dialog'
    STATE_WATCHING = 'watching'
    STATE_RESULT = 'result'

    # ========== 状态识别 ==========

    def recognize_state(self, image: np.ndarray) -> str:
        """识别当前游戏状态"""
        if self._detect_confirm_dialog(image):
            return self.STATE_CONFIRM_DIALOG

        if self._detect_input_amount(image):
            return self.STATE_INPUT_AMOUNT

        if self._detect_result(image):
            return self.STATE_RESULT

        if self._detect_watching(image):
            return self.STATE_WATCHING

        if self._detect_ready_to_start(image):
            return self.STATE_READY_TO_START

        if self._detect_select_team(image):
            return self.STATE_SELECT_TEAM

        if self._detect_menu(image):
            return self.STATE_MENU

        return self.STATE_UNKNOWN

    def recognize_result(self, image: np.ndarray) -> Literal['win', 'lose', 'draw', 'unknown']:
        """识别比赛结果"""
        h, w = image.shape[:2]
        roi = image[int(h * 0.25):int(h * 0.5), int(w * 0.3):int(w * 0.7)]
        text = self._ocr_text(roi)

        if '胜利' in text:
            return 'win'
        elif '失败' in text:
            return 'lose'
        elif '平局' in text:
            return 'draw'
        return 'unknown'

    def recognize_teams(self, image: np.ndarray) -> list[RecognizedTeam]:
        """识别所有队伍信息"""
        h, w = image.shape[:2]
        teams = []

        team_regions = [
            (0.220, 0.265),
            (0.265, 0.310),
            (0.310, 0.355),
            (0.355, 0.400),
        ]

        for i, (y_start, y_end) in enumerate(team_regions):
            row_roi = image[int(h * y_start):int(h * y_end), int(w * 0.53):int(w * 0.88)]
            text = self._ocr_text(row_roi).strip()

            if not text:
                continue

            odds = self._parse_odds(text)
            name = re.sub(r'[\d.]+', '', text).strip()

            if name and odds is not None:
                teams.append(RecognizedTeam(name=name, odds=odds, index=i))

        return teams

    def detect_cheer_prompt(self, image: np.ndarray) -> bool:
        """检测应援提示（左下角圆圈图标）"""
        h, w = image.shape[:2]
        # 左下角区域
        roi = image[int(h * 0.7):int(h * 0.85), int(w * 0.12):int(w * 0.22)]

        # 转换到 HSV 检测红色/粉色圆圈
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # 红色范围（圆圈是红/粉色）
        lower_red1 = np.array([0, 50, 50])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([170, 50, 50])
        upper_red2 = np.array([180, 255, 255])

        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask = mask1 + mask2

        # 计算红色像素占比
        red_ratio = np.sum(mask > 0) / mask.size

        # 红色占比超过阈值认为有圆圈
        return red_ratio > 0.02

    # ========== 状态检测 ==========

    def _detect_confirm_dialog(self, image: np.ndarray) -> bool:
        """检测确认对话框"""
        h, w = image.shape[:2]
        roi = image[int(h * 0.3):int(h * 0.6), int(w * 0.25):int(w * 0.75)]
        text = self._ocr_text(roi)
        return '是否' in text

    def _detect_input_amount(self, image: np.ndarray) -> bool:
        """检测输入金额界面"""
        h, w = image.shape[:2]
        roi = image[int(h * 0.35):int(h * 0.55), int(w * 0.25):int(w * 0.75)]
        text = self._ocr_text(roi)
        return '决定' in text and '应援' in text

    def _detect_result(self, image: np.ndarray) -> bool:
        """检测结果界面"""
        h, w = image.shape[:2]
        roi = image[int(h * 0.25):int(h * 0.5), int(w * 0.3):int(w * 0.7)]
        text = self._ocr_text(roi)
        return '胜利' in text or '失败' in text or '平局' in text

    def _detect_watching(self, image: np.ndarray) -> bool:
        """检测观战界面"""
        h, w = image.shape[:2]
        roi = image[int(h * 0.05):int(h * 0.15), int(w * 0.75):int(w * 0.95)]
        text = self._ocr_text(roi)
        return bool(re.search(r'\d{2}:\d{2}', text))

    def _detect_ready_to_start(self, image: np.ndarray) -> bool:
        """检测准备开始界面"""
        if not self._detect_select_team(image):
            return False
        h, w = image.shape[:2]
        roi = image[int(h * 0.65):int(h * 0.78), int(w * 0.5):int(w * 0.95)]
        text = self._ocr_text(roi)
        return '比赛开始' in text or ('改' in text and '奖章数' in text)

    def _detect_select_team(self, image: np.ndarray) -> bool:
        """检测选队界面"""
        h, w = image.shape[:2]
        roi = image[int(h * 0.12):int(h * 0.35), int(w * 0.5):int(w * 0.95)]
        text = self._ocr_text(roi)
        return '倍数' in text or '状态' in text or bool(re.search(r'\d+\.\d', text))

    def _detect_menu(self, image: np.ndarray) -> bool:
        """检测主菜单"""
        h, w = image.shape[:2]
        roi = image[int(h * 0.15):int(h * 0.4), int(w * 0.05):int(w * 0.35)]
        text = self._ocr_text(roi)
        return '应援' in text and '兑换' in text

    # ========== 工具方法 ==========

    def _ocr_text(self, image: np.ndarray) -> str:
        try:
            results = READER.readtext(image)
            return ' '.join([r[1] for r in results])
        except Exception as e:
            logger.debug(f'OCR失败: {e}')
            return ''

    def _parse_odds(self, text: str) -> float | None:
        match = re.search(r'(\d+\.?\d*)', text)
        if match:
            try:
                odds = float(match.group(1))
                if odds>10.0:
                    odds = odds /10.0
                return odds
            except ValueError:
                pass
        return None
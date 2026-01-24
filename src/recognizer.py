"""游戏状态识别"""
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import cv2
import easyocr
import numpy as np

from config import DEBUG_DIR, DEBUG_SAVE_IMAGES, DEBUG_MAX_IMAGES

logger = logging.getLogger(__name__)

READER = easyocr.Reader(['ch_sim', 'en'])


@dataclass
class RecognizedTeam:
    """识别出的队伍信息"""
    name: str
    odds: float
    index: int


class GameRecognizer:
    """游戏状态识别"""

    # 状态常量
    STATE_UNKNOWN = 'unknown'
    STATE_MENU = 'menu'
    STATE_SELECT_TEAM = 'select_team'
    STATE_READY_TO_START = 'ready_to_start'
    STATE_INPUT_AMOUNT = 'input_amount'
    STATE_CONFIRM_DIALOG = 'confirm_dialog'
    STATE_WATCHING = 'watching'
    STATE_RESULT = 'result'

    def __init__(self, debug: bool = DEBUG_SAVE_IMAGES, max_images: int = DEBUG_MAX_IMAGES):
        self.debug = debug
        self.debug_dir = DEBUG_DIR
        self.max_images = max_images

    # ========== 调试 ==========

    def _rotate_debug_files(self, category_dir: Path, keep: int | None = None):
        """
        滚动删除旧文件，保留最新的 keep 个
        :param category_dir: 目录
        :param keep: 保留数量，None 则用 self.max_images
        """
        keep = keep or self.max_images
        if keep <= 0:
            return

        # 获取所有文件，按修改时间排序
        files = sorted(category_dir.iterdir(), key=lambda f: f.stat().st_mtime)

        # 删除超出数量的旧文件
        delete_count = len(files) - keep
        if delete_count > 0:
            for f in files[:delete_count]:
                try:
                    f.unlink()
                except Exception as e:
                    logger.debug(f'删除文件失败: {f}, {e}')

    def _save_debug_image(self, image: np.ndarray, category: str, extra: str = ''):
        """保存调试图片"""
        if not self.debug:
            return

        category_dir = self.debug_dir / category
        category_dir.mkdir(parents=True, exist_ok=True)

        # 滚动删除
        self._rotate_debug_files(category_dir)

        timestamp = time.strftime('%Y%m%d_%H%M%S')
        extra_str = f'_{extra}' if extra else ''
        filename = f'{timestamp}{extra_str}.png'

        cv2.imwrite(str(category_dir / filename), image)

    def _save_debug_roi(self, image: np.ndarray, roi: np.ndarray,
                        category: str, text: str, result: str):
        """保存ROI调试信息"""
        if not self.debug:
            return

        category_dir = self.debug_dir / category
        category_dir.mkdir(parents=True, exist_ok=True)

        # 滚动删除（每次保存2个文件，所以限制数量要乘2）
        self._rotate_debug_files(category_dir, self.max_images * 2)

        timestamp = time.strftime('%Y%m%d_%H%M%S')

        # 保存ROI图片
        cv2.imwrite(str(category_dir / f'{timestamp}_roi.png'), roi)

        # 保存识别结果
        log_file = category_dir / f'{timestamp}_result.txt'
        log_file.write_text(f'OCR文本: {text}\n识别结果: {result}', encoding='utf-8')

    def _save_teams_debug(self, image: np.ndarray, teams: list[RecognizedTeam], texts: list[str]):
        """保存队伍识别调试信息"""
        if not self.debug:
            return

        category_dir = self.debug_dir / 'teams'
        category_dir.mkdir(parents=True, exist_ok=True)

        # 滚动删除
        self._rotate_debug_files(category_dir, self.max_images * 2)

        timestamp = time.strftime('%Y%m%d_%H%M%S')

        # 保存原图
        cv2.imwrite(str(category_dir / f'{timestamp}_full.png'), image)

        # 保存识别结果
        result_lines = texts + [
            '---',
            f'识别到 {len(teams)} 个队伍:',
        ]
        for t in teams:
            result_lines.append(f'  [{t.index + 1}] {t.name} x{t.odds}')

        log_file = category_dir / f'{timestamp}_result.txt'
        log_file.write_text('\n'.join(result_lines), encoding='utf-8')

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

        # 未知状态保存调试图
        self._save_debug_image(image, 'unknown')
        return self.STATE_UNKNOWN

    def recognize_result(self, image: np.ndarray) -> Literal['win', 'lose', 'draw', 'unknown']:
        """识别比赛结果"""
        h, w = image.shape[:2]
        roi = image[int(h * 0.25):int(h * 0.5), int(w * 0.3):int(w * 0.7)]
        text = self._ocr_text(roi)

        if '胜利' in text:
            result = 'win'
        elif '失败' in text:
            result = 'lose'
        elif '平局' in text:
            result = 'draw'
        else:
            result = 'unknown'

        self._save_debug_roi(image, roi, 'result', text, result)
        return result

    def recognize_teams(self, image: np.ndarray) -> list[RecognizedTeam]:
        """识别所有队伍信息"""
        h, w = image.shape[:2]
        teams = []

        team_regions = [
            (0.150, 0.195),
            (0.198, 0.243),
            (0.246, 0.291),
            (0.294, 0.339),
        ]

        debug_texts = []

        for i, (y_start, y_end) in enumerate(team_regions):
            row_roi = image[int(h * y_start):int(h * y_end), int(w * 0.53):int(w * 0.88)]
            text = self._ocr_text(row_roi).strip()
            debug_texts.append(f'Team{i + 1}: {text}')

            if not text:
                continue

            odds = self._parse_odds(text)
            name = re.sub(r'[\d.]+', '', text).strip()

            if name and odds is not None:
                teams.append(RecognizedTeam(name=name, odds=odds, index=i))

        self._save_teams_debug(image, teams, debug_texts)
        return teams

    # ========== 状态检测 ==========

    def _detect_confirm_dialog(self, image: np.ndarray) -> bool:
        h, w = image.shape[:2]
        roi = image[int(h * 0.3):int(h * 0.6), int(w * 0.25):int(w * 0.75)]
        text = self._ocr_text(roi)
        return '是否' in text

    def _detect_input_amount(self, image: np.ndarray) -> bool:
        h, w = image.shape[:2]
        roi = image[int(h * 0.35):int(h * 0.55), int(w * 0.25):int(w * 0.75)]
        text = self._ocr_text(roi)
        return '决定' in text and '应援' in text

    def _detect_result(self, image: np.ndarray) -> bool:
        h, w = image.shape[:2]
        roi = image[int(h * 0.25):int(h * 0.5), int(w * 0.3):int(w * 0.7)]
        text = self._ocr_text(roi)
        return '胜利' in text or '失败' in text or '平局' in text

    def _detect_watching(self, image: np.ndarray) -> bool:
        h, w = image.shape[:2]
        roi = image[int(h * 0.02):int(h * 0.12), int(w * 0.8):int(w * 0.98)]
        text = self._ocr_text(roi)
        return bool(re.search(r'\d{2}:\d{2}', text))

    def _detect_ready_to_start(self, image: np.ndarray) -> bool:
        if not self._detect_select_team(image):
            return False
        h, w = image.shape[:2]
        roi = image[int(h * 0.65):int(h * 0.78), int(w * 0.5):int(w * 0.95)]
        text = self._ocr_text(roi)
        return '比赛开始' in text or ('改' in text and '奖章数' in text)

    def _detect_select_team(self, image: np.ndarray) -> bool:
        h, w = image.shape[:2]
        roi = image[int(h * 0.12):int(h * 0.35), int(w * 0.5):int(w * 0.95)]
        text = self._ocr_text(roi)
        return '倍数' in text or '状态' in text or bool(re.search(r'\d+\.\d', text))

    def _detect_menu(self, image: np.ndarray) -> bool:
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
                return float(match.group(1))
            except ValueError:
                pass
        return None

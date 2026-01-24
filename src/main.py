"""FF15 Totomostro（水都竞技场）自动挂机机器人"""

import atexit
import logging
import time

from capturer import WindowCapturer
from config import MODEL_PATH
from controller import GamepadController
from recognizer import GameRecognizer, RecognizedTeam
from repository import TotomostroRepository
from strategy import MlStrategy

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

logger = logging.getLogger(__name__)


class TotomostroBot:
    """水都竞技场自动挂机"""

    def __init__(self):
        self.capturer = WindowCapturer()
        self.controller = GamepadController()
        self.recognizer = GameRecognizer()
        self.repo = TotomostroRepository()
        self.running = False

        self.strategy = MlStrategy(self.repo, MODEL_PATH)

        # 当前比赛信息
        self.current_teams: list[RecognizedTeam] = []
        self.current_selection: RecognizedTeam | None = None
        self.current_bet_amount: int = 1

        logger.info(f'已加载历史数据: {self.repo.total_rounds()}场, 胜率{self.repo.win_rate():.1%}')
        atexit.register(self.cleanup)

    def setup(self) -> bool:
        """初始化设置"""
        logger.info('正在检测 chiaki-ng 窗口...')
        if not self.capturer.detect_window():
            logger.error('未检测到 chiaki-ng 窗口')
            return False

        logger.info('窗口已找到，设置中...')
        self.capturer.setup_window(1920, 1080, topmost=True)
        logger.info('窗口已设置：左上角, 1920x1080, 置顶')
        return True

    def cleanup(self):
        """退出时清理"""
        logger.info('清理中...')
        logger.info(f'统计: {self.repo.total_rounds()}场, 赢{self.repo.wins()}, 输{self.repo.losses()}')
        try:
            self.repo.close()
            if self.capturer.window_handle:
                self.capturer.set_topmost(False)
                logger.info('已取消窗口置顶')
        except Exception as e:
            logger.warning(f'清理失败: {e}')

    def capture_screen(self):
        """截图"""
        return self.capturer.capture()

    # ========== 状态处理 ==========

    def handle_menu(self, image):
        """主菜单 - 进入应援"""
        logger.info('[菜单] 进入应援')
        self.controller.confirm()
        time.sleep(0.5)

    def handle_select_team(self, image):
        """选择队伍"""
        teams = self.recognizer.recognize_teams(image)

        if not teams:
            logger.warning('[选队] 识别失败，选第一个')
            self.current_selection = RecognizedTeam(name='unknown', odds=0, index=0)
            self.current_teams = []
        else:
            logger.info(f'[选队] 识别到 {len(teams)} 个队伍:')
            for t in teams:
                wr = self.repo.get_monster_win_rate(t.name)
                wr_str = f'{wr:.0%}' if wr is not None else '-'
                logger.info(f'  [{t.index + 1}] {t.name} x{t.odds} ({wr_str})')

            self.current_teams = teams
            self.current_selection = self.strategy.select_team(teams)
            self._navigate_to_team(self.current_selection.index)

        self.controller.confirm()
        time.sleep(0.3)

    def _navigate_to_team(self, target_index: int):
        """导航到指定队伍"""
        for _ in range(target_index):
            self.controller.down()
            time.sleep(0.15)

    def handle_ready_to_start(self, image):
        """已选队，开始比赛"""
        logger.info('[准备] 开始比赛')
        self.controller.confirm()
        time.sleep(0.1)

    def handle_input_amount(self, image):
        """输入金额"""
        self.current_bet_amount = self.strategy.calculate_bet_amount()
        logger.info(f'[下注] 金额: {self.current_bet_amount} (当前胜率:{self.repo.win_rate():.1%})')

        self._input_amount(self.current_bet_amount)
        self.controller.confirm()
        time.sleep(1.5)

    def _input_amount(self, amount: int):
        """输入指定金额"""
        digits = [int(d) for d in f'{amount:04d}']
        for i in range(3, -1, -1):
            digit = digits[i]
            if digit > 5:
                for _ in range(10 - digit):
                    self.controller.down()
                    time.sleep(0.1)
            else:
                for _ in range(digit):
                    self.controller.up()
                    time.sleep(0.1)
            if i > 0:
                self.controller.left()
                time.sleep(0.1)

    def handle_confirm_dialog(self, image):
        """确认对话框"""
        logger.info('[对话框] 确认')
        self.controller.confirm()
        time.sleep(0.5)

    def handle_watching(self, image):
        """观战中"""
        time.sleep(1)

    def handle_result(self, image):
        """结果界面"""
        result = self.recognizer.recognize_result(image)

        # 记录到数据库
        self.repo.add_match(
            choice=self.current_selection.name if self.current_selection else 'unknown',
            teams=[(t.name, t.odds) for t in self.current_teams],
            result=result if result in ('win', 'lose', 'draw') else None,
            bet_amount=self.current_bet_amount,
        )

        # 每10场训练一次模型
        total = self.repo.total_rounds()
        if total % 10 == 0:
            logger.info('[训练] 更新模型...')
            self.strategy.train()

        # 日志
        symbol = {'win': '✓', 'lose': '✗', 'draw': '='}.get(result, '?')
        choice_name = self.current_selection.name if self.current_selection else 'unknown'
        logger.info(f'[结果] #{total} {symbol} {choice_name}')
        logger.info(f'[统计] {self.repo.win_rate():.1%} ({self.repo.wins()}/{total})')

        # 显示近100场胜率
        if total >= 100:
            recent_wr = self.repo.win_rate(100)
            logger.info(f'[近100场] {recent_wr:.1%}')

        # 重置当前比赛状态
        self.current_teams = []
        self.current_selection = None

        self.controller.confirm()
        time.sleep(1)

    # ========== 主循环 ==========

    def run_once(self):
        """执行一次循环"""
        image = self.capture_screen()
        if image is None:
            logger.warning('截图失败')
            time.sleep(1)
            return

        state = self.recognizer.recognize_state(image)

        handlers = {
            GameRecognizer.STATE_MENU: self.handle_menu,
            GameRecognizer.STATE_SELECT_TEAM: self.handle_select_team,
            GameRecognizer.STATE_READY_TO_START: self.handle_ready_to_start,
            GameRecognizer.STATE_INPUT_AMOUNT: self.handle_input_amount,
            GameRecognizer.STATE_CONFIRM_DIALOG: self.handle_confirm_dialog,
            GameRecognizer.STATE_WATCHING: self.handle_watching,
            GameRecognizer.STATE_RESULT: self.handle_result,
        }

        handler = handlers.get(state)
        if handler:
            handler(image)
        else:
            logger.debug(f'[未知状态] {state}')
            time.sleep(0.5)

    def run(self):
        """主循环"""
        self.running = True
        logger.info('开始运行...')
        try:
            while self.running:
                self.run_once()
                time.sleep(0.2)
        except KeyboardInterrupt:
            logger.info('用户中断')
        finally:
            self.running = False


def main():
    logger.info('=== FF15 Totomostro Bot ===')

    bot = TotomostroBot()
    if not bot.setup():
        return

    logger.info('3 秒后开始，按 Ctrl+C 停止')
    time.sleep(3)
    bot.run()
    logger.info('=== done ===')


if __name__ == '__main__':
    main()

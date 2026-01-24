"""配置文件"""
from pathlib import Path

# 项目根目录
PROJECT_DIR = Path(__file__).parent.parent

# 输出目录
OUTPUT_DIR = PROJECT_DIR / 'output'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 调试目录
DEBUG_DIR = OUTPUT_DIR / 'debug'
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

# 模型文件
MODEL_PATH = OUTPUT_DIR / 'model.pkl'

# 数据库文件
DATABASE_PATH = OUTPUT_DIR / 'totomostro-bot.db'

# 调试开关
DEBUG_SAVE_IMAGES = True  # 是否保存识别图片
DEBUG_MAX_IMAGES = 1000  # 最多保存多少张图片（防止占用太多空间）

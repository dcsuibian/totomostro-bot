"""配置文件"""
from pathlib import Path

# 项目根目录
PROJECT_DIR = Path(__file__).parent.parent

# 输出目录
OUTPUT_DIR = PROJECT_DIR / 'output'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 模型文件
MODEL_PATH = OUTPUT_DIR / 'model.pkl'

# 数据库文件
DATABASE_PATH = OUTPUT_DIR / 'totomostro-bot.db'

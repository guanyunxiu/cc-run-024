"""全局配置。"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get("MEALPLAN_DB", str(BASE_DIR / "mealplan.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

JWT_SECRET = os.environ.get("MEALPLAN_SECRET", "change-me-in-production-7f3a9c1e")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 12

# 营养目标可调系数（活动量 → PAL 乘子）
ACTIVITY_FACTOR = {
    "bedridden": 1.10,      # 卧床
    "sedentary": 1.20,      # 久坐
    "light": 1.375,         # 轻度活动
    "moderate": 1.55,       # 中度活动
    "active": 1.725,        # 较活跃
}

# IDDSI 等级（数字越小质地越受限）。0 稀薄液体 … 7 常规固体
IDDSI_LEVELS = list(range(8))

# 每日餐次槽位：key, 中文, 默认热量占比
MEAL_SLOTS = [
    ("breakfast", "早餐", 0.30),
    ("morning_snack", "上午加餐", 0.05),
    ("lunch", "午餐", 0.35),
    ("afternoon_snack", "下午加餐", 0.05),
    ("dinner", "晚餐", 0.25),
]

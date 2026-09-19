"""全局配置。"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get("NUTRITION_DB", str(BASE_DIR / "data" / "app.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

# JWT
SECRET_KEY = os.environ.get("NUTRITION_SECRET", "elderly-nutrition-meal-planner-secret-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12

# 配餐
SLOTS = ["breakfast", "lunch", "dinner"]
SLOT_LABELS = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐"}

# IDDSI 等级（数字越大越稀薄/越容易吞咽，老人等级 = 允许的最高食物质地等级）
IDDSI_LABELS = {
    0: "0级 稀薄液体",
    1: "1级 微稠液体",
    2: "2级 浓稠液体",
    3: "3级 流动糊状",
    4: "4级 泥状/糊状",
    5: "5级 碎软食",
    6: "6级 软质食",
    7: "7级 普通食",
}

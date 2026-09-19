"""种子数据：用户、规则、食材、菜品配方、老人档案。

首次启动时写入；菜品营养/成本由配方自动换算。
"""
from sqlmodel import Session, select

from .database import engine
from .models import Dish, DishIngredient, Ingredient, Resident, Rule, User
from .nutrition import targets_snapshot
from .recipe import recompute_dish
from .rules import DEFAULT_RULES
from .security import hash_password


# ---------------- 用户 ----------------

USERS = [
    dict(username="admin", password="Admin@2026", name="系统管理员", role="admin"),
    dict(username="dietitian", password="Nutri@2026", name="林营养师", role="nutritionist"),
    dict(username="viewer", password="View@2026", name="护理部查看员", role="viewer"),
]


# ---------------- 食材 ----------------
# (name, cat, edible%, 元/kg, energy, pro, fat, carb, Na, K, P, fiber, Ca, vitK, purine, GI, allergens, tags)
def _i(name, cat, edible=100, cost=0.0, en=0, pro=0, fat=0, carb=0, na=0,
       k=0, p=0, fib=0, ca=0, vk=0, pur=0, gi=0, al=None, tags=None):
    return dict(name=name, category=cat, edible_pct=edible, unit_cost=cost,
                energy_kcal=en, protein_g=pro, fat_g=fat, carb_g=carb,
                sodium_mg=na, potassium_mg=k, phosphorus_mg=p, fiber_g=fib,
                calcium_mg=ca, vitamin_k_ug=vk, purine_mg=pur, glycemic_index=gi,
                allergens=al or [], tags=tags or [])


INGREDIENTS = [
    # 主食（每100g可食部）
    _i("粳米(生)", "主食", 100, 8, 346, 7.4, 0.8, 77.9, 2, 103, 113, 0.7, 13, gi=73),
    _i("小米(生)", "主食", 100, 12, 361, 9, 3.1, 75.1, 4, 284, 229, 1.6, 41, pur=60, gi=71),
    _i("燕麦片", "主食", 100, 14, 377, 15, 6.7, 61.6, 4, 214, 290, 5.3, 186, gi=55),
    _i("糙米(生)", "主食", 100, 10, 348, 7.7, 2.7, 73, 7, 304, 333, 3.4, 12, gi=50),
    _i("红豆(生)", "主食", 100, 16, 324, 20.2, 0.6, 60.7, 2, 860, 386, 7.7, 74, pur=80),
    _i("绿豆(生)", "主食", 100, 14, 329, 21.6, 0.8, 62, 3, 787, 337, 6.4, 81, pur=75),
    _i("面粉", "主食", 100, 7, 354, 11.2, 1.5, 73.6, 3, 190, 188, 2.1, 31, al=["gluten"]),
    _i("馒头", "主食", 100, 6, 223, 7, 1.1, 47, 194, 138, 107, 1.3, 38, al=["gluten"]),
    _i("全麦面包", "主食", 100, 20, 250, 9, 3.2, 46, 380, 180, 150, 6, 80, al=["gluten", "sesame"], gi=50),
    _i("面条(湿)", "主食", 100, 7, 110, 4.5, 0.5, 24, 160, 60, 60, 1.5, 14, al=["gluten"]),
    _i("红薯", "主食", 90, 4, 86, 1.6, 0.1, 20.1, 70, 88, 47, 3, 23, gi=63),
    _i("土豆", "主食", 85, 4, 77, 2, 0.1, 17.2, 3, 421, 40, 0.7, 8, gi=78),
    _i("南瓜", "蔬菜", 85, 4, 23, 0.7, 0.1, 5.5, 1, 340, 24, 0.8, 16, gi=75),
    _i("玉米", "主食", 60, 5, 112, 4, 1.2, 22.8, 1, 238, 117, 2.9, 14, gi=55),

    # 蛋奶
    _i("鸡蛋", "蛋奶", 88, 12, 144, 13.3, 8.8, 2.8, 132, 154, 130, 0, 56, al=["egg"], tags=["egg"]),
    _i("牛奶", "蛋奶", 100, 8, 54, 3, 3.2, 3.4, 37, 109, 73, 0, 104, al=["milk"], tags=["milk"]),
    _i("无糖酸奶", "蛋奶", 100, 16, 72, 2.5, 2.7, 9.3, 36, 155, 85, 0, 118, al=["milk"], tags=["milk"]),

    # 鱼肉豆
    _i("鸡胸肉", "肉类", 100, 24, 118, 21.9, 3.1, 0, 34, 338, 214, 0, 16, tags=["poultry"]),
    _i("牛肉(瘦)", "肉类", 100, 70, 125, 20.2, 4.2, 0, 53, 284, 205, 0, 9, pur=100, tags=["meat"]),
    _i("猪肉(瘦)", "肉类", 100, 30, 143, 20.3, 6.2, 1.5, 58, 305, 189, 0, 6, pur=120, tags=["meat"]),
    _i("五花肉", "肉类", 100, 30, 395, 13.6, 37, 2.2, 59, 204, 162, 0, 5, tags=["meat", "pork", "fatty_meat"]),
    _i("猪排(带骨)", "肉类", 60, 32, 264, 18, 20, 1.7, 62, 270, 175, 0, 8, tags=["meat", "pork"]),
    _i("猪肝", "肉类", 100, 28, 129, 19.3, 3.5, 5, 69, 235, 310, 0, 6, vk=25, pur=270, tags=["meat", "pork", "organ_meat", "high_purine", "high_phosphorus"]),
    _i("鲈鱼", "鱼类", 58, 38, 105, 18.6, 3.4, 0, 144, 205, 213, 0, 138, al=["fish"], pur=70, tags=["fish"]),
    _i("带鱼", "鱼类", 76, 30, 127, 17.7, 4.9, 3.1, 150, 280, 191, 0, 28, al=["fish"], pur=240, tags=["fish", "high_purine"]),
    _i("草鱼", "鱼类", 58, 22, 113, 16.6, 5.2, 0, 46, 312, 203, 0, 38, al=["fish"], pur=140, tags=["fish"]),
    _i("虾仁", "鱼虾", 100, 70, 48, 10.6, 0.8, 0, 303, 215, 158, 0, 62, al=["shrimp"], pur=137, tags=["seafood"]),
    _i("北豆腐", "豆制品", 100, 8, 98, 12.2, 4.8, 2, 7, 106, 158, 0.4, 138, al=["soy"], tags=["high_phosphorus"]),
    _i("南豆腐", "豆制品", 100, 7, 57, 6.2, 2.5, 2.4, 7, 154, 95, 0.2, 116, al=["soy"]),
    _i("豆腐脑", "豆制品", 100, 6, 15, 1.7, 0.8, 0.3, 110, 100, 40, 0, 18, al=["soy"]),
    _i("豆浆", "豆制品", 100, 5, 31, 3, 1.6, 1.2, 3, 117, 42, 0, 10, al=["soy"]),
    _i("豆干", "豆制品", 100, 14, 140, 16, 8, 4, 76, 140, 200, 0.8, 308, al=["soy"], tags=["high_phosphorus"]),
    _i("素鸡", "豆制品", 100, 14, 192, 16.5, 12.5, 4.5, 420, 60, 180, 0.5, 319, al=["soy"]),
    _i("鱼丸", "鱼类", 100, 25, 107, 11, 1.3, 12, 600, 120, 90, 0, 20, al=["fish"], tags=["fish"]),
    _i("海米(虾皮)", "鱼虾", 100, 60, 153, 30.7, 2.2, 2.5, 5058, 617, 583, 0, 991, al=["shrimp"], tags=["seafood", "high_sodium"]),

    # 蔬菜
    _i("番茄", "蔬菜", 97, 8, 20, 0.9, 0.2, 4, 5, 237, 23, 0.5, 10, vk=8),
    _i("小白菜", "蔬菜", 81, 7, 15, 1.5, 0.3, 2.7, 74, 178, 36, 1.1, 90, vk=45),
    _i("菠菜", "蔬菜", 89, 8, 28, 2.6, 0.3, 4.5, 85, 311, 47, 1.7, 66, vk=483, pur=130,
       tags=["high_vitamin_k", "high_potassium", "high_purine"]),
    _i("西兰花", "蔬菜", 53, 12, 36, 4.1, 0.6, 4.3, 19, 318, 72, 2.6, 67, vk=102,
       tags=["high_vitamin_k", "high_potassium"]),
    _i("冬瓜", "蔬菜", 80, 3, 12, 0.4, 0.2, 2.6, 2, 136, 12, 0.7, 19),
    _i("胡萝卜", "蔬菜", 97, 5, 39, 1, 0.2, 8.8, 71, 320, 27, 2.8, 32, vk=10,
       tags=["high_potassium"]),
    _i("芹菜", "蔬菜", 66, 7, 20, 1.2, 0.2, 4.5, 159, 260, 50, 1.4, 80, vk=40,
       tags=["high_vitamin_k", "high_potassium"]),
    _i("黄瓜", "蔬菜", 92, 6, 16, 0.8, 0.2, 2.9, 5, 102, 24, 0.5, 24),
    _i("丝瓜", "蔬菜", 83, 7, 20, 1, 0.2, 4.2, 3, 115, 29, 0.6, 14),
    _i("木耳(水发)", "蔬菜", 100, 40, 27, 1.5, 0.2, 6, 5, 52, 30, 2.6, 34, pur=38),
    _i("香菇(鲜)", "蔬菜", 95, 16, 26, 2.2, 0.3, 5.2, 11, 311, 53, 3.3, 2, pur=214,
       tags=["high_purine", "high_potassium"]),
    _i("莲藕", "蔬菜", 88, 8, 73, 1.9, 0.2, 16.4, 44, 243, 58, 1.2, 39, gi=38,
       tags=["high_potassium"]),
    _i("茄子", "蔬菜", 93, 7, 23, 1.1, 0.2, 4.9, 5, 142, 23, 1.3, 24),
    _i("生菜", "蔬菜", 94, 8, 13, 1.3, 0.3, 1.3, 33, 91, 27, 0.7, 34, vk=127,
       tags=["high_vitamin_k"]),

    # 水果
    _i("香蕉", "水果", 59, 7, 93, 1.4, 0.2, 22, 1, 256, 28, 1.2, 7, gi=52,
       tags=["high_potassium"]),
    _i("苹果", "水果", 76, 10, 53, 0.2, 0.2, 13.7, 2, 90, 7, 1.7, 4, gi=36),
    _i("橙子", "水果", 74, 9, 48, 0.8, 0.2, 11.1, 1, 159, 22, 0.6, 20, gi=43),
    _i("猕猴桃", "水果", 83, 18, 61, 0.8, 0.6, 14.5, 3, 312, 26, 2.6, 27,
       tags=["high_potassium"]),
    _i("苹果泥", "水果", 100, 15, 52, 0.2, 0.1, 13.5, 2, 80, 6, 1.5, 4, gi=36),

    # 调味
    _i("食盐", "调味", 100, 3, 0, 0, 0, 0, 39300, 0, 0, 0, 0, tags=["high_sodium"]),
    _i("酱油", "调味", 100, 8, 63, 5.6, 0.1, 10.1, 5757, 337, 38, 0.2, 66,
       tags=["high_sodium"]),
    _i("植物油", "油脂", 100, 15, 900, 0, 100, 0, 0, 0, 0, 0, 0, tags=["fried"]),
    _i("白糖", "调味", 100, 8, 396, 0, 0, 98.9, 1, 0, 0, 0, 0, tags=["high_sugar"]),
    _i("醋", "调味", 100, 6, 31, 2.1, 0.3, 4.9, 262, 35, 9, 0, 17),
    _i("花生", "坚果", 70, 18, 574, 24.8, 44.3, 21.7, 2, 587, 324, 5.5, 39,
       al=["peanut"], pur=80, tags=["high_purine"]),
    _i("芝麻", "坚果", 100, 25, 559, 19.1, 46.1, 24, 8, 358, 531, 14, 780,
       al=["sesame"], tags=["high_phosphorus"]),
    _i("猪肉松", "肉类", 100, 60, 396, 41.8, 13.4, 28.6, 2300, 300, 200, 0, 30,
       tags=["meat", "pork", "high_sodium"]),
]


# ---------------- 菜品 ----------------
# (name, category, iddsi, satisfaction, waste, extra_tags, [(食材, 毛重g, 损失%)])
def _d(name, cat, iddsi, sat, waste, tags, recipe, note=""):
    return dict(name=name, category=cat, iddsi_level=iddsi, satisfaction=sat,
                waste_index=waste, tags=list(tags), recipe=recipe, note=note)


R = lambda ing, g, loss=0: (ing, g, loss)

DISHES = [
    # ========== 主食 ==========
    _d("白米饭", "staple", 7, 4.2, 0.08, [], [R("粳米(生)", 100, -130)]),
    _d("杂粮饭", "staple", 7, 3.6, 0.1, [], [R("粳米(生)", 80, -130), R("糙米(生)", 20, -130)]),
    _d("小米红豆饭", "staple", 7, 3.4, 0.12, [], [R("粳米(生)", 70, -130), R("小米(生)", 15, -130), R("红豆(生)", 15, -120)]),
    _d("燕麦粥", "staple", 5, 3.5, 0.06, [], [R("燕麦片", 35, -350), R("水", 0)]),
    _d("白粥", "staple", 5, 3.2, 0.05, [], [R("粳米(生)", 40, -300)]),
    _d("小米粥", "staple", 5, 3.4, 0.06, [], [R("小米(生)", 40, -300)]),
    _d("软米饭", "staple", 6, 4.0, 0.06, [], [R("粳米(生)", 80, -160)]),
    _d("蒸红薯", "staple", 6, 3.8, 0.15, [], [R("红薯", 150, 15)]),
    _d("蒸玉米", "staple", 7, 3.7, 0.2, [], [R("玉米", 200, 10)]),
    _d("馒头", "staple", 6, 3.9, 0.05, [], [R("馒头", 100, 0)]),
    _d("全麦面包", "staple", 6, 3.5, 0.05, [], [R("全麦面包", 80, 0)]),
    _d("清汤面", "staple", 6, 3.8, 0.08, [], [R("面条(湿)", 180, 20), R("酱油", 5, 0), R("植物油", 3, 0)]),
    _d("番茄鸡蛋面", "staple", 6, 4.3, 0.07, [], [R("面条(湿)", 180, 20), R("番茄", 80, 5), R("鸡蛋", 40, 0), R("植物油", 6, 0), R("食盐", 1.2, 0)]),
    _d("土豆泥", "staple", 4, 3.4, 0.05, [], [R("土豆", 150, 10), R("牛奶", 30, 0), R("植物油", 3, 0)]),
    _d("红薯泥", "staple", 4, 3.3, 0.06, [], [R("红薯", 150, 15)]),
    _d("南瓜泥", "staple", 4, 3.3, 0.06, [], [R("南瓜", 160, 10)]),
    _d("米糊", "staple", 4, 3.0, 0.03, [], [R("粳米(生)", 45, -250)]),

    # ========== 主菜 ==========
    _d("清蒸鲈鱼", "entree", 6, 4.5, 0.12, [], [R("鲈鱼", 140, 8), R("植物油", 5, 0), R("食盐", 1.2, 0), R("酱油", 3, 0)]),
    _d("红烧鱼块", "entree", 6, 4.4, 0.1, [], [R("草鱼", 130, 12), R("酱油", 8, 0), R("白糖", 3, 0), R("植物油", 7, 0)]),
    _d("香煎带鱼", "entree", 7, 4.2, 0.1, ["fried"], [R("带鱼", 130, 10), R("植物油", 10, 0), R("食盐", 1.2, 0)]),
    _d("番茄炒蛋", "entree", 6, 4.7, 0.06, [], [R("鸡蛋", 100, 5), R("番茄", 120, 5), R("植物油", 8, 0), R("食盐", 1.5, 0)]),
    _d("水蒸蛋", "egg", 4, 4.2, 0.04, [], [R("鸡蛋", 100, 0), R("水", 0), R("植物油", 2, 0), R("食盐", 0.8, 0)]),
    _d("白煮蛋", "egg", 7, 3.8, 0.05, [], [R("鸡蛋", 60, 5)]),
    _d("香芹炒牛肉", "entree", 7, 4.0, 0.08, [], [R("牛肉(瘦)", 80, 0), R("芹菜", 100, 8), R("植物油", 8, 0), R("食盐", 1.5, 0)]),
    _d("清蒸鸡胸肉", "entree", 6, 3.7, 0.1, [], [R("鸡胸肉", 90, 5), R("酱油", 5, 0), R("植物油", 3, 0)]),
    _d("白切鸡", "entree", 7, 4.1, 0.1, [], [R("鸡胸肉", 90, 5), R("食盐", 1, 0), R("酱油", 3, 0)]),
    _d("冬瓜肉丸", "entree", 6, 4.0, 0.08, [], [R("猪肉(瘦)", 70, 0), R("冬瓜", 80, 5), R("植物油", 4, 0), R("食盐", 1.2, 0)]),
    _d("肉末豆腐", "entree", 6, 4.1, 0.06, [], [R("猪肉(瘦)", 50, 0), R("北豆腐", 100, 5), R("酱油", 5, 0), R("植物油", 5, 0)]),
    _d("清蒸肉丸", "entree", 5, 3.9, 0.07, [], [R("猪肉(瘦)", 80, 0), R("植物油", 3, 0), R("食盐", 1, 0)]),
    _d("虾仁滑蛋", "entree", 6, 4.3, 0.08, [], [R("虾仁", 70, 5), R("鸡蛋", 80, 0), R("植物油", 6, 0), R("食盐", 1.2, 0)]),
    _d("清炒虾仁", "entree", 6, 4.2, 0.1, [], [R("虾仁", 90, 8), R("黄瓜", 60, 5), R("植物油", 6, 0), R("食盐", 1.2, 0)]),
    _d("红烧排骨", "entree", 7, 4.6, 0.18, [], [R("猪排(带骨)", 150, 10), R("酱油", 9, 0), R("白糖", 4, 0), R("植物油", 5, 0)]),
    _d("红烧肉", "entree", 7, 4.7, 0.12, ["fatty_meat"], [R("五花肉", 100, 10), R("酱油", 9, 0), R("白糖", 5, 0)]),
    _d("糖醋里脊", "entree", 7, 4.5, 0.1, ["fried", "high_sugar"], [R("猪肉(瘦)", 90, 0), R("面粉", 20, 0), R("白糖", 18, 0), R("植物油", 15, 0), R("醋", 8, 0)]),
    _d("溜肝尖", "entree", 7, 3.6, 0.1, [], [R("猪肝", 80, 8), R("植物油", 8, 0), R("酱油", 6, 0)]),
    _d("鱼丸烧冬瓜", "entree", 6, 3.9, 0.08, [], [R("鱼丸", 70, 0), R("冬瓜", 100, 5), R("植物油", 4, 0), R("食盐", 1.2, 0)]),
    _d("麻婆豆腐", "entree", 6, 4.2, 0.07, [], [R("北豆腐", 120, 5), R("猪肉(瘦)", 30, 0), R("酱油", 6, 0), R("植物油", 6, 0), R("食盐", 1, 0)]),
    _d("清蒸豆腐", "soy", 5, 3.6, 0.05, [], [R("南豆腐", 120, 0), R("酱油", 4, 0), R("植物油", 2, 0)]),
    _d("豆腐脑", "soy", 4, 3.5, 0.04, [], [R("豆腐脑", 200, 0), R("酱油", 4, 0)]),
    _d("水煮豆干", "soy", 7, 3.4, 0.08, [], [R("豆干", 80, 0), R("酱油", 4, 0)]),
    _d("鱼羹", "entree", 4, 3.8, 0.05, [], [R("草鱼", 80, 5), R("南豆腐", 50, 0), R("植物油", 3, 0), R("食盐", 1, 0)]),
    _d("蛋花豆腐羹", "entree", 4, 3.7, 0.04, [], [R("鸡蛋", 50, 0), R("南豆腐", 80, 0), R("植物油", 2, 0), R("食盐", 0.8, 0)]),
    _d("肉末土豆泥", "entree", 4, 3.8, 0.05, [], [R("猪肉(瘦)", 40, 0), R("土豆", 120, 10), R("植物油", 3, 0), R("食盐", 0.9, 0)]),

    # ========== 蔬菜 ==========
    _d("蒜蓉小白菜", "vegetable", 7, 3.9, 0.12, [], [R("小白菜", 160, 8), R("植物油", 7, 0), R("食盐", 1.2, 0)]),
    _d("清炒菠菜", "vegetable", 7, 3.6, 0.12, [], [R("菠菜", 160, 10), R("植物油", 7, 0), R("食盐", 1.2, 0)]),
    _d("蒜蓉西兰花", "vegetable", 7, 3.8, 0.12, [], [R("西兰花", 170, 10), R("植物油", 7, 0), R("食盐", 1.3, 0)]),
    _d("清炒黄瓜", "vegetable", 7, 3.5, 0.1, [], [R("黄瓜", 160, 5), R("植物油", 6, 0), R("食盐", 1.1, 0)]),
    _d("蒸南瓜", "vegetable", 6, 3.8, 0.1, [], [R("南瓜", 170, 10)]),
    _d("虾皮冬瓜", "vegetable", 6, 3.7, 0.1, [], [R("冬瓜", 160, 8), R("海米(虾皮)", 5, 0), R("植物油", 5, 0), R("食盐", 0.8, 0)]),
    _d("清炒冬瓜", "vegetable", 6, 3.5, 0.1, [], [R("冬瓜", 160, 8), R("植物油", 6, 0), R("食盐", 1.1, 0)]),
    _d("胡萝卜炒木耳", "vegetable", 7, 3.6, 0.1, [], [R("胡萝卜", 120, 5), R("木耳(水发)", 60, 0), R("植物油", 7, 0), R("食盐", 1.2, 0)]),
    _d("番茄烩丝瓜", "vegetable", 6, 3.6, 0.1, [], [R("丝瓜", 130, 8), R("番茄", 70, 5), R("植物油", 6, 0), R("食盐", 1.1, 0)]),
    _d("软炒时蔬", "vegetable", 5, 3.5, 0.08, [], [R("小白菜", 150, 12), R("冬瓜", 60, 5), R("植物油", 5, 0), R("食盐", 1, 0)]),
    _d("软炒绿叶菜", "vegetable", 5, 3.4, 0.08, [], [R("生菜", 150, 12), R("植物油", 5, 0), R("食盐", 1, 0)]),
    _d("冬瓜菜泥", "vegetable", 4, 3.2, 0.04, [], [R("冬瓜", 170, 8), R("植物油", 3, 0), R("食盐", 0.8, 0)]),
    _d("南瓜菜泥", "vegetable", 4, 3.3, 0.04, [], [R("南瓜", 170, 10)]),
    _d("胡萝卜菜泥", "vegetable", 4, 3.2, 0.04, [], [R("胡萝卜", 170, 8)]),
    _d("腌雪里蕻", "pickle", 7, 3.3, 0.15, ["pickle"], [R("食盐", 12, 0)]),
    _d("酱黄瓜", "pickle", 7, 3.4, 0.1, ["pickle"], [R("黄瓜", 100, 0), R("食盐", 10, 0), R("酱油", 6, 0)]),

    # ========== 汤 ==========
    _d("番茄蛋花汤", "soup", 5, 4.0, 0.1, [], [R("番茄", 80, 5), R("鸡蛋", 30, 0), R("植物油", 2, 0), R("食盐", 1, 0)]),
    _d("冬瓜虾仁汤", "soup", 5, 3.9, 0.1, [], [R("冬瓜", 100, 5), R("虾仁", 30, 0), R("食盐", 1, 0)]),
    _d("紫菜蛋花汤", "soup", 5, 3.7, 0.1, [], [R("鸡蛋", 30, 0), R("酱油", 3, 0), R("食盐", 0.8, 0)]),
    _d("丝瓜豆腐汤", "soup", 5, 3.8, 0.1, [], [R("丝瓜", 90, 8), R("南豆腐", 80, 0), R("植物油", 2, 0), R("食盐", 1, 0)]),
    _d("白菜豆腐汤", "soup", 5, 3.7, 0.1, [], [R("小白菜", 80, 8), R("南豆腐", 80, 0), R("植物油", 2, 0), R("食盐", 1, 0)]),
    _d("冬瓜海带汤", "soup", 5, 3.5, 0.1, [], [R("冬瓜", 120, 5), R("植物油", 2, 0), R("食盐", 1, 0)]),
    _d("小米粥汤", "soup", 4, 3.3, 0.05, [], [R("小米(生)", 20, -300)]),
    _d("蛋花羹", "soup", 4, 3.6, 0.04, [], [R("鸡蛋", 40, 0), R("植物油", 2, 0), R("食盐", 0.7, 0)]),
    _d("豆腐菜泥羹", "soup", 4, 3.4, 0.04, [], [R("南豆腐", 80, 0), R("小白菜", 50, 8), R("食盐", 0.8, 0)]),
    _d("冬瓜羹", "soup", 4, 3.3, 0.04, [], [R("冬瓜", 150, 8), R("食盐", 0.8, 0), R("植物油", 2, 0)]),
    _d("老火排骨汤", "soup", 7, 4.4, 0.15, ["strong_broth"], [R("猪排(带骨)", 120, 10), R("食盐", 1.5, 0)]),
    _d("香菇鸡汤", "soup", 7, 4.3, 0.12, [], [R("鸡胸肉", 60, 5), R("香菇(鲜)", 60, 5), R("食盐", 1.3, 0)]),

    # ========== 加餐/水果/奶类 ==========
    _d("温牛奶", "dairy", 7, 4.0, 0.03, [], [R("牛奶", 250, 0)]),
    _d("无糖酸奶", "dairy", 7, 4.1, 0.03, [], [R("无糖酸奶", 150, 0)]),
    _d("酸奶糊", "dairy", 4, 3.8, 0.03, [], [R("无糖酸奶", 150, 0)]),
    _d("香蕉", "fruit", 6, 4.2, 0.2, [], [R("香蕉", 150, 25)]),
    _d("苹果", "fruit", 7, 4.0, 0.22, [], [R("苹果", 200, 10)]),
    _d("橙子", "fruit", 6, 3.9, 0.2, [], [R("橙子", 200, 25)]),
    _d("猕猴桃", "fruit", 6, 3.8, 0.18, [], [R("猕猴桃", 150, 15)]),
    _d("苹果泥", "fruit", 4, 3.7, 0.05, [], [R("苹果泥", 120, 0)]),
    _d("蒸蛋羹(加餐)", "snack", 4, 3.8, 0.04, [], [R("鸡蛋", 60, 0), R("食盐", 0.5, 0)]),
    _d("豆浆", "snack", 5, 3.6, 0.05, [], [R("豆浆", 250, 0)]),
    _d("牛奶花生汤", "snack", 6, 3.9, 0.08, [], [R("牛奶", 200, 0), R("花生", 15, 0)]),
    _d("芝麻糊", "snack", 4, 3.8, 0.05, ["high_sugar"], [R("芝麻", 20, 0), R("白糖", 12, 0), R("粳米(生)", 15, -300)]),
    _d("肉松粥(加餐)", "snack", 5, 3.9, 0.05, [], [R("粳米(生)", 30, -300), R("猪肉松", 10, 0)]),
]


# ---------------- 老人档案 ----------------

RESIDENTS = [
    dict(name="王秀兰", gender="female", age=82, height_cm=156, weight_kg=52,
         activity_level="light", swallowing_level=7,
         chronic_conditions=["hypertension", "diabetes"],
         allergies=["shrimp"], dislikes=["bitter"], religion="none",
         medications=[], nutrition_goal_type="maintain",
         note="高血压+糖尿病，对虾蟹过敏。目标控盐控糖、稳定血糖。"),
    dict(name="李建国", gender="male", age=78, height_cm=170, weight_kg=68,
         activity_level="moderate", swallowing_level=7,
         chronic_conditions=["gout", "hyperlipidemia"],
         allergies=[], dislikes=[], religion="none",
         medications=[], nutrition_goal_type="lose",
         note="痛风+高脂血症，减重期。限高嘌呤、油炸、酒精。"),
    dict(name="张桂芳", gender="female", age=87, height_cm=152, weight_kg=43,
         activity_level="sedentary", swallowing_level=4,
         chronic_conditions=["hypertension", "ckd"],
         allergies=["egg"], dislikes=[], religion="none",
         medications=[], nutrition_goal_type="gain",
         note="鼻饲/糊状饮食 IDDSI 4，高血压+慢性肾病，鸡蛋过敏。需增重、限钠钾磷。"),
    dict(name="赵德福", gender="male", age=84, height_cm=168, weight_kg=61,
         activity_level="light", swallowing_level=6,
         chronic_conditions=["hypertension"],
         allergies=[], dislikes=[], religion="islam",
         medications=[], nutrition_goal_type="maintain",
         note="回族，清真饮食；IDDSI 6 软食。"),
    dict(name="刘慧敏", gender="female", age=76, height_cm=160, weight_kg=65,
         activity_level="light", swallowing_level=5,
         chronic_conditions=["diabetes"],
         allergies=["milk"], dislikes=["fish"], religion="none",
         medications=["warfarin"], nutrition_goal_type="maintain",
         note="糖尿病 IDDSI 5，乳制品过敏、不爱吃鱼，长期服用华法林需稳定维K。"),
    dict(name="陈广明", gender="male", age=81, height_cm=172, weight_kg=58,
         activity_level="bedridden", swallowing_level=7,
         chronic_conditions=["ckd", "diabetes", "hypertension"],
         allergies=["peanut"], dislikes=[], religion="none",
         medications=[], nutrition_goal_type="maintain",
         note="长期卧床，糖尿病肾病+高血压多病共存，花生过敏。"),
]


def seed_all(clean: bool = False) -> None:
    from .database import init_db
    init_db()
    with Session(engine) as s:
        if s.exec(select(User)).first():
            return

        for u in USERS:
            s.add(User(username=u["username"], password_hash=hash_password(u["password"]),
                       name=u["name"], role=u["role"]))

        for r in DEFAULT_RULES:
            row = dict(r)
            row.setdefault("version", "1.0.0")
            cond = row.pop("condition_label", None)
            s.add(Rule(
                code=row["code"], name=row["name"], rule_type=row["rule_type"],
                severity=row["severity"], priority=row["priority"],
                version=row["version"], rationale=row["rationale"],
                params=row.get("params", {})))

        ing_id = {}
        for ing in INGREDIENTS:
            obj = Ingredient.model_validate(ing)
            s.add(obj)
            s.flush()
            ing_id[ing["name"]] = obj.id

        for d in DISHES:
            dish = Dish(
                name=d["name"], category=d["category"],
                iddsi_level=d["iddsi_level"], satisfaction=d["satisfaction"],
                waste_index=d["waste_index"], tags=d["tags"], note=d.get("note", ""),
                serving_desc="每份")
            s.add(dish)
            s.flush()
            for (ing_name, gross, loss) in d["recipe"]:
                if ing_name == "水" or ing_name not in ing_id:
                    continue
                s.add(DishIngredient(dish_id=dish.id,
                                     ingredient_id=ing_id[ing_name],
                                     gross_g=gross, cooking_loss_pct=loss))
            s.flush()
            recompute_dish(s, dish)
            s.add(dish)

        for r in RESIDENTS:
            resident = Resident.model_validate(r)
            s.add(resident)
            s.flush()
            resident.targets = targets_snapshot(resident)
            s.add(resident)

        s.commit()


if __name__ == "__main__":
    seed_all()
    print("seed done")

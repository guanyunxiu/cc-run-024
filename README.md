# 颐养配餐 —— 养老机构老年营养与慢病配餐优化管理系统

根据老人**慢病、过敏、吞咽等级（IDDSI）、营养目标、成本约束、宗教/个人禁忌、在服药物**，
基于 **OR-Tools CP-SAT** 自动生成每日或每周配餐方案，并支持手动拖拽调整、冲突实时高亮、
锁定后局部重求解、版本管理与回滚、PDF/Excel 报告与采购需求汇总。

---

## 一、登录账号

| 角色 | 用户名 | 密码 | 权限 |
| --- | --- | --- | --- |
| 管理员 | `admin` | `admin123` | 全部功能 + 规则版本发布 |
| 营养师 | `nutritionist` | `nutri123` | 档案/菜品/配餐/报告（规则只读） |

系统首次启动自动初始化种子数据：2 个账号、43 种食材、64 道菜品（覆盖 IDDSI 3~7 各质地与
荤素结构）、1 个已发布规则版本（18 条规则）、4 位典型多病共存演示老人：

- **张德福**：高血压 + 2型糖尿病，IDDSI 6，减重目标
- **李秀兰**：CKD + 肌少症 + 骨质疏松，蛋过敏，IDDSI 5，ACEI，营养不良干预（含 CKD×肌少症蛋白冲突调解）
- **王桂英**：无慢病，花生过敏，佛教全素，IDDSI 7
- **刘建国**：痛风 + 血脂异常 + 高血压，海鲜过敏，华法林，IDDSI 6

---

## 二、技术栈

**后端**：Python 3.11 · FastAPI · SQLModel · SQLite（单文件，免安装）· Google OR-Tools CP-SAT ·
WeasyPrint(PDF) · OpenPyXL(Excel) · JWT 鉴权 · BackgroundTasks 异步任务 · pytest + Hypothesis

**前端**：React 18 + TypeScript + Vite · Ant Design 5 · ECharts（营养雷达/对比）·
FullCalendar（排餐日历）· dnd-kit（拖拽换菜）· TanStack Query · Zustand ·
React Hook Form + Zod · Axios

## 三、快速启动

### 方式 A：一键启动（推荐）

```bash
# 1. 后端（自动建库 + 种子数据，监听 :8000）
./run-backend.sh
# 2. 前端（另开终端，监听 :5173，/api 已代理到 8000）
./run-frontend.sh
```

浏览器打开 http://localhost:5173 ，用上表账号登录。
后端交互式 API 文档：http://localhost:8000/docs

### 方式 B：手动启动

```bash
# 后端
cd backend
pip install -r requirements.txt
python -m app.seed --reset      # 可选：重建数据库并灌入种子
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 前端
cd frontend
npm install
npm run dev
```

> PDF 导出依赖 pango/cairo（多数 Linux 自带）与中文字体；若中文显示为方块，
> 安装 `fonts-noto-cjk` 或将 NotoSansCJK 字体放到 `~/.fonts` 后 `fc-cache -f`。

---

## 四、核心功能与实现说明

| # | 模块 | 关键实现 |
| - | ---- | -------- |
| 1 | 老人档案与营养目标 | Mifflin-St Jeor 基础能量 × 活体系数（老年下调）；蛋白按健康/肌少症/CKD 分档；钠钾磷纤维等 12 项区间目标；**多病共存按临床优先级分层修正并输出冲突调解说明**（如 CKD×肌少症蛋白折中 0.8~1.0g/kg）；营养师手工覆盖置顶；表单支持实时试算 |
| 2 | 菜品营养库 | 食材（可食部）→ 配方（市品投料、烹饪损失率/吸水系数）→ 成品每100g营养与每份成本自动聚合；过敏原与身份标签沿配方传播，**高钠/高脂/高嘌呤等营养等级标签按成品阈值重新判定**，避免"加了盐的菜都算高钠食品"的误伤 |
| 3 | 禁忌规则 | JSON 规则表（带版本/优先级/forbid|warn/生效开关）+ Python 校验函数（IDDSI 质地、过敏原、宗教、药食交互、个人忌口）；规则版本 draft→published→archived，已发布版本只读；每次校验返回可解释的命中规则与替换建议 |
| 4 | 配餐求解（NP-hard） | CP-SAT 三阶段：**phase0 纯结构可行性 → phase1 温和营养引导选菜（满意度/成本/浪费/多样性）→ phase2 固定结构精调份量营养偏差**；硬约束=过敏/禁忌/IDDSI/宗教/成本/餐次结构/周重复≤3/相邻日不重复/锁定菜；不可行时按 成本+25%→结构放宽→重复放宽 分级松弛并记录轨迹 |
| 5 | 排餐日历与版本 | 日/周方案、草稿/发布/归档三态；每次保存与发布生成 `PlanVersionArchive` 快照，支持版本查看、对比（增/删/改）与一键回滚；方案表带 `lock_version` 乐观锁，并发修改返回 409 |
| 6 | 手动调整与冲突高亮 | dnd-kit 拖拽换餐次、双击改份量、锁定/解锁；右侧菜品面板按吞咽等级过滤并实时调用 `/rules/check-dishes`，红框=硬冲突、黄框=软警告；保存仍允许带冲突（供营养师决策）但发布前强提醒；锁定后"局部重求解"只重算未锁定部分 |
| 7 | 报告导出与审计 | 后端生成 PDF（排餐明细/营养达标/冲突调解/目标依据/求解器参数快照）、多 Sheet Excel（概览/排餐/每日营养/采购汇总/求解记录/操作日志）、多方案对比 Excel；采购仅做需求汇总不做库存；所有关键操作写 AuditLog，指标统一取落库快照保证口径一致 |

### 目录结构

```
backend/
  app/
    config.py                 # 配置（餐次、IDDSI 标签）
    database.py seed.py       # DB 引擎 / 种子初始化
    models/                  # User/Ingredient/Dish/Elder/Rule/MealPlan/Task/AuditLog
    schemas/                 # Pydantic
    core/
      nutrition.py           # 个体化目标计算 + 配方→成品营养换算（难点1）
      rules_engine.py        # JSON 规则表 + Python 校验函数（难点3）
      solver.py              # OR-Tools CP-SAT 三阶段多目标求解（难点4）
      security.py            # bcrypt + JWT
    services/                # foodlib / planner / reports / audit
    routes/                  # auth food elders rules plans tasks reports
    data/                    # seed_ingredients/dishes/rules.json
  tests/                     # pytest + Hypothesis（24 个用例）
frontend/src/
  pages/ components/ api/ store/ lib/
```

## 五、测试

```bash
cd backend
python -m pytest tests/ -q      # 营养计算/规则引擎/求解硬约束/API全流程/PDF/Excel
```

覆盖：多病共存冲突调解、手工覆盖优先级、烹饪吸水换算、过敏/宗教/IDDSI/药食规则、
方案中过敏原与吞咽等级强制满足、锁定菜保留、周重复限制、餐次结构、
登录→求解→轮询→乐观锁409→发布、PDF(`%PDF`)/Excel(`PK`) 导出等。

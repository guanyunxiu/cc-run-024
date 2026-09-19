"""养老机构老年营养与慢病配餐优化管理系统 —— 后端入口。"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .database import init_db
from .seed import main as seed_main
from .routes import auth, food, elders, rules, plans, tasks, reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # 首次启动自动种子（空库时）
    import sys
    sys.argv = [sys.argv[0]]
    try:
        seed_main()
    except Exception as exc:  # noqa: BLE001
        print(f"[启动] 种子初始化跳过: {exc}")
    yield


app = FastAPI(
    title="老年营养与慢病配餐优化管理系统",
    version="1.0.0",
    description="根据慢病、过敏、吞咽等级、营养目标与成本约束自动生成日/周配餐",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(food.router)
app.include_router(elders.router)
app.include_router(rules.router)
app.include_router(plans.router)
app.include_router(tasks.router)
app.include_router(reports.router)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@app.get("/api/health", tags=["系统"])
def health():
    return {"status": "ok", "service": "elderly-nutrition-planner", "version": "1.0.0"}

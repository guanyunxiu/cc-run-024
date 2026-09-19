"""FastAPI 主入口。

启动时初始化数据库与种子数据，注册全部路由。
前端由 Vite/静态服务器提供；/api 由本服务提供（开发期前端代理 /api）。
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .database import init_db
from .routers import (audit_logs, auth, dishes, ingredients, plans, reports,
                      residents, rules, tasks)
from .seed import seed_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_all()
    yield


app = FastAPI(title="老年营养与慢病配餐优化管理系统", version="1.0.0",
              lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"],
)

api_prefix = "/api"
app.include_router(auth.router)
app.include_router(residents.router)
app.include_router(ingredients.router)
app.include_router(dishes.router)
app.include_router(rules.router)
app.include_router(plans.router)
app.include_router(tasks.router)
app.include_router(reports.router)
app.include_router(audit_logs.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "mealplan", "version": "1.0.0"}


# 生产环境：托管前端构建产物（SPA history 路由回退到 index.html）
_dist = Path(__file__).resolve().parent.parent / "frontend_dist"
if _dist.exists():
    class SPAStaticFiles(StaticFiles):
        async def get_response(self, path: str, scope):
            try:
                return await super().get_response(path, scope)
            except StarletteHTTPException as e:
                if e.status_code == 404 and not path.startswith("api/"):
                    index = _dist / "index.html"
                    if index.exists():
                        return FileResponse(str(index))
                raise

    app.mount("/", SPAStaticFiles(directory=str(_dist), html=True), name="web")

#!/usr/bin/env bash
# 一键启动：确保已播种并启动后端（同时托管已构建的前端）
set -e
cd "$(dirname "$0")"

if [ ! -d "../frontend_dist" ] || [ ! -f "../frontend_dist/index.html" ]; then
  echo "[run.sh] 未发现前端构建产物，先构建前端 ..."
  (cd ../frontend && npm install && npm run build)
fi

python3 -c "from app.seed import seed_all; seed_all()"
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

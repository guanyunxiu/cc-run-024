#!/usr/bin/env bash
# 启动后端：首次自动建库+种子，监听 http://localhost:8000
set -e
cd "$(dirname "$0")/backend"

if ! python3 -c "import fastapi, ortools, sqlmodel" 2>/dev/null; then
  echo "[启动] 安装 Python 依赖..."
  python3 -m pip install --user --break-system-packages -r requirements.txt
fi

if [ ! -f app/data/app.db ]; then
  echo "[启动] 初始化数据库与种子数据..."
  python3 -m app.seed
fi

exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

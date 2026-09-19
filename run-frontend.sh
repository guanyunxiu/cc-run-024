#!/usr/bin/env bash
# 启动前端开发服务器：http://localhost:5173 （/api 代理到 8000）
set -e
cd "$(dirname "$0")/frontend"

if [ ! -d node_modules ]; then
  echo "[启动] 安装前端依赖..."
  npm install --registry=https://registry.npmmirror.com
fi

exec npm run dev -- --host 0.0.0.0

#!/usr/bin/env sh
# 生产启动：Gunicorn + UvicornWorker 多进程并发
# 用法：在仓库根目录 export PYTHONPATH=. 后执行；或 Docker CMD 调用本脚本
set -e
cd "$(dirname "$0")/.."
export PYTHONPATH="${PYTHONPATH:-.}"
WORKERS="${GUNICORN_WORKERS:-4}"
exec gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  -w "${WORKERS}" \
  -b 0.0.0.0:8000 \
  --timeout 120 \
  --graceful-timeout 30 \
  --access-logfile - \
  --error-logfile -

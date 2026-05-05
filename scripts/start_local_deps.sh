#!/usr/bin/env bash
# 用 Docker 在本机启动 PostgreSQL + Redis（与 README / .env 默认密码一致）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-chattutor123}"

if ! docker info >/dev/null 2>&1; then
  echo "错误: 未检测到 Docker，请先打开 Docker Desktop 或安装 Docker。"
  exit 1
fi

start_or_run() {
  local name="$1"
  shift
  if docker ps -a --format '{{.Names}}' | grep -qx "$name"; then
    docker start "$name" >/dev/null
    echo "已启动已有容器: $name"
  else
    "$@"
    echo "已创建并启动: $name"
  fi
}

start_or_run chattutor-postgres docker run -d --name chattutor-postgres \
  -e POSTGRES_USER=chattutor \
  -e "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}" \
  -e POSTGRES_DB=chattutor \
  -p 5432:5432 \
  pgvector/pgvector:pg16

start_or_run chattutor-redis docker run -d --name chattutor-redis \
  -p 6379:6379 \
  redis:7-alpine

echo "等待 PostgreSQL 就绪..."
for i in $(seq 1 30); do
  if docker exec chattutor-postgres pg_isready -U chattutor >/dev/null 2>&1; then
    echo "PostgreSQL 已就绪。"
    break
  fi
  sleep 1
done

if command -v alembic >/dev/null 2>&1; then
  echo "执行 alembic upgrade head ..."
  LOG="$(mktemp)"
  set +e
  alembic upgrade head 2>"$LOG"
  code=$?
  set -e
  if [ "$code" -ne 0 ]; then
    if grep -qiE 'already exists|DuplicateTable|duplicate key' "$LOG"; then
      echo "检测到表已存在（常见原因：应用启动时 init_db 已建表，或曾跑过迁移）。补打版本: alembic stamp head"
      alembic stamp head
    else
      cat "$LOG"
      rm -f "$LOG"
      exit "$code"
    fi
  fi
  rm -f "$LOG"
else
  echo "提示: 未找到 alembic 命令，请在虚拟环境中: pip install -r requirements.txt && alembic upgrade head"
fi

echo ""
echo "依赖已就绪。请确认 .env 中:"
echo "  DATABASE_URL=postgresql+asyncpg://chattutor:${POSTGRES_PASSWORD}@localhost:5432/chattutor"
echo "  REDIS_URL=redis://localhost:6379/0"
echo ""
echo "然后启动 API:"
echo "  cd $ROOT && PYTHONPATH=. uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

# ChatTutor 生产化改造 - 测试与运行指南

## 前置条件

1. **Docker 和 Docker Compose** (推荐)
2. 或者本地安装 **PostgreSQL 16+** 和 **Redis 7**

## 方式一：Docker 一键启动（推荐）

```bash
cd docker

# 1. 复制环境变量文件
cp ../.env.example ../.env

# 2. 编辑.env 文件，配置 API 密钥和数据库密码
# vi ../.env 或使用其他编辑器

# 3. 启动所有服务
docker-compose up -d

# 4. 查看日志
docker-compose logs -f

# 5. 访问服务
# - 前端：http://localhost:8080
# - 后端 API: http://localhost:8000
# - 健康检查：http://localhost:8000/health

# 6. 停止服务
docker-compose down
```

## 方式二：本地开发环境

### 1. 启动 PostgreSQL 和 Redis

```bash
# 使用 Docker 启动依赖服务
docker run -d --name chattutor-postgres \
  -e POSTGRES_USER=chattutor \
  -e POSTGRES_PASSWORD=chattutor123 \
  -e POSTGRES_DB=chattutor \
  -p 5432:5432 \
  pgvector/pgvector:pg16

docker run -d --name chattutor-redis \
  -p 6379:6379 \
  redis:7-alpine
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑.env 文件
```

### 3. 运行数据库迁移

```bash
# 生成迁移脚本（已完成）
alembic upgrade head

# 查看当前版本
alembic current
```

### 4. 运行数据库测试

```bash
python scripts/test_db_migration.py
```

### 5. 启动后端

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. 启动前端

```bash
streamlit run web_ui.py
```

## API 测试

### 1. 用户注册

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "test123"}'
```

### 2. 用户登录

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=test123"
```

### 3. 获取当前用户

```bash
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 4. 发送聊天消息

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "你好，请解释什么是量子纠缠？"}'
```

### 5. 健康检查

```bash
curl http://localhost:8000/health
```

## 限流测试

```bash
# 快速发送多个请求，应该会被限流
for i in {1..15}; do
  curl -X POST http://localhost:8000/api/v1/chat \
    -H "Authorization: Bearer YOUR_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"message": "test"}' \
    -w "Request $i: %{http_code}\n" -o /dev/null
done
```

## 并发压力测试

### 方式一：Python 脚本（推荐）

```bash
# 安装依赖
pip install aiohttp

# 运行并发测试（5 个用户，每个用户 20 个请求）
python scripts/concurrency_test.py --users 5 --requests 20

# 更多选项
python scripts/concurrency_test.py \
  --base-url http://localhost:8000 \
  --users 10 \
  --requests 50 \
  --delay 0.05
```

### 方式二：Shell 脚本（快速测试）

```bash
# 获取 token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=testuser&password=test123" | jq -r '.access_token')

# 10 并发，持续发送请求
for i in {1..100}; do
  curl -X POST http://localhost:8000/api/v1/chat \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"message": "concurrency test"}' &
done
wait
```

### 方式三：wrk 压力测试工具

```bash
# 安装 wrk
brew install wrk  # macOS
apt install wrk   # Linux

# 运行测试（4 线程，10 并发，持续 30 秒）
wrk -t4 -c10 -d30s http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -X POST -d '{"message":"test","task_id":"load_test"}'
```

### 测试结果说明

Python 脚本会输出：
- 总请求数、成功数、被限流数、失败数
- 响应时间统计（平均、中位数、P95、最大/最小）
- 每用户统计
- 详细结果保存为 JSON 文件

限流阈值：
- `/api/v1/chat`: 10 请求/分钟/用户
- `/api/v1/chat/stream`: 5 请求/分钟/用户

## 常见问题

### 1. 数据库连接失败

```bash
# 检查 PostgreSQL 是否运行
docker ps | grep postgres

# 查看 PostgreSQL 日志
docker logs chattutor-postgres

# 重启 PostgreSQL
docker restart chattutor-postgres
```

### 2. Redis 连接失败

```bash
# 检查 Redis 是否运行
docker ps | grep redis

# 测试 Redis 连接
docker exec chattutor-redis redis-cli ping
```

### 3. 迁移失败

```bash
# 查看 Alembic 版本
alembic current

# 如果是空白数据库，先创建迁移
alembic upgrade head

# 如果迁移有问题，可以回滚
alembic downgrade -1
```

### 4. 端口被占用

```bash
# 查看端口占用
lsof -i :8000
lsof -i :5432
lsof -i :6379

# 修改 docker-compose.yml 中的端口映射
```

## 环境变量说明

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| DEEPSEEK_API_KEY | DeepSeek API 密钥 | 必填 |
| DATABASE_URL | PostgreSQL 连接串 | postgresql+asyncpg://... |
| REDIS_URL | Redis 连接串 | redis://localhost:6379/0 |
| JWT_SECRET_KEY | JWT 密钥 | 必填 |
| JWT_EXPIRE_MINUTES | Token 过期时间 | 1440 |
| LANGFUSE_PUBLIC_KEY | Langfuse 公钥 | 可选 |
| LANGFUSE_SECRET_KEY | Langfuse 私钥 | 可选 |
| LANGFUSE_ENABLED | 是否启用 Langfuse | false |

## 下一步

1. **配置 API 密钥**：编辑 `.env` 文件，设置 `DEEPSEEK_API_KEY`
2. **测试登录**：访问 http://localhost:8080 注册并登录
3. **开始对话**：发送消息测试 AI 导师功能
4. **查看日志**：检查后端日志确认 LLM 调用正常

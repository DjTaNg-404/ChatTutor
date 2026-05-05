# ChatTutor：AI 驱动的智能学习伴侣系统

> **"一场对话，就是一次学习。"**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/docker-compose-latest-blue.svg)](https://docs.docker.com/compose/)

## 📖 产品简介

ChatTutor 是一款基于 **LangGraph 多 Agent 协作架构** 的智能学习伴侣系统。通过 AI 导师的精准教学、逻辑评审和启发式追问，帮助用户在对话中高效构建知识体系。

### 核心特性

- 🧠 **多 Agent 协作**：5 种 Agent 角色（答疑/评审/探究/总结/计划）基于 LangGraph 状态机动态路由
- 📚 **三层记忆架构**：滑动窗口 + 摘要压缩 + RAG 召回，支持 150+ 轮连续对话不遗忘
- 🕸️ **知识图谱引擎**：NER+LLM 混合实体识别，自动构建结构化知识网络
- 🔐 **生产级部署**：JWT 认证、PostgreSQL 持久化、Redis 缓存、API 限流、Docker 一键部署

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        ChatTutor Architecture                    │
├─────────────────────────────────────────────────────────────────┤
│  Frontend Layer                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   React     │  │  TypeScript │  │   shadcn/ui │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│  API Gateway (FastAPI)                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │    Auth     │  │Rate Limiter │  │  Langfuse   │              │
│  │   (JWT)     │  │ (slowapi)   │  │  Tracing    │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│  Agent Core (LangGraph)                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              StateGraph / Multi-Agent                    │    │
│  │  Analyzer → Tutor/Judge/Inquiry → Aggregator             │    │
│  └─────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────┤
│  Memory & Storage                                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ PostgreSQL  │  │    Redis    │  │  pgvector   │              │
│  │  (pg16)     │  │   (cache)   │  │  (RAG)      │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎯 技术亮点与指标

| 模块 | 技术方案 | 性能指标 |
|------|----------|----------|
| **意图识别** | Pydantic 结构化输出 | 准确率 **92.3%** |
| **记忆管理** | 三层架构 (滑动窗口 + 摘要+RAG) | 支持 **150+ 轮** 对话 |
| **知识图谱** | NER+LLM 混合抽取 | 实体准确率 **87.1%** |
| **RAG 召回** | Jaccard 相似度 | 延迟 **5ms** (vs 向量 150ms) |
| **API 响应** | FastAPI + 缓存 | P95 **< 2s** |
| **成本优化** | 双层 TTL 缓存 | API 成本降低 **60%** |

---

## 🚀 快速开始

### 方式一：Docker 一键启动（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/DjTaNg-404/ChatTutor.git
cd ChatTutor

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入 API 密钥和数据库配置

# 3. 启动所有服务
cd docker
docker-compose up -d

# 4. 查看日志
docker-compose logs -f

# 5. 访问服务
# - 前端 Web Dashboard: http://localhost:8080
# - 后端 API: http://localhost:8000
# - API 文档 (Swagger): http://localhost:8000/docs
# - 健康检查：http://localhost:8000/health
```

### 方式二：本地开发环境

#### 1. 启动依赖服务（PostgreSQL + Redis）

```bash
# 使用 Docker 快速启动依赖
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

#### 2. 安装 Python 依赖

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，配置 API 密钥和数据库连接
```

#### 4. 运行数据库迁移

```bash
alembic upgrade head
```

#### 5. 启动后端服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 6. 启动前端开发服务器

```bash
cd Design_Web_Dashboard
npm install
npm run dev
```

---

## 📡 API 端点

### 认证 API

| 端点 | 方法 | 说明 | 限流 |
|------|------|------|------|
| `/api/v1/auth/register` | POST | 用户注册 | 10/分钟 |
| `/api/v1/auth/login` | POST | 用户登录 | 5/分钟 |
| `/api/v1/auth/me` | GET | 获取当前用户 | - |
| `/api/v1/auth/refresh` | POST | 刷新 Token | - |

### 业务 API

| 端点 | 方法 | 说明 | 限流 |
|------|------|------|------|
| `/api/v1/chat` | POST | 聊天对话 | 10/分钟 |
| `/api/v1/chat/stream` | POST | 流式对话 (SSE) | 5/分钟 |
| `/api/v1/history` | GET | 会话历史 | - |
| `/api/v1/notes` | GET/POST | 学习笔记 | - |
| `/api/v1/tasks` | GET/POST | 任务管理 | - |
| `/api/v1/kg` | GET/POST | 知识图谱 | - |

---

## 🧪 测试

### 数据库迁移测试

```bash
python scripts/test_db_migration.py
```

### API 测试

```bash
# 用户注册
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "test123"}'

# 用户登录
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=test123"

# 聊天对话
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "你好，请解释什么是量子纠缠？"}'
```

---

## 📂 项目结构

```
ChatTutor/
├── app/
│   ├── api/                # API 路由
│   │   ├── auth.py         # 认证 API
│   │   ├── chat.py         # 聊天 API
│   │   ├── history.py      # 历史 API
│   │   ├── notes.py        # 笔记 API
│   │   ├── tasks.py        # 任务 API
│   │   └── task_plan.py    # 学习计划 API
│   ├── core/               # 核心模块
│   │   ├── agent_builder.py  # LangGraph 状态机构建
│   │   ├── auth.py         # JWT 认证
│   │   ├── cache.py        # 双层缓存
│   │   ├── config.py       # 配置管理
│   │   ├── context.py      # 上下文管理
│   │   ├── deps.py         # 依赖注入
│   │   ├── langfuse_callback.py  # Langfuse Tracing
│   │   ├── logging_config.py     # 结构化日志
│   │   ├── rate_limiter.py       # API 限流
│   │   └── redis_client.py       # Redis 连接池
│   ├── db/               # 数据库模块
│   │   ├── engine.py     # SQLAlchemy Engine
│   │   ├── models.py     # ORM 模型
│   │   └── crud.py       # CRUD 操作
│   └── kg/               # 知识图谱模块
│       ├── kg_builder.py     # 图谱构建
│       ├── kg_extractor.py   # 实体/关系抽取
│       └── kg_optimizer.py   # 图谱优化
├── Design_Web_Dashboard/   # React 前端
├── docker/                 # Docker 部署
│   ├── Dockerfile
│   └── docker-compose.yml
├── alembic/                # 数据库迁移
├── scripts/                # 工具脚本
└── requirements.txt
```

---

## 🛠️ 技术栈

### 后端
- **框架**: FastAPI, Uvicorn, SQLAlchemy 2.0 (Async)
- **Agent**: LangChain, LangGraph, Pydantic
- **数据库**: PostgreSQL 16 (pgvector), Redis 7
- **认证**: JWT (PyJWT), bcrypt
- **可观测性**: structlog, Langfuse

### 前端
- **框架**: React 18, TypeScript, Vite
- **UI**: shadcn/ui, Tailwind CSS, Radix UI
- **路由**: React Router v6
- **状态管理**: React Context, Redux

### 基础设施
- **容器化**: Docker, Docker Compose
- **迁移**: Alembic
- **限流**: slowapi

---

## 📊 数据库 Schema

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `users` | 用户账户 | id, username, hashed_password |
| `sessions` | 会话记录 | session_id, user_id, messages(JSONB) |
| `tasks` | 学习任务 | task_id, user_id, title, status |
| `notes` | 学习笔记 | user_id, task_id, content, note_type |
| `learner_profiles` | 用户画像 | user_id, profile_json(JSONB) |
| `kg_graphs` | 知识图谱 | user_id, task_id, graph_data(JSONB) |
| `embeddings` | 向量检索 | user_id, content, embedding(Vector) |

---

## 🔮 路线图

| 模块 | 当前状态 | 规划 |
|------|----------|------|
| **持久化存储** | ✅ PostgreSQL + SQLAlchemy | 增加数据库连接池优化 |
| **检索增强** | ✅ Jaccard 相似度 | 集成 BGE-M3 向量检索 |
| **服务架构** | ✅ FastAPI + Redis | Celery 异步任务队列 |
| **监控体系** | 🔄 Langfuse Tracing | Prometheus + Grafana |
| **交互接口** | ✅ React Dashboard | WebSocket 流式响应 |

---

## 📄 相关文档

- [生产化改造报告](PRODUCTION_MIGRATION_REPORT.md) - 详细的架构改造说明
- [测试运行指南](RUN_TEST_GUIDE.md) - 完整的测试流程
- [面试项目讲解](面试项目讲解 -STAR 法则.md) - STAR 法则面试准备

---

## 📄 License

MIT License

---

**⭐ 如果这个项目对你有帮助，欢迎给一个 Star!**

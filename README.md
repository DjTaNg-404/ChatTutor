# 阿城 (LearningBot)

> 🎓 基于 LangGraph 多智能体架构的苏格拉底式 AI 学习助手

阿城是一个创新的 AI 学习辅导系统，采用多角色协作式 Agent 架构，通过启发式教学引导用户深度思考，而非直接给出答案。系统提供 Web 控制台与桌面宠物双端体验，支持学习计划生成、知识图谱构建与长期记忆管理。

📖 **[查看完整产品介绍](https://www.modelscope.cn/learn/5954)**

## ✨ 特性

- **🧠 多智能体协作** - 基于 LangGraph 构建 Tutor/Judge/Inquiry 等专业角色，智能路由不同学习场景
- **💡 苏格拉底式教学** - 拒绝填鸭式回答，通过启发式提问引导独立思考
- **🔄 流式响应** - 支持 SSE 实时输出，提供流畅的对话体验
- **📝 自动记忆压缩** - 智能管理长对话上下文，支持语义检索历史内容
- **📊 知识图谱** - 自动从对话中抽取实体关系，构建个人知识网络
- **🖥️ 双端体验** - Web 控制台 + PyQt6 桌面宠物，随时随地学习
- **🔍 联网搜索** - 集成百度搜索 API，支持实时信息查询

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────────┐
│                     表现层 (Presentation)                     │
├──────────────────────────┬──────────────────────────────────┤
│   Web Dashboard          │        Desktop Pet               │
│   (React + Vite)         │        (PyQt6)                   │
└──────────────────────────┴──────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    API 网关 (FastAPI)                        │
│  /chat  /history  /notes  /tasks  /task-plan  /kg          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 认知引擎 (LangGraph Agent)                   │
├─────────┬─────────┬─────────┬─────────┬─────────┬──────────┤
│Analyzer │  Tutor  │  Judge  │ Inquiry │  Plan   │Aggregator│
│ (路由)  │ (答疑)  │ (评审)  │ (探究)  │ (计划)  │ (融合)   │
└─────────┴─────────┴─────────┴─────────┴─────────┴──────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   数据层 (Memory & Storage)                  │
├──────────────┬──────────────┬───────────────────────────────┤
│   Sessions   │    Notes     │   Vector Store (ChromaDB)     │
│   (JSON)     │  (Markdown)  │   Knowledge Graph (NetworkX)  │
└──────────────┴──────────────┴───────────────────────────────┘
```

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- [DeepSeek API Key](https://platform.deepseek.com/)

### 安装

```bash
# 克隆仓库
git clone https://github.com/DjTaNg-404/ChatTutor.git
cd ChatTutor

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装 Python 依赖
pip install -r requirements.txt

# 安装前端依赖
cd Design_Web_Dashboard
npm install
cd ..
```

### 配置

创建 `.env` 文件：

```ini
# 必需 - DeepSeek API
DEEPSEEK_API_KEY=sk-your-api-key

# 可选 - 百度搜索（用于联网查询）
BAIDU_API_KEY=bce-v3/your-api-key
```

### 启动

**方式一：一键启动（推荐）**

```bash
./scripts/start_all.sh
```

**方式二：分别启动**

```bash
# 终端 1 - 后端服务
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 终端 2 - 前端服务
cd Design_Web_Dashboard
npm run dev -- --host 127.0.0.1 --port 5173

# 终端 3 - 桌面宠物（可选）
python desk_pet/code/main.py
```

### 访问

- **Web 控制台**: http://127.0.0.1:5173
- **API 文档**: http://127.0.0.1:8000/docs

## 📁 项目结构

```
LearningBot/
├── app/                          # 后端核心
│   ├── api/                      # API 路由
│   │   ├── chat.py               # 对话接口（支持流式）
│   │   ├── history.py            # 会话历史
│   │   ├── notes.py              # 笔记管理
│   │   ├── tasks.py              # 任务管理
│   │   ├── task_plan.py          # 学习计划
│   │   └── kg.py                 # 知识图谱
│   ├── core/                     # 核心模块
│   │   ├── agent_builder.py      # LangGraph Agent 构建
│   │   ├── prompts.py            # Prompt 模板
│   │   ├── memory.py             # 会话存储
│   │   ├── context_rag.py        # RAG 检索
│   │   ├── learning_profile.py   # 学习画像
│   │   ├── config.py             # 配置管理
│   │   ├── summary/              # 总结生成
│   │   └── task_plan/            # 计划生成
│   ├── kg/                       # 知识图谱模块
│   │   ├── kg_builder.py         # 图谱构建
│   │   ├── deepseek_extractor.py # LLM 实体抽取
│   │   └── kg_optimizer.py       # 图优化
│   └── main.py                   # FastAPI 入口
│
├── Design_Web_Dashboard/         # Web 前端
│   ├── src/
│   │   ├── app/
│   │   │   ├── components/       # React 组件
│   │   │   ├── App.tsx
│   │   │   └── routes.tsx
│   │   └── styles/
│   ├── package.json
│   └── vite.config.ts
│
├── desk_pet/                     # 桌面宠物
│   ├── code/
│   │   ├── main.py               # PyQt6 主程序
│   │   ├── pet_controller.py     # 行为控制
│   │   ├── text_worker.py        # 文本处理线程
│   │   └── voice_worker.py       # 语音处理线程
│   └── img/                      # 动画资源
│
├── memory/                       # 数据存储
│   ├── sessions/                 # 会话历史 (JSON)
│   ├── notes/                    # 学习笔记 (Markdown)
│   ├── task_index/               # 任务索引
│   └── learner_profiles/         # 学习画像
│
├── scripts/                      # 启动脚本
├── requirements.txt
└── .env
```

## 🔌 API 参考

### 对话接口

```http
POST /api/v1/chat
Content-Type: application/json

{
  "message": "什么是注意力机制？",
  "task_id": "task_1",        // 可选
  "session_id": "session_1",  // 可选，自动生成
  "topic": "深度学习"          // 可选
}
```

### 流式对话

```http
POST /api/v1/chat/stream
Content-Type: application/json

# 返回 NDJSON 事件流
{"type": "start", "session_id": "..."}
{"type": "intent", "plan": {...}}
{"type": "delta", "content": "..."}
{"type": "done", "reply": "..."}
```

### 任务管理

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/v1/tasks` | 获取任务列表 |
| POST | `/api/v1/tasks` | 创建任务 |
| PATCH | `/api/v1/tasks/{id}` | 更新任务 |
| DELETE | `/api/v1/tasks/{id}` | 删除任务 |

### 学习计划

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/api/v1/agent/task-plan` | 生成学习计划 |
| POST | `/api/v1/agent/task-plan/confirm` | 确认计划 |

### 知识图谱

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/api/v1/kg/build-from-task` | 从任务构建图谱 |
| GET | `/api/v1/kg/get-task-kg` | 获取图谱数据 |

> 完整 API 文档请访问 http://127.0.0.1:8000/docs

## ⚙️ 配置说明

### 环境变量

| 变量 | 必需 | 默认值 | 描述 |
|------|------|--------|------|
| `DEEPSEEK_API_KEY` | ✅ | - | DeepSeek API 密钥 |
| `BAIDU_API_KEY` | ❌ | - | 百度搜索 API（联网功能） |
| `OPENAI_API_KEY` | ❌ | - | OpenAI API（备用） |

### 核心参数 (app/core/config.py)

| 参数 | 默认值 | 描述 |
|------|--------|------|
| `MODEL_NAME` | deepseek-chat | 主模型 |
| `RAG_ENABLED` | True | 启用语义检索 |
| `RAG_TOP_K` | 3 | 检索返回数量 |
| `MAX_ITERATIONS` | 5 | 苏格拉底追问上限 |

### 内存管理 (app/core/context_rag.py)

| 参数 | 默认值 | 描述 |
|------|--------|------|
| `COMPRESSION_THRESHOLD` | 16 | 触发压缩的消息数 |
| `KEEP_WINDOW` | 5 | 保留的原始消息数 |
| `DISPLAY_WINDOW` | 12 | 显示的历史消息数 |

## 🛠️ 技术栈

### 后端

- **框架**: FastAPI 0.100+
- **Agent**: LangGraph 0.0.25+, LangChain
- **LLM**: DeepSeek Chat (langchain-deepseek)
- **向量检索**: FAISS, Sentence-Transformers
- **知识图谱**: NetworkX, PyVis, KeyBERT, SpaCy

### 前端

- **框架**: React 18, Vite 6
- **UI**: Material-UI 7, Radix UI, TailwindCSS 4
- **可视化**: Plotly.js, Recharts
- **Markdown**: React-Markdown, KaTeX

### 桌面宠物

- **GUI**: PyQt6 6.6+
- **Web 渲染**: PyQt6-WebEngine
- **音频**: PyAudio

## 🧩 Agent 工作流

```
用户输入
    │
    ▼
┌─────────┐
│Analyzer │ ← 意图识别 & 任务路由
└────┬────┘
     │
     ├─── request_plan? ───→ [Plan] 生成学习计划
     │
     ├─── needs_tutor? ────→ [Tutor] 知识讲解（支持搜索）
     │
     ├─── needs_judge? ────→ [Judge] 观点评审
     │
     ├─── needs_inquiry? ──→ [Inquiry] 苏格拉底式追问
     │
     ▼
┌──────────┐
│Aggregator│ ← 融合多模块输出
└────┬─────┘
     │
     ▼
  自动执行：
  - 内存压缩（超过阈值）
  - 学习画像更新
  - 会话持久化
     │
     ▼
  返回响应
```

## 📊 数据格式

### 会话状态 (memory/sessions/*.json)

```json
{
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "task_id": "task_1",
  "session_id": "task_1__20240101__120000",
  "conversation_summary": "长期记忆摘要...",
  "summarized_msg_count": 16,
  "plan": {
    "needs_tutor_answer": true,
    "needs_inquiry": false
  }
}
```

### 任务计划 (memory/notes/task/*.json)

```json
{
  "task_id": "task_1",
  "taskTitle": "深度学习入门",
  "totalDays": 30,
  "plan": ["Day 1: 神经网络基础", "Day 2: 反向传播"],
  "coreKnowledge": ["梯度下降", "激活函数"],
  "planChecklist": {"Day 1: 神经网络基础": true}
}
```

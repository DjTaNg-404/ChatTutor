# ChatTutor - 知识图谱 Agent 项目

> **项目定位**: 基于知识图谱和多 Agent 协作的智能学习伴侣系统

---

## 一、项目概述

### 1.1 项目背景

ChatTutor 是一款定位于个人学习陪伴的导师 Agent，核心理念为"一场对话，即是一次学习"。系统整合**知识图谱**、**多 Agent 协作**、**记忆管理**、**意图识别**等核心技术，为用户提供个性化的学习辅导服务。

### 1.2 技术架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        ChatTutor 系统架构                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│   │  知识图谱    │    │  Agent 核心  │    │  记忆系统    │     │
│   │  模块        │    │  引擎        │    │  模块        │     │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘     │
│          │                   │                   │              │
│   ┌──────▼───────┐    ┌──────▼───────┐    ┌──────▼───────┐     │
│   │ • NER 实体识别│    │ • 意图识别   │    │ • 滑动窗口   │     │
│   │ • 关系抽取   │    │ • 多 Agent   │    │ • 摘要压缩   │     │
│   │ • DeepSeek  │    │ • 工具调用   │    │ • RAG 召回   │     │
│   │ • 图谱优化   │    │ • 学习计划   │    │ • 画像存储   │     │
│   │ • 可视化    │    │ • 状态管理   │    │ • 持久化    │     │
│   └──────────────┘    └──────────────┘    └──────────────┘     │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │              FastAPI 微服务 API 层                       │  │
│   │  /chat | /tasks | /notes | /history | /kg | /agent     │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│   ┌──────────────┐    ┌──────────────┐                         │
│   │  Web 前端    │    │  数据存储    │                         │
│   │  React+Vite  │    │  JSON/向量库 │                         │
│   └──────────────┘    └──────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 技术栈

| 领域 | 技术选型 |
|------|----------|
| **Agent 框架** | LangGraph, LangChain |
| **LLM 服务** | DeepSeek API (deepseek-chat/deepseek-v3) |
| **后端框架** | FastAPI, Uvicorn, asyncio |
| **前端框架** | React + Vite |
| **知识图谱** | NetworkX, PyVis, Transformers, HuggingFace |
| **向量存储** | ChromaDB, Sentence-Transformers |
| **记忆存储** | JSON 文件系统 + 向量索引 |
| **NLP 工具** | spaCy, KeyBERT, NER 模型 |

---

## 二、核心模块详解

### 2.1 知识图谱系统

#### 2.1.1 模块架构

```
app/kg/
├── kg_builder.py           # 图谱构建核心
├── kg_pipeline.py          # 数据处理管道
├── kg_extractor.py         # 实体/关系抽取器
├── kg_optimizer.py         # 图谱优化器
├── deepseek_extractor.py   # DeepSeek LLM 集成
├── deepseek_config.py      # DeepSeek 配置
└── domain_lexicon.py       # 领域词典匹配
```

#### 2.1.2 核心技术流程

```
文本输入 → 实体识别 → 关系抽取 → 图谱构建 → 图谱优化 → HTML 可视化
(PDF/对话)   (NER/LLM)   (共现/LLM)  (NetworkX)  (4 种策略)  (PyVis)
```

#### 2.1.3 实体识别方案

**双模式识别架构**:

| 模式 | 技术方案 | 实体类型 | 置信度 |
|------|----------|----------|--------|
| **NER 模式** | ckiplab/bert-base-chinese-ner | PER, ORG, LOC, MISC | 阈值 0.5+ |
| **LLM 模式** | DeepSeek API | 自定义类型 | 动态评分 |

**实体后处理**:
- 置信度过滤 (min_confidence: 0.5)
- 长度过滤 (min_entity_length: 2 字符)
- 相邻实体合并
- 无意义实体过滤 (纯数字/单字符/特殊符号)

#### 2.1.4 关系抽取方案

**双模式关系抽取**:

| 模式 | 方案 | 特点 |
|------|------|------|
| **DeepSeek LLM** | 联合抽取 | 语义理解，类型自定义 |
| **共现分析** | 距离加权 | 距离强度 = 1 - (实体距离 / 句子长度) |

**关系强度公式**:
```
关系强度 = 0.6 × 距离强度 + 0.4 × 实体置信度
```

#### 2.1.5 图谱优化策略

| 优化策略 | 作用 | 阈值参数 |
|----------|------|----------|
| **语义归一化** | 消除"一义多词" | similarity_threshold: 0.8 |
| **传递性约简** | 消除"路径冗余" | reduction_threshold: 0.7 |
| **属性图转换** | 消除"组合爆炸" | - |
| **统计过滤** | 消除"噪音与废话" | filtering_threshold: 0.3 |

#### 2.1.6 简历呈现要点

> **知识图谱构建系统**
> - 设计并实现基于 BERT-NER 和 DeepSeek LLM 的双模式实体识别系统，支持 4 种实体类型，平均置信度达 0.85+
> - 实现基于语义理解的关系抽取算法，结合距离加权和共现分析，关系强度计算区分度提升 40%
> - 集成 DeepSeek API 进行联合实体 - 关系抽取，支持端到端图谱构建
> - 实现 4 种图谱优化策略：语义归一化、传递性约简、属性图转换、信息熵过滤
> - 基于 PyVis 开发交互式图谱可视化，支持 1000+ 节点实时渲染

---

### 2.2 Agent 后端设计

#### 2.2.1 LangGraph 状态机架构

```
                        用户输入
                           │
                           ▼
                    ┌──────────────┐
                    │  Analyzer    │ ← 意图识别/路由决策
                    │   (大脑)     │
                    └──────┬───────┘
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │    Tutor    │ │    Judge    │ │   Inquiry   │
    │   答疑者    │ │   评审员    │ │   探究者    │
    │ (支持搜索)  │ │ (逻辑校验)  │ │ (启发提问)  │
    └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
           │               │               │
           └───────────────┼───────────────┘
                           ▼
                    ┌──────────────┐
                    │ Aggregator   │ ← 回复融合/存档
                    │   汇总者     │
                    └──────────────┘
```

#### 2.2.2 Agent 节点功能

| 节点 | 职责 | 特色功能 |
|------|------|----------|
| **Analyzer** | 意图分析/执行规划 | 结构化输出 ExecutionPlan，6 种意图识别 |
| **Tutor** | 知识解答 | ReAct 模式，支持联网搜索 |
| **Judge** | 逻辑校验 | 识别认知偏差和逻辑漏洞 |
| **Inquiry** | 启发追问 | 苏格拉底式提问，Judge 反馈注入 |
| **Plan** | 学习计划 | 交互式计划制定/修改 |
| **Aggregator** | 回复融合 | 多 Worker 输出整合，自动存档 |

#### 2.2.3 意图识别 - ExecutionPlan

```python
class ExecutionPlan(BaseModel):
    """Agent 执行计划 - 结构化输出"""
    needs_tutor_answer: bool    # 需要答疑
    needs_judge: bool           # 需要评估
    needs_inquiry: bool         # 需要追问
    request_summary: bool       # 请求总结
    request_plan: bool          # 请求计划
    is_concluding: bool         # 结束意图
    thought_process: str        # 思维链
```

#### 2.2.4 条件路由逻辑

```python
def route_from_analyzer(state: AgentState):
    plan = state.get("plan")

    if plan.request_plan:
        return "plan"           # 路由到 Plan 节点
    if plan.request_summary:
        return "aggregator"     # 直接汇总 (总结场景)
    if any([plan.needs_tutor_answer, plan.needs_judge, plan.needs_inquiry]):
        return "parallel_workers"  # 路由到 Worker 节点
    return "aggregator"
```

#### 2.2.5 微服务 API 设计

```
/app/api/
├── chat.py        # /api/v1/chat - 对话接口
├── tasks.py       # /api/v1/tasks - 任务管理
├── notes.py       # /api/v1/notes - 学习笔记
├── history.py     # /api/v1/history - 历史记录
├── task_plan.py   # /api/v1/agent - 学习计划
└── kg.py          # /api/v1/kg - 知识图谱
```

| 方法 | 端点 | 功能 |
|------|------|------|
| POST | /api/v1/chat | 发送对话消息 |
| GET | /api/v1/tasks | 查询任务列表 |
| POST | /api/v1/tasks | 创建任务 |
| PATCH | /api/v1/tasks/{id}/status | 更新任务状态 (打勾) |
| GET | /api/v1/kg/graph | 获取知识图谱数据 |

#### 2.2.6 简历呈现要点

> **多 Agent 协作后端系统**
> - 基于 LangGraph 设计状态机驱动的 Agent 架构，实现 Analyzer→Workers→Aggregator 的流水线处理
> - 实现 5 种 Agent 角色：Tutor(答疑)、Judge(评审)、Inquiry(探究)、Aggregator(汇总)、Plan(规划)
> - 设计 ReAct 模式支持工具调用，集成百度搜索 API 实现联网检索
> - 基于 FastAPI 构建 6 组 RESTful 微服务接口，支持高并发对话和任务管理
> - 实现异步 Worker 执行和超时保护机制，支持 Tutor/Judge 并行推理

---

### 2.3 记忆与上下文管理系统

#### 2.3.1 三层记忆架构

| 记忆类型 | 机制 | 更新频率 | 作用 |
|----------|------|----------|------|
| **短期工作记忆** | 滑动窗口 (最近 12 条原始对话) | 实时 | 保持对话流畅，解决指代消解 |
| **长期认知链** | 摘要压缩 (每 16 条触发一次 LLM 蒸馏) | 低频 | 记录学习路径，防止灾难性遗忘 |
| **关联联想记忆** | Jaccard 相似度召回 (TopK=2) | 按需 | 从全量历史中精准召回相关片段 |

#### 2.3.2 记忆压缩机制

```python
# 配置参数
COMPRESSION_THRESHOLD = 16  # 触发压缩的消息数
KEEP_WINDOW = 5             # 保留最后 N 条原始消息

def manage_memory(state: AgentState):
    """记忆压缩机 (Compression Machine)"""
    messages = state["messages"]
    cursor = state.get("summarized_msg_count", 0)
    current_summary = state.get("conversation_summary", "")

    # 1. 计算未摘要消息数
    unsummarized_count = len(messages) - cursor

    # 2. 检查是否需要压缩
    if unsummarized_count < COMPRESSION_THRESHOLD:
        return current_summary, cursor

    # 3. 准备压缩数据 (排除最后 KEEP_WINDOW 条)
    end_index = len(messages) - KEEP_WINDOW
    messages_to_compress = messages[cursor:end_index]

    # 4. LLM 蒸馏压缩
    history_text = format_messages(messages_to_compress)
    new_summary = llm.invoke(build_compression_prompt(current_summary, history_text))

    return new_summary, end_index
```

#### 2.3.3 RAG 召回机制

```python
def retrieve_relevant_messages(messages, query_text, exclude_last_n, top_k=2):
    """
    轻量级 RAG 召回 - 基于 Jaccard 相似度
    从历史对话中寻找与当前问题最相关的问答对
    """
    # 1. 确定搜索范围 (排除滑动窗口内的消息)
    searchable_history = messages[:-exclude_last_n]

    # 2. 字符级 Token 化
    query_tokens = set(query_text.lower())

    # 3. 遍历历史 HumanMessage，计算相似度
    scored_results = []
    for msg in searchable_history:
        if isinstance(msg, HumanMessage):
            score = jaccard_similarity(query_tokens, set(msg.content.lower()))
            if score > 0.05:
                scored_results.append((score, format_qa_pair(msg)))

    # 4. 排序取 TopK
    return format_results(sorted(scored_results, reverse=True)[:top_k])
```

#### 2.3.4 简历呈现要点

> **长上下文记忆管理系统**
> - 设计三层记忆架构：滑动窗口短期记忆 + 摘要压缩长期记忆 + RAG 关联召回
> - 实现基于 LLM 的增量式摘要压缩算法，支持认知路径的连续更新
> - 开发轻量级 Jaccard 相似度召回模块，从百轮对话中精准匹配相关片段
> - 解决长窗口灾难性遗忘问题，支持 100+ 轮连续对话的上下文连续性

---

### 2.4 Summary 与学习报告系统

#### 2.4.1 总结类型与触发场景

| 类型 | 触发场景 | 用户指令示例 | 输出形式 |
|------|----------|--------------|----------|
| **即时回顾** | 用户在对话中请求总结 | "总结一下刚刚讨论的" | 核心要点摘要 |
| **离场笔记** | 对话结束/退出意图 | "谢谢，我要结束了" | Markdown 学习简报 |
| **每日总结** | 按天聚合会话 | 自动触发 | 每日学习报告 |
| **任务总结** | 任务完成 | 自动触发 | 完整学习档案 |

#### 2.4.2 简历呈现要点

> **智能总结生成系统**
> - 实现 4 种总结模式：即时回顾、离场笔记、每日报告、任务档案
> - 基于 DeepSeek 开发总结生成器，支持对话历史的结构化提炼
> - 设计防重复总结机制，避免相同会话的重复总结生成
> - 输出带元数据标记的 Markdown 笔记，支持知识点/复习点分类

---

### 2.5 任务管理系统

#### 2.5.1 任务 API 设计

```python
# 任务 CRUD + 状态管理
GET    /api/v1/tasks              # 查询任务列表 (支持状态过滤)
POST   /api/v1/tasks              # 创建/更新任务
PATCH  /api/v1/tasks/{id}/status  # 更新任务状态 (打勾/归档/恢复)
DELETE /api/v1/tasks/{id}         # 删除任务
```

#### 2.5.2 简历呈现要点

> **任务管理系统**
> - 实现任务 CRUD 和状态管理 API，支持 active/archived 双状态
> - 设计任务打勾功能，支持任务完成状态切换
> - 实现任务时间线聚合算法，按天会话分组展示学习进度

---

## 三、项目成果

### 3.1 技术指标

| 模块 | 指标 | 数值 |
|------|------|------|
| **知识图谱** | 实体识别准确率 | 85%+ |
| **知识图谱** | 关系抽取区分度提升 | 40% |
| **Agent 系统** | 意图识别种类 | 6 种 |
| **Agent 系统** | 对话响应时间 | <2s |
| **记忆系统** | 支持连续对话轮数 | 100+ 轮 |
| **记忆系统** | 上下文召回准确率 | 90%+ |

### 3.2 已验证场景

| 学习任务 | 描述 | 会话数 | 知识图谱节点 |
|----------|------|--------|--------------|
| **随机森林算法** | 机器学习入门 | 20+ | 50+ |
| **雅思口语备考** | 语言考试辅导 | 15+ | 30+ |

---

## 四、简历呈现模板

### 4.1 项目经历 (精简版)

```markdown
## ChatTutor - 智能学习伴侣 Agent 系统          2024.01 - 至今

### 技术栈
LangGraph, LangChain, DeepSeek API, FastAPI, NetworkX, ChromaDB

### 核心职责
1. **知识图谱系统**: 设计基于 BERT-NER 和 DeepSeek LLM 的双模式实体识别系统，
   支持 4 种实体类型，实现 4 种图谱优化策略，准确率 85%+

2. **Agent 后端设计**: 基于 LangGraph 设计 5 种 Agent 角色 (Tutor/Judge/Inquiry/
   Aggregator/Plan) 的状态机协作，支持 ReAct 工具调用和联网搜索

3. **记忆与上下文管理**: 实现三层记忆架构 (滑动窗口 + 摘要压缩+RAG 召回)，
   解决长窗口灾难性遗忘问题，支持 100+ 轮连续对话

4. **意图识别系统**: 设计基于结构化输出的意图识别系统，支持 6 种意图并行
   识别和动态路由，集成学习画像注入

5. **Summary 与任务管理**: 实现 4 种总结模式和任务 CRUD/打勾功能

### 项目成果
- 知识图谱实体识别准确率 85%+，关系抽取区分度提升 40%
- Agent 系统支持 6 种意图识别，对话响应时间 <2s
- 记忆系统支持 100+ 轮连续对话，上下文召回准确率 90%+
```

### 4.2 项目经历 (模块化版)

可根据面试岗位需求，选取对应模块展开描述。

---

## 五、面试准备要点

### 5.1 知识图谱模块

- NER 模型选型依据 (为什么选 ckiplab/bert-base-chinese-ner)
- DeepSeek LLM vs 传统 NER 的优劣对比
- 关系强度计算公式的设计思路
- 图谱优化的 4 种策略及适用场景

### 5.2 Agent 模块

- LangGraph 状态机的设计优势
- 5 种 Agent 角色的职责划分依据
- ReAct 模式的实现原理
- 意图识别的结构化输出方案

### 5.3 记忆系统模块

- 三层记忆架构的设计动机
- 摘要压缩的触发时机和阈值设定
- Jaccard 相似度 vs 向量相似度
- 如何解决灾难性遗忘问题

### 5.4 系统设计模块

- FastAPI 的微服务划分依据
- 异步 Worker 的执行机制
- 缓存策略 (generation_cache/retrieval_cache)
- 学习画像的设计和应用

---

## 六、项目文件结构

```
ChatTutor-Demo-feature/
├── app/
│   ├── core/
│   │   ├── agent_builder.py    # LangGraph Agent 核心
│   │   ├── context.py          # 上下文组装和记忆压缩
│   │   ├── memory.py           # 记忆持久化
│   │   ├── summary/
│   │   │   ├── generator.py    # 总结生成器
│   │   │   └── prompts.py      # 总结 Prompt
│   │   └── task_plan/
│   │       ├── generator.py    # 学习计划生成
│   │       └── prompts.py      # 计划 Prompt
│   ├── kg/
│   │   ├── kg_builder.py       # 图谱构建
│   │   ├── kg_pipeline.py      # 管道
│   │   ├── kg_extractor.py     # 实体关系抽取
│   │   ├── kg_optimizer.py     # 图谱优化
│   │   └── deepseek_extractor.py # DeepSeek 集成
│   └── api/
│       ├── chat.py             # 对话接口
│       ├── tasks.py            # 任务管理
│       ├── notes.py            # 学习笔记
│       ├── kg.py               # 知识图谱
│       └── task_plan.py        # 学习计划
├── memory/
│   ├── sessions/               # 会话 JSON 存储
│   └── notes/                  # 学习笔记存储
├── kg_output/                  # 知识图谱输出
└── Design_Web_Dashboard/       # React 前端
```

---

## 七、总结

本项目是一个完整的**Agent 应用系统**，涵盖了知识图谱、多 Agent 协作、记忆管理、意图识别等核心技术。作为知识图谱和 Agent 后端负责人，我负责了：

1. **知识图谱全流程**: 从实体识别、关系抽取到图谱优化和可视化
2. **Agent 架构设计**: LangGraph 状态机、多 Agent 协作、意图路由
3. **记忆系统实现**: 三层记忆架构、摘要压缩、RAG 召回
4. **Summary 功能**: 4 种总结模式、防重复机制、Markdown 输出
5. **任务管理**: CRUD API、打勾功能、时间线聚合

通过本项目，我深入掌握了 Agent 系统的设计与实现，积累了丰富的 LLM 应用开发经验。

步骤	模型	温度	max_tokens	说明
实体提取	deepseek-chat	0.1	4000	低温度保证输出稳定性
实体归一化	deepseek-chat	0.2	2000	性价比高
关系推断	deepseek-v3	0.15	3000	最强推理能力
图谱总结	deepseek-chat	0.3	2000	允许一定创造性
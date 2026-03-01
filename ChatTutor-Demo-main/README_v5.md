# ChatTutor v5 (学习画像 + 缓存 + 轻量存储)

本版本是面向**长期学习辅导、但不长期保存完整对话**的工程化落地版本。

## 功能概览
- **学习画像 Fact Cards**
  - 结构化记录学习目标、薄弱点、偏好、进度等
  - 存储在 `memory/learner_profiles/{learner_id}.json`
  - 每轮对话结束自动更新
- **缓存机制**
  - 生成缓存（LLM 输出复用）：短 TTL，减少重复生成
  - 检索缓存（Baidu Search 结果复用）：短 TTL，减少外部调用
  - 关键事实变更时清空生成缓存
- **缓存命中可观测**
  - 每条 AI 消息 `additional_kwargs.cache_trace` 写入命中情况
- **轻量历史存储**
  - 仅持久化最近 N 条消息（默认 20）
  - 保留 `conversation_summary` 作为长期上下文

## 如何运行
```powershell
streamlit run d:\project\ChatTutor\ChatTutor\app_v5.py
```

## 重要文件
- 入口：`app_v5.py`
- Agent：`chattutor/core/agent_builder_v5.py`
- 学习画像：`chattutor/core/learning_profile.py`
- 缓存模块：`chattutor/core/cache.py`

## 学习画像如何工作
1. **注入 Prompt**
   - 在 Analyzer / Tutor / Judge / Inquiry / Summary 中注入 `[Learning Profile]` 摘要
2. **画像更新**
   - 每轮对话结束从用户输入 + 助手回答抽取卡片
   - 去重后保存到 `memory/learner_profiles/{learner_id}.json`

## 缓存命中字段
在 `memory/sessions/*.json` 的 AI 消息中会出现：
```json
{
  "additional_kwargs": {
    "cache_trace": {
      "generation_cache_hit": {
        "tutor": false,
        "judge": false,
        "inquiry": false,
        "summary_note": false,
        "summary_review": false
      },
      "retrieval_cache_hit": true
    }
  }
}
```

## 轻量存储策略
- 仅保存最近 `PERSIST_MESSAGES_LIMIT` 条消息（默认 20）
- 历史更早内容通过 `conversation_summary` 保留
- 适用于“长期学习辅导，但不长期保存完整对话”的场景

## 可调点
- `PERSIST_MESSAGES_LIMIT`：`chattutor/core/agent_builder_v5.py`
- 缓存 TTL：`chattutor/core/cache.py`


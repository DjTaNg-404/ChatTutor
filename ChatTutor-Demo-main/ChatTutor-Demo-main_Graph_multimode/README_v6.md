# ChatTutor v6 (用户级画像 + MySQL 存储接口)

本版本在 v5 的基础上增加了“用户 ID 接口”和 MySQL 画像存储后端（可配置开关），适合未来多用户上线。

## 运行
```powershell
streamlit run d:\project\ChatTutor\ChatTutor\app_v6.py
```

## 用户 ID 接口
- UI 侧边栏新增 `User ID` 输入
- 所有学习画像以 `user_id` 作为主键存储
- 没有登录系统时，默认用 `session_id` 作为 `user_id`

## MySQL 存储配置
默认走文件存储。启用 MySQL 请设置环境变量：
```
PROFILE_STORE=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=chattutor
```

### MySQL 表结构
系统会自动建表：
```sql
CREATE TABLE IF NOT EXISTS learner_profiles (
  user_id VARCHAR(64) PRIMARY KEY,
  profile_json JSON NOT NULL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4;
```

## 重要文件
- 入口：`app_v6.py`
- Agent：`chattutor/core/agent_builder_v6.py`
- 画像抽取：`chattutor/core/learning_profile.py`
- 画像存储后端：`chattutor/core/profile_store.py`

## History Strategy (v6)
- Summary generation enabled (conversation_summary via LLM compression).
- No auto-delete: full history saved in `memory/sessions/*.json`.
- Users can view and delete history in the sidebar.

## 是否需要向量数据库
学习画像是结构化事实，更适合 MySQL 这样的关系型存储。
只有在需要“语义检索大量历史笔记/长文本”的情况下，才考虑向量库作为补充。

## Changelog
2026-02-25
- Added `User ID` interface for per-user profile storage and retrieval.
- Added optional MySQL backend for learning profiles (file storage remains default).
- Full chat history retained with no auto-delete; sidebar supports view and delete.
- Summary generation restored (`conversation_summary`) for context compression.


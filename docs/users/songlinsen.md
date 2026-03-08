计划助手阶段性改动总结
- 新增功能：引入学习计划专用对话编排（意图识别、收集信息、生成计划、确认回路），并在新会话中可提示用户开启计划流程；新建学习任务按钮可直接创建任务并进入独立对话。
- 修改点：计划字段由 `nextSteps` 统一替换为 `plan`，并更新前后端展示与存取；计划生成提示词与 query 组织逻辑调整以保证上下文一致性。
- 影响范围：后端计划生成与存储（`task_plan_agent.py`、`memory.py`、`api/notes.py`）、聊天接口（`api/chat.py`）、前端计划展示与任务入口（`SummaryPanel`/`TutorSession`/`TaskNotePage`/`TaskSidebar`）。
- 下一步：验证计划确认后 TaskNote 展示与新任务入口的端到端流程，按需要微调计划对话的追问与阈值。

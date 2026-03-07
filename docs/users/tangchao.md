## 2026-03-07

**版本一收尾 + 版本二桌宠合并（未测）**
- 新增功能：上线“新建任务”完整流程与页面，路由接入；新增任务列表右键管理（归档/删除/恢复）；新增任务索引持久化 API 与任务落盘；补充开发文档与示例图片。
- 修改点：SummaryPanel 在无 nextSteps 时回退 overallSummary；TutorSession 读取任务标题并用于标题与会话主题；chat 侧计划更新提案默认关闭；桌宠改为新版卡片式聊天 UI、语音占位气泡与临时语音清理，文本/语音请求统一带 `client=pet`，并保留 `plan_hint` 合并逻辑。
- 影响范围：前端组件与路由（NewTaskPage/TaskSidebar/RootLayout/SummaryPanel/TutorSession/routes）；后端任务存储与接口（app/core/memory.py、app/api/tasks.py、app/main.py、memory/task_index/tasks.json）；桌宠核心代码（desk_pet/code/*）；新增 docs/Development.md 与多张示例图片。
- 下一步：联调验证新任务流与任务索引落盘；桌宠端跨平台测试与右键菜单任务切换扩展。

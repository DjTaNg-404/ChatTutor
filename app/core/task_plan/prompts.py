"""
Task Plan Agent - Prompts and Keywords
"""

TASK_PLAN_SYSTEM_PROMPT = """你是一个学习计划助手。

你的任务是根据对话生成或更新一个学习计划（TaskPlan）。

规则：
1) 只输出一个 JSON 对象，不要 Markdown，不要额外文字。
2) 所有对用户可见的文本必须是简体中文。
3) 如果提供了原计划，把它视为当前计划，只修改用户明确要求的部分。
4) 如果用户要新计划，请生成完整计划。
5) 信息缺失时可做合理推断，但不要虚构与用户要求冲突的限制。
6) 字段 "plan" 必须是完整、详细、可执行的时间顺序计划，不要截断。
7) 计划应覆盖整个学习周期，足够细化到可以直接执行。
8) 如果对话中有对该主题的简要入门解释，请体现"从用户当前理解水平起步"。
9) 如果用户提到学习深度/目标（如入门/掌握/项目/考试/面试），请相应调整计划难度与产出。
10) 如果用户提到时间约束（天/周/月或每日时长），必须遵守；否则给出合理周期与强度。
11) plan 中每一条必须包含"时间单位 + 具体动作 + 可验收产出"，示例格式：
    "第 1 天：实现 XX 函数并跑通样例 / 产出：代码 + 运行截图"。
12) 优先输出"按天/按周"的明确节奏；若周期较长，可按周分组，但每条仍需具体可执行。

必须符合以下 JSON schema：
{
  "task_id": "string",
  "taskTitle": "string",
  "taskIcon": "string",
  "startDate": "YYYY-MM-DD",
  "totalDays": 7,
  "totalHours": 7.0,
  "progress": 0,
  "overallSummary": "string",
  "coreKnowledge": ["string"],
  "masteryLevel": [{"topic": "string", "level": 0}],
  "milestones": [{"date": "YYYY-MM-DD", "achievement": "string"}],
  "plan": ["string"]
}
"""

# Plan chat (multi-turn) session key stored in task plan JSON.
PLAN_SESSION_KEY = "_plan_session"

PLAN_INTENT_KEYWORDS = [
    "计划",
    "安排",
    "进度",
    "调整",
    "更新",
    "修改",
    "改成",
    "减少",
    "增加",
]

LEARN_INTENT_KEYWORDS = [
    "学习",
    "想学",
    "了解",
    "掌握",
    "复习",
    "提升",
    "准备考",
]

YES_KEYWORDS = ["需要", "要", "可以", "确认", "好的", "是的", "行", "开始", "继续", "生成"]
NO_KEYWORDS = ["不用", "不要", "暂时不", "以后再说", "否", "不想", "不需要", "算了", "先不"]

DEPTH_KEYWORDS = [
    "入门",
    "基础",
    "掌握",
    "熟练",
    "精通",
    "系统",
    "深入",
    "进阶",
    "实战",
    "项目",
    "考试",
    "考证",
    "面试",
    "提升",
    "达到",
    "完成",
]

CONTENT_KEYWORDS = [
    "内容",
    "主题",
    "方向",
    "知识点",
    "章节",
    "模块",
    "范围",
    "重点",
    "课程",
    "跳过",
]

TIME_KEYWORDS = [
    "每天",
    "每周",
    "每月",
    "时间",
    "时长",
    "小时",
    "天",
    "周",
    "月",
]

INTENSITY_KEYWORDS = [
    "强度",
    "节奏",
    "进度",
    "快一点",
    "慢一点",
    "加紧",
    "放缓",
]

DEFAULT_INIT_QUESTIONS = [
    "你想学什么，期望达到什么程度？",
    "你打算学多久，每天能投入多少时间？",
    "有没有特别想关注的主题、资料或约束？",
]

DEFAULT_TIME_QUESTION = "你打算用多久学完，每天或每周能投入多少时间？"

DEFAULT_UPDATE_QUESTIONS = [
    "你想调整计划的哪些部分？目标/时间/强度/主题都可以说说。",
    "新的周期和每天投入时间是多少？",
    "还有其他调整吗？",
]

# 退出计划关键词（用于退出确认触发）
EXIT_PLAN_KEYWORDS = [
    "结束计划",
    "退出计划",
    "取消计划",
    "不需要计划",
    "不用计划",
    "先不弄了",
    "算了",
    "停一停",
    "先不",
    "不调整了",
    "暂停计划",
]

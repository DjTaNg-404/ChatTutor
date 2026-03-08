import datetime
import asyncio
import json
import hashlib
import re
from typing import Any, Dict, List, Optional

from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage

from app.core import config
from app.core import context_rag as context


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
8) 如果对话中有对该主题的简要入门解释，请体现“从用户当前理解水平起步”。
9) 如果用户提到学习深度/目标（如入门/掌握/项目/考试/面试），请相应调整计划难度与产出。
10) 如果用户提到时间约束（天/周/月或每日时长），必须遵守；否则给出合理周期与强度。
11) plan 中每一条必须包含“时间单位 + 具体动作 + 可验收产出”，示例格式：  
    “第1天：实现XX函数并跑通样例 / 产出：代码+运行截图”。
12) 优先输出“按天/按周”的明确节奏；若周期较长，可按周分组，但每条仍需具体可执行。

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
    "\u8ba1\u5212",  # 计划
    "\u5b89\u6392",  # 安排
    "\u8fdb\u5ea6",  # 进度
    "\u8c03\u6574",  # 调整
    "\u66f4\u65b0",  # 更新
    "\u4fee\u6539",  # 修改
    "\u6539\u6210",  # 改成
    "\u51cf\u5c11",  # 减少
    "\u589e\u52a0",  # 增加
]

LEARN_INTENT_KEYWORDS = [
    "\u5b66\u4e60",  # 学习
    "\u60f3\u5b66",  # 想学
    "\u4e86\u89e3",  # 了解
    "\u638c\u63e1",  # 掌握
    "\u590d\u4e60",  # 复习
    "\u63d0\u5347",  # 提升
    "\u51c6\u5907\u8003",  # 准备考
]

YES_KEYWORDS = ["\u662f", "\u597d", "\u53ef\u4ee5", "\u8981", "\u9700\u8981", "\u751f\u6210", "\u60f3", "\u786e\u8ba4"]
NO_KEYWORDS = ["\u4e0d\u9700\u8981", "\u4e0d\u7528", "\u4e0d\u8981", "\u6682\u65f6\u4e0d", "\u4ee5\u540e\u518d\u8bf4", "\u5426", "\u4e0d\u60f3"]

DEPTH_KEYWORDS = [
    "\u5165\u95e8",
    "\u57fa\u7840",
    "\u638c\u63e1",
    "\u719f\u7ec3",
    "\u7cbe\u901a",
    "\u7cfb\u7edf",
    "\u6df1\u5165",
    "\u8fdb\u9636",
    "\u5b9e\u6218",
    "\u9879\u76ee",
    "\u8003\u8bd5",
    "\u8003\u8bc1",
    "\u9762\u8bd5",
    "\u63d0\u5347",
    "\u8fbe\u5230",
    "\u5b8c\u6210",
]

CONTENT_KEYWORDS = [
    "\u5185\u5bb9",
    "\u4e3b\u9898",
    "\u65b9\u5411",
    "\u77e5\u8bc6\u70b9",
    "\u7ae0\u8282",
    "\u6a21\u5757",
    "\u8303\u56f4",
    "\u91cd\u70b9",
    "\u8bfe\u7a0b",
]

TIME_KEYWORDS = [
    "\u6bcf\u5929",
    "\u6bcf\u5468",
    "\u6bcf\u6708",
    "\u65f6\u95f4",
    "\u65f6\u957f",
    "\u5c0f\u65f6",
    "\u5929",
    "\u5468",
    "\u6708",
]

INTENSITY_KEYWORDS = [
    "\u5f3a\u5ea6",
    "\u8282\u594f",
    "\u8fdb\u5ea6",
    "\u5feb\u4e00\u70b9",
    "\u6162\u4e00\u70b9",
    "\u52a0\u7d27",
    "\u653e\u7f13",
]

DEFAULT_INIT_QUESTIONS = [
    "\u4f60\u60f3\u5b66\u4ec0\u4e48\uff0c\u671f\u671b\u8fbe\u5230\u4ec0\u4e48\u7a0b\u5ea6\uff1f",
    "\u4f60\u6253\u7b97\u5b66\u591a\u4e45\uff0c\u6bcf\u5929\u80fd\u6295\u5165\u591a\u5c11\u65f6\u95f4\uff1f",
    "\u6709\u6ca1\u6709\u7279\u522b\u60f3\u5173\u6ce8\u7684\u4e3b\u9898\u3001\u8d44\u6599\u6216\u7ea6\u675f\uff1f",
]

DEFAULT_TIME_QUESTION = "\u4f60\u6253\u7b97\u7528\u591a\u4e45\u5b66\u5b8c\uff0c\u6bcf\u5929\u6216\u6bcf\u5468\u80fd\u6295\u5165\u591a\u5c11\u65f6\u95f4\uff1f"

DEFAULT_UPDATE_QUESTIONS = [
    "\u4f60\u60f3\u8c03\u6574\u8ba1\u5212\u7684\u54ea\u4e9b\u90e8\u5206\uff1f\u76ee\u6807/\u65f6\u95f4/\u5f3a\u5ea6/\u4e3b\u9898\u90fd\u53ef\u4ee5\u8bf4\u8bf4\u3002",
    "\u65b0\u7684\u5468\u671f\u548c\u6bcf\u5929\u6295\u5165\u65f6\u95f4\u662f\u591a\u5c11\uff1f",
    "\u8fd8\u6709\u5176\u4ed6\u8c03\u6574\u5417\uff1f",
]


def _normalize_topics(focus_topics: Optional[List[str]]) -> List[str]:
    topics = [t.strip() for t in (focus_topics or []) if t and t.strip()]
    if topics:
        return topics
    return [
        "\u57fa\u7840\u6982\u5ff5",
        "\u6838\u5fc3\u539f\u7406",
        "\u65b9\u6cd5\u4e0e\u6280\u5de7",
        "\u5b9e\u8df5\u5e94\u7528",
        "\u590d\u76d8\u4f18\u5316",
    ]


def _build_milestones(
    start_date: datetime.date, total_days: int, task_title: str
) -> List[Dict[str, str]]:
    if total_days <= 0:
        total_days = 7
    checkpoints = [max(1, total_days // 3), max(2, (2 * total_days) // 3), total_days]
    labels = [
        "\u8d77\u6b65\uff1a\u660e\u786e\u8303\u56f4\u3001\u8d44\u6599\u4e0e\u57fa\u7840\u8ba4\u77e5",
        "\u4e2d\u6bb5\uff1a\u5b8c\u6210\u6838\u5fc3\u7ec3\u4e60\u5e76\u9a8c\u8bc1\u7406\u89e3",
        "\u6536\u5c3e\uff1a\u4ea7\u51fa\u5c0f\u9879\u76ee\u5e76\u603b\u7ed3\u8981\u70b9",
    ]
    milestones: List[Dict[str, str]] = []
    for offset, label in zip(checkpoints, labels):
        date = start_date + datetime.timedelta(days=offset - 1)
        milestones.append(
            {
                "date": date.isoformat(),
                "achievement": f"{task_title}: {label}",
            }
        )
    return milestones


def _coerce_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value)
    match = re.search(r"(\d+)", text)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value)
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _coerce_str_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    parts = re.split(r"[,\u3001;|\n]+", text)
    return [p.strip() for p in parts if p.strip()]


def _parse_date(value: Any) -> Optional[datetime.date]:
    if not value:
        return None
    if isinstance(value, datetime.date):
        return value
    text = str(value).strip()
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        return None


def _normalize_mastery_level(value: Any, topics: List[str]) -> List[Dict[str, Any]]:
    if isinstance(value, list) and value:
        normalized = []
        for item in value:
            if isinstance(item, dict):
                topic = str(item.get("topic") or "").strip()
                level = _coerce_int(item.get("level")) or 15
                if topic:
                    normalized.append({"topic": topic, "level": level})
        if normalized:
            return normalized
    return [{"topic": topic, "level": 15} for topic in topics]


def _normalize_milestones(value: Any) -> List[Dict[str, str]]:
    if isinstance(value, list) and value:
        normalized: List[Dict[str, str]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            date = str(item.get("date") or "").strip()
            achievement = str(item.get("achievement") or "").strip()
            if date and achievement:
                normalized.append({"date": date, "achievement": achievement})
        if normalized:
            return normalized
    return []


def _normalize_plan(
    plan: Dict[str, Any],
    task_id: str,
    existing_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    base = dict(existing_plan or {})
    base.update(plan or {})
    base["task_id"] = task_id
    base.setdefault("taskIcon", "*")

    start_date = _parse_date(base.get("startDate")) or datetime.date.today()
    base["startDate"] = start_date.isoformat()

    total_days = _coerce_int(base.get("totalDays")) or _coerce_int(base.get("targetDays"))
    if total_days is None:
        total_days = _coerce_int(existing_plan.get("totalDays")) if existing_plan else None
    if not total_days or total_days <= 0:
        total_days = 7
    base["totalDays"] = total_days

    total_hours = _coerce_float(base.get("totalHours"))
    if total_hours is None:
        daily_hours = _coerce_float(base.get("dailyHours") or base.get("daily_hours"))
        if daily_hours is None and existing_plan:
            daily_hours = _coerce_float(existing_plan.get("dailyHours") or existing_plan.get("daily_hours"))
        if daily_hours is None:
            daily_hours = 1.0
        total_hours = round(daily_hours * total_days, 1)
    base["totalHours"] = total_hours

    progress = _coerce_int(base.get("progress"))
    if progress is None and existing_plan:
        progress = _coerce_int(existing_plan.get("progress"))
    if progress is None:
        progress = 0
    base["progress"] = max(0, min(progress, 100))

    task_title = str(base.get("taskTitle") or "").strip()
    if not task_title:
        task_title = str(existing_plan.get("taskTitle") if existing_plan else "").strip()
    if not task_title:
        task_title = f"Task Plan {task_id}"
    base["taskTitle"] = task_title

    overall_summary = str(base.get("overallSummary") or "").strip()
    if not overall_summary:
        level_hint = "\u5f53\u524d\u6c34\u5e73\uff1a\u672a\u8bf4\u660e\u3002"
        constraint_hint = "\u7ea6\u675f\u6761\u4ef6\uff1a\u7075\u6d3b\u3002"
        overall_summary = f"{task_title}. {level_hint} {constraint_hint}"
    base["overallSummary"] = overall_summary

    core_knowledge = _coerce_str_list(base.get("coreKnowledge"))
    if not core_knowledge:
        core_knowledge = _normalize_topics(base.get("focusTopics"))
    base["coreKnowledge"] = core_knowledge

    base["masteryLevel"] = _normalize_mastery_level(base.get("masteryLevel"), core_knowledge)

    milestones = _normalize_milestones(base.get("milestones"))
    if not milestones:
        milestones = _build_milestones(start_date, total_days, task_title)
    base["milestones"] = milestones

    plan_steps = _coerce_str_list(base.get("plan") or base.get("nextSteps"))
    if not plan_steps:
        plan_steps = [
            "\u660e\u786e\u5b66\u4e60\u76ee\u6807\u548c\u6210\u529f\u6807\u51c6\uff0c\u7ed1\u5b9a\u53ef\u9a8c\u6536\u7684\u4ea7\u51fa",
            "\u4f7f\u7528\u4e00\u5929\u65f6\u95f4\u8fc7\u4e00\u904d\u5165\u95e8\u5185\u5bb9\uff0c\u8865\u9f50\u57fa\u7840\u6982\u5ff5",
            "\u4e3b\u9898\u5206\u5757\u7ec3\u4e60\uff0c\u6bcf\u5929\u4e00\u4e2a\u4f8b\u5b50\u8fdb\u884c\u4ea4\u4e92\u9a8c\u8bc1",
            "\u6574\u7406\u7b14\u8bb0\u4e0e\u95ee\u9898\u6e05\u5355\uff0c\u6bcf\u5468\u4e00\u6b21\u590d\u76d8\u4fee\u6b63",
            "\u4e2d\u671f\u8fdb\u884c\u5c0f\u9879\u76ee\u6f14\u7ec3\uff0c\u7ed9\u51fa\u7ed3\u679c\u548c\u6539\u8fdb\u70b9",
            "\u672b\u671f\u5b8c\u6210\u4e00\u4e2a\u7ed3\u9898\u5c0f\u9879\u76ee\uff0c\u603b\u7ed3\u65b9\u6cd5\u4e0e\u6a21\u677f",
            "\u6839\u636e\u53cd\u9988\u66f4\u65b0\u540e\u7eed\u8ba1\u5212\uff0c\u540c\u6b65\u62cc\u751f\u5b66\u4e60\u76ee\u6807",
        ]
    base["plan"] = plan_steps

    base.pop("nextSteps", None)
    base.pop("targetDays", None)
    base.pop("focusTopics", None)
    base.pop("dailyHours", None)
    base.pop("daily_hours", None)
    return base


def plan_signature(plan: Dict[str, Any]) -> str:
    payload = {
        "taskTitle": plan.get("taskTitle"),
        "totalDays": plan.get("totalDays"),
        "totalHours": plan.get("totalHours"),
        "overallSummary": plan.get("overallSummary"),
        "coreKnowledge": plan.get("coreKnowledge"),
        "masteryLevel": plan.get("masteryLevel"),
        "milestones": plan.get("milestones"),
        "plan": plan.get("plan"),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _extract_json_block(text: str) -> Optional[str]:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        return match.group(0) if match else None
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    return match.group(0) if match else None


def _parse_plan_response(text: str) -> Optional[Dict[str, Any]]:
    json_block = _extract_json_block(text)
    if not json_block:
        return None
    try:
        data = json.loads(json_block)
    except Exception:
        return None
    if isinstance(data, dict) and "plan" in data and isinstance(data["plan"], dict):
        return data["plan"]
    return data if isinstance(data, dict) else None


def _split_steps_from_text(text: str) -> List[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    steps: List[str] = []
    for line in lines:
        stripped = re.sub(r"^\s*[-*•]\s*", "", line)
        stripped = re.sub(r"^\s*\d+[\.\)\-、]\s*", "", stripped)
        if stripped:
            steps.append(stripped)
    if steps:
        return steps
    return [cleaned]


def _build_system_prompt(existing_plan: Optional[Dict[str, Any]]) -> str:
    if not existing_plan:
        return TASK_PLAN_SYSTEM_PROMPT
    existing = json.dumps(existing_plan, ensure_ascii=False, sort_keys=True)
    return TASK_PLAN_SYSTEM_PROMPT + "\n\nCurrent plan JSON:\n" + existing


def _get_plan_model() -> ChatDeepSeek:
    return ChatDeepSeek(
        model=config.settings.MODEL_NAME,
        api_key=config.settings.DEEPSEEK_API_KEY,
        temperature=0.2,
    )


def _get_chat_model():
    # Reuse the main chat model from agent_builder to keep behavior aligned.
    from app.core import agent_builder

    return agent_builder.model


def _normalize_plan_session(plan_session: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base = dict(plan_session or {})
    base.setdefault("status", "idle")  # idle | await_offer | await_confirm | collecting | await_plan_confirm
    base.setdefault("mode", "")
    base.setdefault("turns", 0)
    base.setdefault("max_turns", 0)
    base.setdefault("messages", [])
    base.setdefault("pending_mode", "")
    base.setdefault("draft_plan", None)
    return base


def _contains_keywords(text: str, keywords: List[str]) -> bool:
    return any(k in text for k in keywords)


def _is_yes(text: str) -> bool:
    if not text:
        return False
    text = text.strip()
    if any(k in text for k in NO_KEYWORDS):
        return False
    return any(k in text for k in YES_KEYWORDS)


def _is_no(text: str) -> bool:
    if not text:
        return False
    text = text.strip()
    if any(k in text for k in NO_KEYWORDS):
        return True
    if any(k in text for k in YES_KEYWORDS):
        return False
    return False


def _is_update_intent(text: str) -> bool:
    if not text:
        return False
    return _contains_keywords(text, PLAN_INTENT_KEYWORDS)


def _is_learn_intent(text: str) -> bool:
    if not text:
        return False
    return _contains_keywords(text, LEARN_INTENT_KEYWORDS)


def _detect_plan_intent(text: str, has_plan: bool) -> str:
    if _is_update_intent(text):
        return "update" if has_plan else "init"
    if _is_learn_intent(text):
        return "learn"
    return "none"


def _build_plan_dialogue_text(plan_session: Dict[str, Any]) -> str:
    parts: List[str] = []
    for item in plan_session.get("messages", []):
        role = item.get("role")
        content = item.get("content") or ""
        if not content:
            continue
        tag = "User" if role == "user" else "Assistant"
        parts.append(f"{tag}: {content}")
    return "\n".join(parts)

def _has_time_signal(text: str) -> bool:
    hints = _extract_plan_hints(text)
    if hints.get("target_days") or hints.get("daily_hours"):
        return True
    return _contains_keywords(text, TIME_KEYWORDS)


def _has_depth_or_goal(text: str) -> bool:
    if _contains_keywords(text, DEPTH_KEYWORDS):
        return True
    if "\u76ee\u6807" in text or "\u6253\u7b97" in text or "\u60f3" in text:
        return True
    return False


def _has_update_points(text: str) -> bool:
    return (
        _contains_keywords(text, TIME_KEYWORDS)
        or _contains_keywords(text, CONTENT_KEYWORDS)
        or _contains_keywords(text, DEPTH_KEYWORDS)
        or _contains_keywords(text, INTENSITY_KEYWORDS)
    )


def _has_enough_info(text: str, mode: str) -> bool:
    hints = _extract_plan_hints(text)
    goal = (hints.get("user_goal") or "").strip()
    has_time = _has_time_signal(text)
    has_goal = bool(goal) or _has_depth_or_goal(text) or _contains_keywords(text, CONTENT_KEYWORDS)
    if mode == "update":
        return _has_update_points(text)
    return has_goal and has_time


def _next_default_question(mode: str, turns: int) -> str:
    if mode == "update":
        idx = min(turns, len(DEFAULT_UPDATE_QUESTIONS) - 1)
        return DEFAULT_UPDATE_QUESTIONS[idx]
    idx = min(turns, len(DEFAULT_INIT_QUESTIONS) - 1)
    return DEFAULT_INIT_QUESTIONS[idx]

def _pick_init_first_question(user_message: str) -> str:
    text = (user_message or "").strip()
    if not text:
        return _next_default_question("init", 0)
    if _has_time_signal(text):
        return _next_default_question("init", 2)
    if _is_learn_intent(text) or _contains_keywords(text, CONTENT_KEYWORDS):
        return DEFAULT_TIME_QUESTION
    return _next_default_question("init", 0)


async def _generate_followup_question(
    mode: str,
    turns: int,
    plan_session: Dict[str, Any],
    has_plan: bool,
    existing_plan: Optional[Dict[str, Any]] = None,
    require_time: bool = False,
) -> str:
    if require_time:
        return DEFAULT_TIME_QUESTION
    try:
        model = _get_chat_model()
        base_plan = existing_plan or {}
        if isinstance(plan_session.get("draft_plan"), dict):
            base_plan = plan_session.get("draft_plan") or base_plan

        summary = json.dumps(base_plan, ensure_ascii=False, sort_keys=True) if base_plan else ""
        dialogue = _build_plan_dialogue_text(plan_session)
        sys_prompt = (
            "\u4f60\u662f\u5b66\u4e60\u8ba1\u5212\u52a9\u624b\uff0c\u9700\u8981\u7528\u6700\u7b80\u6d01\u7684\u4e00\u4e2a\u95ee\u9898\u7ee7\u7eed\u6536\u96c6\u8ba1\u5212\u4fe1\u606f\u3002"
            "\u53ea\u8bf7\u4e00\u4e2a\u95ee\u9898\uff0c\u4e0d\u8981\u5217\u8868\uff0c\u4e0d\u8981\u591a\u4e2a\u95ee\u53f7\uff0c\u4e2d\u6587\u56de\u7b54\u3002"
            "\u5982\u679c\u5f53\u524d\u6a21\u5f0f\u662f init\uff0c\u8bf7\u5148\u7528 1-2 \u53e5\u7b80\u5355\u7684\u5165\u95e8\u89e3\u91ca\u5e2e\u52a9\u7528\u6237\u5bf9\u4e3b\u9898\u6709\u521d\u6b65\u4e86\u89e3\uff0c\u7136\u540e\u63d0\u4e00\u4e2a\u95ee\u9898\u3002"
            "\u5982\u679c\u5f53\u524d\u6a21\u5f0f\u662f update\uff0c\u76f4\u63a5\u63d0\u95ee\u3002"
            f"\n\u5f53\u524d\u6a21\u5f0f: {mode}."
            f"\n\u662f\u5426\u5df2\u6709\u8ba1\u5212: {str(has_plan)}."
        )
        user_prompt = f"\u5f53\u524d\u5bf9\u8bdd:\n{dialogue}\n\n\u539f\u8ba1\u5212:\n{summary}"
        response = await model.ainvoke(
            [
                HumanMessage(content=sys_prompt),
                HumanMessage(content=user_prompt),
            ]
        )
        content = getattr(response, "content", "") or ""
        content = content.strip()
        if content:
            return content
    except Exception:
        pass
    return _next_default_question(mode, turns)


async def handle_plan_chat(
    task_id: str,
    user_message: str,
    existing_plan: Optional[Dict[str, Any]],
    plan_session: Optional[Dict[str, Any]],
    has_plan: bool,
    conversation_summary: str = "",
    history_messages: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    session = _normalize_plan_session(plan_session)
    status = session.get("status", "idle")
    mode = session.get("mode", "")

    # Awaiting user response to a soft plan offer
    if status == "await_offer":
        if _is_yes(user_message):
            mode = "update" if has_plan else "init"
            session.update(
                {
                    "status": "collecting",
                    "mode": mode,
                    "turns": 0,
                    "max_turns": 5 if mode == "init" else 3,
                    "messages": [],
                }
            )
            if mode == "init":
                question = _pick_init_first_question(user_message)
            else:
                question = await _generate_followup_question(mode, 0, session, has_plan, existing_plan)
            session["messages"].append({"role": "assistant", "content": question})
            return {
                "handled": True,
                "reply": question,
                "plan_proposal": None,
                "plan_session": session,
            }
        if _is_no(user_message):
            session.update({"status": "idle", "mode": "", "turns": 0, "pending_mode": "", "messages": []})
            return {
                "handled": True,
                "reply": "\u597d\u7684\uff0c\u5982\u679c\u9700\u8981\u5b66\u4e60\u8ba1\u5212\uff0c\u968f\u65f6\u544a\u8bc9\u6211\u3002",
                "plan_proposal": None,
                "plan_session": session,
            }
        return {
            "handled": True,
            "reply": "\u5982\u679c\u4f60\u9700\u8981\u5b66\u4e60\u8ba1\u5212\uff0c\u56de\u590d\u201c\u9700\u8981\u201d\u5c31\u53ef\u4ee5\u5f00\u59cb\u3002",
            "plan_proposal": None,
            "plan_session": session,
        }

    # Awaiting plan confirmation prompt
    if status == "await_confirm":
        pending_mode = session.get("pending_mode") or ("update" if has_plan else "init")
        if _is_yes(user_message):
            mode = pending_mode
            session.update(
                {
                    "status": "collecting",
                    "mode": mode,
                    "turns": 0,
                    "max_turns": 5 if mode == "init" else 3,
                    "pending_mode": "",
                    "messages": [],
                }
            )
            question = await _generate_followup_question(mode, 0, session, has_plan, existing_plan)
            session["messages"].append({"role": "assistant", "content": question})
            return {
                "handled": True,
                "reply": question,
                "plan_proposal": None,
                "plan_session": session,
            }
        if _is_no(user_message):
            session.update({"status": "idle", "mode": "", "turns": 0, "pending_mode": "", "messages": []})
            return {
                "handled": True,
                "reply": "\u597d\u7684\uff0c\u5982\u679c\u9700\u8981\u5b66\u4e60\u8ba1\u5212\uff0c\u968f\u65f6\u544a\u8bc9\u6211\u3002",
                "plan_proposal": None,
                "plan_session": session,
            }
        return {
            "handled": True,
            "reply": "\u4f60\u662f\u5426\u9700\u8981\u6211\u4e3a\u4f60\u751f\u6210/\u8c03\u6574\u5b66\u4e60\u8ba1\u5212\uff1f\u56de\u590d\u201c\u9700\u8981\u201d\u6216\u201c\u4e0d\u9700\u8981\u201d\u5373\u53ef\u3002",
            "plan_proposal": None,
            "plan_session": session,
        }

    # Awaiting user confirmation after plan proposal
    if status == "await_plan_confirm":
        # If user提出新诉求，回到更新流程
        if _is_update_intent(user_message) or _is_learn_intent(user_message):
            session.update(
                {
                    "status": "collecting",
                    "mode": "update",
                    "turns": 0,
                    "max_turns": 3,
                    "messages": [],
                }
            )
            session["messages"].append({"role": "user", "content": user_message})
            question = await _generate_followup_question("update", 0, session, True, existing_plan)
            session["messages"].append({"role": "assistant", "content": question})
            return {
                "handled": True,
                "reply": question,
                "plan_proposal": None,
                "plan_session": session,
            }
        return {
            "handled": True,
            "reply": "\u5982\u679c\u4f60\u9700\u8981\u8c03\u6574\u8ba1\u5212\uff0c\u76f4\u63a5\u544a\u8bc9\u6211\u60f3\u6539\u54ea\u4e9b\u5185\u5bb9\u3002",
            "plan_proposal": None,
            "plan_session": session,
        }

    # Active collection flow
    if status == "collecting":
        session["messages"].append({"role": "user", "content": user_message})
        session["turns"] = int(session.get("turns", 0)) + 1
        mode = session.get("mode") or "init"
        session["mode"] = mode
        if session.get("max_turns", 0) <= 0:
            session["max_turns"] = 5 if mode == "init" else 3

        dialogue_text = _build_plan_dialogue_text(session)
        should_generate = _has_enough_info(dialogue_text, mode) or session["turns"] >= session["max_turns"]

        if should_generate:
            base_plan = existing_plan or {}
            if isinstance(session.get("draft_plan"), dict):
                base_plan = session.get("draft_plan") or base_plan

            plan_query = ""
            messages_for_plan = list(history_messages or [])
            if user_message:
                messages_for_plan.append(HumanMessage(content=user_message))
            plan_state = {
                "messages": messages_for_plan,
                "conversation_summary": conversation_summary or "",
                "task_id": task_id,
                "session_id": "",
            }
            plan = await asyncio.to_thread(
                generate_task_plan_from_state,
                plan_state,
                plan_query,
                base_plan,
                _get_chat_model(),
            )
            session.update(
                {
                    "status": "await_plan_confirm",
                    "draft_plan": plan,
                }
            )
            reply = (
                "\u6211\u5df2\u4e3a\u4f60\u751f\u6210\u4e86\u65b0\u7684\u5b66\u4e60\u8ba1\u5212\uff0c\u8bf7\u8fdb\u884c\u786e\u8ba4\u3002"
                "\u5982\u679c\u9700\u8981\u8c03\u6574\uff0c\u76f4\u63a5\u544a\u8bc9\u6211\u60f3\u6539\u54ea\u91cc\u3002"
            )
            return {
                "handled": True,
                "reply": reply,
                "plan_proposal": plan,
                "plan_session": session,
            }

        time_missing = mode == "init" and not _has_time_signal(dialogue_text)
        require_time = time_missing and session["turns"] >= (session["max_turns"] - 1)
        question = await _generate_followup_question(
            mode,
            session["turns"],
            session,
            has_plan,
            existing_plan,
            require_time=require_time,
        )
        session["messages"].append({"role": "assistant", "content": question})
        return {
            "handled": True,
            "reply": question,
            "plan_proposal": None,
            "plan_session": session,
        }

    # Idle: detect intent
    intent = _detect_plan_intent(user_message, has_plan)
    if intent == "learn":
        mode = "update" if has_plan else "init"
        session.update(
            {
                "status": "collecting",
                "mode": mode,
                "turns": 0,
                "max_turns": 5 if mode == "init" else 3,
                "messages": [],
            }
        )
        if mode == "init":
            question = _pick_init_first_question(user_message)
        else:
            question = await _generate_followup_question(mode, 0, session, has_plan, existing_plan)
        session["messages"].append({"role": "assistant", "content": question})
        return {
            "handled": True,
            "reply": question,
            "plan_proposal": None,
            "plan_session": session,
        }
    if intent in {"init", "update"}:
        mode = intent
        session.update(
            {
                "status": "collecting",
                "mode": mode,
                "turns": 0,
                "max_turns": 5 if mode == "init" else 3,
                "messages": [],
            }
        )
        question = await _generate_followup_question(mode, 0, session, has_plan, existing_plan)
        session["messages"].append({"role": "assistant", "content": question})
        return {
            "handled": True,
            "reply": question,
            "plan_proposal": None,
            "plan_session": session,
        }

    return {"handled": False}


def generate_task_plan(
    task_id: str,
    user_goal: str = "",
    current_level: str = "",
    constraints: str = "",
    target_days: Optional[int] = None,
    daily_hours: Optional[float] = None,
    focus_topics: Optional[List[str]] = None,
) -> Dict[str, Any]:
    today = datetime.date.today()
    total_days = int(target_days) if target_days else 7
    total_hours = round((daily_hours or 1.0) * total_days, 1)

    task_title = user_goal.strip() if user_goal else f"Task Plan {task_id}"
    level_hint = (
        f"\u5f53\u524d\u6c34\u5e73\uff1a{current_level}\u3002"
        if current_level
        else "\u5f53\u524d\u6c34\u5e73\uff1a\u672a\u8bf4\u660e\u3002"
    )
    constraint_hint = (
        f"\u7ea6\u675f\u6761\u4ef6\uff1a{constraints}\u3002"
        if constraints
        else "\u7ea6\u675f\u6761\u4ef6\uff1a\u7075\u6d3b\u3002"
    )

    topics = _normalize_topics(focus_topics)
    mastery_level = [{"topic": topic, "level": 15} for topic in topics]

    plan = {
        "task_id": task_id,
        "taskTitle": task_title,
        "taskIcon": "*",
        "startDate": today.isoformat(),
        "totalDays": total_days,
        "totalHours": total_hours,
        "progress": 0,
        "overallSummary": f"{task_title}. {level_hint} {constraint_hint}",
        "coreKnowledge": topics,
        "masteryLevel": mastery_level,
        "milestones": _build_milestones(today, total_days, task_title),
        "plan": [
            "\u660e\u786e\u5b66\u4e60\u76ee\u6807\u548c\u6210\u529f\u6807\u51c6\uff0c\u7ed1\u5b9a\u53ef\u9a8c\u6536\u7684\u4ea7\u51fa",
            "\u4f7f\u7528\u4e00\u5929\u65f6\u95f4\u8fc7\u4e00\u904d\u5165\u95e8\u5185\u5bb9\uff0c\u8865\u9f50\u57fa\u7840\u6982\u5ff5",
            "\u4e3b\u9898\u5206\u5757\u7ec3\u4e60\uff0c\u6bcf\u5929\u4e00\u4e2a\u4f8b\u5b50\u8fdb\u884c\u4ea4\u4e92\u9a8c\u8bc1",
            "\u6574\u7406\u7b14\u8bb0\u4e0e\u95ee\u9898\u6e05\u5355\uff0c\u6bcf\u5468\u4e00\u6b21\u590d\u76d8\u4fee\u6b63",
            "\u4e2d\u671f\u8fdb\u884c\u5c0f\u9879\u76ee\u6f14\u7ec3\uff0c\u7ed9\u51fa\u7ed3\u679c\u548c\u6539\u8fdb\u70b9",
            "\u672b\u671f\u5b8c\u6210\u4e00\u4e2a\u7ed3\u9898\u5c0f\u9879\u76ee\uff0c\u603b\u7ed3\u65b9\u6cd5\u4e0e\u6a21\u677f",
            "\u6839\u636e\u53cd\u9988\u66f4\u65b0\u540e\u7eed\u8ba1\u5212\uff0c\u540c\u6b65\u62cc\u751f\u5b66\u4e60\u76ee\u6807",
        ],
    }
    plan["_plan_sig"] = plan_signature(plan)
    return plan


def _extract_plan_hints(text: str) -> Dict[str, Any]:
    cleaned = " ".join(text.strip().split())
    target_days = None
    daily_hours = None

    match_days = re.search(r"(\\d+)\\s*\\u5929", cleaned)
    if match_days:
        target_days = int(match_days.group(1))

    match_weeks = re.search(r"(\\d+)\\s*\\u5468", cleaned)
    if match_weeks and target_days is None:
        target_days = int(match_weeks.group(1)) * 7

    match_months = re.search(r"(\\d+)\\s*\\u6708", cleaned)
    if match_months and target_days is None:
        target_days = int(match_months.group(1)) * 30

    match_hours = re.search(r"(\\d+(?:\\.\\d+)?)\\s*(?:\\u5c0f\\u65f6|h)", cleaned)
    if match_hours:
        daily_hours = float(match_hours.group(1))

    user_goal = cleaned[:120] if cleaned else ""

    return {
        "user_goal": user_goal,
        "target_days": target_days,
        "daily_hours": daily_hours,
    }


def generate_task_plan_from_dialogue(task_id: str, dialogue: str) -> Dict[str, Any]:
    hints = _extract_plan_hints(dialogue)
    return generate_task_plan(
        task_id=task_id,
        user_goal=hints.get("user_goal", ""),
        target_days=hints.get("target_days"),
        daily_hours=hints.get("daily_hours"),
        constraints="Auto-generated from conversation",
    )


def generate_task_plan_from_state(
    state: Dict[str, Any],
    plan_query: Optional[str] = None,
    existing_plan: Optional[Dict[str, Any]] = None,
    model_override: Optional[Any] = None,
) -> Dict[str, Any]:
    task_id = str(state.get("task_id") or "task_default")
    messages = list(state.get("messages") or [])

    query = (plan_query or "").strip()
    if query:
        messages.append(HumanMessage(content=query))

    plan_state = {
        "messages": messages,
        "conversation_summary": state.get("conversation_summary") or "",
        "task_id": task_id,
        "session_id": state.get("session_id") or "",
    }

    system_prompt = _build_system_prompt(existing_plan)
    llm_messages = context.build_context(plan_state, system_prompt)

    try:
        model = model_override or _get_plan_model()
        response = model.invoke(llm_messages)
        content = getattr(response, "content", "") or ""
        plan = _parse_plan_response(content)
        if plan:
            normalized = _normalize_plan(plan, task_id, existing_plan)
            normalized["_plan_sig"] = plan_signature(normalized)
            return normalized
        if content:
            steps = _split_steps_from_text(content)
            if steps:
                fallback_plan = {"plan": steps}
                normalized = _normalize_plan(fallback_plan, task_id, existing_plan)
                normalized["_plan_sig"] = plan_signature(normalized)
                return normalized
    except Exception:
        pass

    fallback_text = query or ""
    fallback_plan = generate_task_plan_from_dialogue(task_id, fallback_text)
    normalized = _normalize_plan(fallback_plan, task_id, existing_plan)
    normalized["_plan_sig"] = plan_signature(normalized)
    return normalized

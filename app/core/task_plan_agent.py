import datetime
import json
import hashlib
import re
from typing import Any, Dict, List, Optional

from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage

from app.core import config
from app.core import context_rag as context


TASK_PLAN_SYSTEM_PROMPT = """You are a study plan assistant.
Your task is to generate or update a TaskPlan based on the conversation.

Rules:
1) Always output a single JSON object. No markdown, no extra text.
2) All user-facing text MUST be in Simplified Chinese.
3) If an existing plan is provided, treat it as the current plan and only update what the user asked to change.
4) If the user asks for a new plan, create a complete plan.
5) If information is missing, infer reasonable defaults.
6) The field "nextSteps" MUST be the full, detailed study plan (chronological, actionable). Do not truncate.
7) The plan should cover the whole study period and be specific enough to execute.

Required JSON schema:
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
  "nextSteps": ["string"]
}
"""


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

    next_steps = _coerce_str_list(base.get("nextSteps"))
    if not next_steps:
        next_steps = [
            "\u660e\u786e\u5b66\u4e60\u76ee\u6807\u548c\u6210\u529f\u6807\u51c6\uff0c\u7ed1\u5b9a\u53ef\u9a8c\u6536\u7684\u4ea7\u51fa",
            "\u4f7f\u7528\u4e00\u5929\u65f6\u95f4\u8fc7\u4e00\u904d\u5165\u95e8\u5185\u5bb9\uff0c\u8865\u9f50\u57fa\u7840\u6982\u5ff5",
            "\u4e3b\u9898\u5206\u5757\u7ec3\u4e60\uff0c\u6bcf\u5929\u4e00\u4e2a\u4f8b\u5b50\u8fdb\u884c\u4ea4\u4e92\u9a8c\u8bc1",
            "\u6574\u7406\u7b14\u8bb0\u4e0e\u95ee\u9898\u6e05\u5355\uff0c\u6bcf\u5468\u4e00\u6b21\u590d\u76d8\u4fee\u6b63",
            "\u4e2d\u671f\u8fdb\u884c\u5c0f\u9879\u76ee\u6f14\u7ec3\uff0c\u7ed9\u51fa\u7ed3\u679c\u548c\u6539\u8fdb\u70b9",
            "\u672b\u671f\u5b8c\u6210\u4e00\u4e2a\u7ed3\u9898\u5c0f\u9879\u76ee\uff0c\u603b\u7ed3\u65b9\u6cd5\u4e0e\u6a21\u677f",
            "\u6839\u636e\u53cd\u9988\u66f4\u65b0\u540e\u7eed\u8ba1\u5212\uff0c\u540c\u6b65\u62cc\u751f\u5b66\u4e60\u76ee\u6807",
        ]
    base["nextSteps"] = next_steps

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
        "nextSteps": plan.get("nextSteps"),
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
        "nextSteps": [
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
        model = _get_plan_model()
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
                fallback_plan = {"nextSteps": steps}
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

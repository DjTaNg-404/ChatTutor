"""
Task Plan Agent - Utilities
"""
import datetime
import re
from typing import Any, Dict, List, Optional


def _normalize_topics(focus_topics: Optional[List[str]]) -> List[str]:
    topics = [t.strip() for t in (focus_topics or []) if t and t.strip()]
    if topics:
        return topics
    return [
        "基础概念",
        "核心原理",
        "方法与技巧",
        "实践应用",
        "复盘优化",
    ]


def _build_milestones(
    start_date: datetime.date, total_days: int, task_title: str
) -> List[Dict[str, str]]:
    if total_days <= 0:
        total_days = 7
    checkpoints = [max(1, total_days // 3), max(2, (2 * total_days) // 3), total_days]
    labels = [
        "起步：明确范围、资料与基础认知",
        "中段：完成核心练习并验证理解",
        "收尾：产出小项目并总结要点",
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


def _extract_plan_hints(text: str) -> Dict[str, Any]:
    """从用户文本中提取计划相关提示信息"""
    import re
    cleaned = " ".join(text.strip().split())
    target_days = None
    daily_hours = None

    match_days = re.search(r"(\d+)\s*天", cleaned)
    if match_days:
        target_days = int(match_days.group(1))

    match_weeks = re.search(r"(\d+)\s*周", cleaned)
    if match_weeks and target_days is None:
        target_days = int(match_weeks.group(1)) * 7

    match_months = re.search(r"(\d+)\s*月", cleaned)
    if match_months and target_days is None:
        target_days = int(match_months.group(1)) * 30

    match_hours = re.search(r"(\d+(?:\.\d+)?)\s*(?:小时|h)", cleaned)
    if match_hours:
        daily_hours = float(match_hours.group(1))

    user_goal = cleaned[:120] if cleaned else ""

    return {
        "user_goal": user_goal,
        "target_days": target_days,
        "daily_hours": daily_hours,
    }


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
        level_hint = "当前水平：未说明。"
        constraint_hint = "约束条件：灵活。"
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
            "明确学习目标和成功标准，绑定可验收的产出",
            "使用一天时间过一遍入门内容，补齐基础概念",
            "主题分块练习，每天一个例子进行交互验证",
            "整理笔记与问题清单，每周一次复盘修正",
            "中期进行小项目演练，给出结果和改进点",
            "末期完成一个结题小项目，总结方法与模板",
            "根据反馈更新后续计划，同步伴生学习目标",
        ]
    base["plan"] = plan_steps

    base.pop("nextSteps", None)
    base.pop("targetDays", None)
    base.pop("focusTopics", None)
    base.pop("dailyHours", None)
    base.pop("daily_hours", None)
    return base

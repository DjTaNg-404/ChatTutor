"""
Task Plan Agent - Generator
"""
import datetime
import asyncio
import json
import hashlib
from typing import Any, Dict, List, Optional

from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage

from app.core import config
from app.core import context_rag as context
from app.core.task_plan.prompts import TASK_PLAN_SYSTEM_PROMPT
from app.core.task_plan.utils import (
    _normalize_plan,
    _normalize_topics,
    _build_milestones,
    _extract_plan_hints,
)
from app.core.task_plan.parser import (
    _parse_plan_response,
    _split_steps_from_text,
)


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
    from app.core import agent_builder
    return agent_builder.model


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
        f"当前水平：{current_level}。"
        if current_level
        else "当前水平：未说明。"
    )
    constraint_hint = (
        f"约束条件：{constraints}。"
        if constraints
        else "约束条件：灵活。"
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
            "明确学习目标和成功标准，绑定可验收的产出",
            "使用一天时间过一遍入门内容，补齐基础概念",
            "主题分块练习，每天一个例子进行交互验证",
            "整理笔记与问题清单，每周一次复盘修正",
            "中期进行小项目演练，给出结果和改进点",
            "末期完成一个结题小项目，总结方法与模板",
            "根据反馈更新后续计划，同步伴生学习目标",
        ],
    }
    plan["_plan_sig"] = plan_signature(plan)
    return plan


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

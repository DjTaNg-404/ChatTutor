from typing import Dict, Any, Literal, Optional
import hashlib
import asyncio

from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from rich import print as rprint

from langchain_core.messages import ToolMessage

from app.core.config import settings
from app.core.models import AgentState, ExecutionPlan
from app.core import prompts, memory
from app.core import context_rag as context  # RAG enhanced context module
from app.core.cache import generation_cache, retrieval_cache
from app.core import learning_profile
from app.core import profile_store
from app.core.tools_v2 import search_tool_v2
from app.core.task_plan import (
    PLAN_SESSION_KEY,
    handle_plan_chat,
)
from pydantic import BaseModel

# --- 1. Model Initialization ---
# 通用模型：用于文本生成 (Tutor, Judge, Inquiry, Aggregator)
model = ChatDeepSeek(
    model=settings.MODEL_NAME,
    api_key=settings.DEEPSEEK_API_KEY,
    temperature=0.7
)

# 绑定了工具的模型 (ReAct Worker)
# DeepSeek 原生支持工具调用，我们把 Search 绑定给它
model_with_tools = model.bind_tools([search_tool_v2])

# 分析模型：用于结构化输出规划 (Analyzer)
# 通常我们可以用稍微低一点的 temperature 保证 JSON 格式稳定
analyzer_model_raw = ChatDeepSeek(
    model=settings.MODEL_NAME, # 或者使用更便宜/快速的模型
    api_key=settings.DEEPSEEK_API_KEY,
    temperature=0.1
)

PERSIST_MESSAGES_LIMIT = 0  # 0 = 不裁剪，保留全量历史
WORKER_TIMEOUT_SECONDS = 30

# --- Cache & Profile Helpers ---

def _history_sig(state: AgentState) -> str:
    """生成最近消息的 MD5 签名，用于缓存 key 的一部分。"""
    msgs = state.get("messages", [])
    recent = msgs[-8:]
    parts = [str(getattr(m, "content", "")) for m in recent if getattr(m, "content", "")]
    summary = state.get("conversation_summary") or ""
    seed = "||".join(parts) + "||" + summary
    return hashlib.md5(seed.encode("utf-8")).hexdigest()


def _gen_cache_key(state: AgentState, node_name: str, prompt_str: str) -> str:
    return generation_cache.make_key(
        session_id=state.get("session_id", ""),
        node=node_name,
        prompt=prompt_str,
        history_sig=_history_sig(state),
    )


def _ensure_cache_trace(state: AgentState) -> dict:
    trace = state.setdefault("_cache_trace", {})
    trace.setdefault("generation_cache_hit", {})
    trace.setdefault("retrieval_cache_hit", False)
    return trace


def _mark_gen_cache(state: AgentState, node_name: str, hit: bool):
    _ensure_cache_trace(state)["generation_cache_hit"][node_name] = bool(hit)


def _mark_retrieval_cache(state: AgentState, hit: bool):
    trace = _ensure_cache_trace(state)
    trace["retrieval_cache_hit"] = trace["retrieval_cache_hit"] or bool(hit)


def _get_user_id(state: AgentState) -> str:
    return state.get("user_id") or "local_user"


def _inject_profile(prompt_str: str, state: AgentState) -> str:
    """将用户学习画像摘要注入 Prompt 末尾。"""
    user_id = _get_user_id(state)
    profile = profile_store.load_profile(user_id)
    summary = learning_profile.profile_summary(profile)
    if not summary:
        return prompt_str
    return prompt_str + "\n\n[Learning Profile]\n" + summary


_CACHE_INVALIDATE_KEYWORDS: list = []  # 可按需添加触发缓存失效的关键词


def _should_invalidate_cache(messages) -> bool:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            text = m.content or ""
            return any(k in text for k in _CACHE_INVALIDATE_KEYWORDS)
    return False


# --- 2. Node Functions (节点逻辑) ---

class PlanExitDecision(BaseModel):
    exit_plan: bool = False

class PlanRouteDecision(BaseModel):
    plan_related: bool = False


async def _should_exit_plan_dialog_llm(
    user_message: str,
    plan_session: Optional[Dict[str, Any]],
    has_plan: bool,
) -> bool:
    if not user_message:
        return False
    # Only exit plan dialog when user explicitly opts out.
    normalized = user_message.strip()
    return normalized == "暂不调整计划"


async def _is_plan_related_llm(
    user_message: str,
    plan_session: Optional[Dict[str, Any]],
    has_plan: bool,
) -> bool:
    if not user_message:
        return False
    try:
        router = analyzer_model_raw.with_structured_output(PlanRouteDecision)
        status = ""
        last_question = ""
        if isinstance(plan_session, dict):
            status = str(plan_session.get("status") or "")
            for item in reversed(plan_session.get("messages", []) or []):
                if item.get("role") == "assistant":
                    last_question = item.get("content") or ""
                    if last_question:
                        break
        sys_prompt = (
            "你是对话路由器。用户当前处于学习计划规划流程中。"
            "判断用户这句话是否与学习计划的制定/修改/确认/继续相关。"
            "若是计划相关（回答计划问题、补充约束、提出修改、继续调整、确认计划），返回 plan_related=true。"
            "若是普通知识问答或与计划无关的问题，返回 plan_related=false。"
            "仅输出JSON：{\"plan_related\": true/false}。"
        )
        user_prompt = (
            f"PlanStatus: {status}\n"
            f"HasPlan: {has_plan}\n"
            f"LastPlanQuestion: {last_question}\n"
            f"UserMessage: {user_message}"
        )
        result: PlanRouteDecision = await router.ainvoke(
            [SystemMessage(content=sys_prompt), HumanMessage(content=user_prompt)]
        )
        return bool(getattr(result, "plan_related", False))
    except Exception:
        return False

async def analyzer_node(state: AgentState) -> Dict[str, Any]:
    """
    大脑节点：分析用户意图并制定执行计划 (ExecutionPlan)。
    同时负责清理上一轮的临时输出。
    """
    messages = state["messages"]
    if not messages:
        return {}

    _ensure_cache_trace(state)
    recent_context = messages[-3:]
    last_user_msg = ""
    for msg in reversed(recent_context):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content or ""
            break

    # 构造 Prompt（注入用户学习画像）
    sys_msg_content = _inject_profile(prompts.ANALYZER_SYSTEM_PROMPT, state)

    # 注入当前计划状态，帮助 Analyzer 准确判断
    from app.core import memory as memory_io
    task_id = state.get("task_id", "task_default")
    has_existing_plan = False
    plan_should_pause = False
    plan_force_request = False
    try:
        existing_plan = memory_io.get_task_plan_data(task_id)
        draft_plan = existing_plan.get("draft_plan") if isinstance(existing_plan, dict) else None
        # ?? has_task_plan ?????????????????? await_offer ???
        has_existing_plan = memory_io.has_task_plan(task_id) or isinstance(draft_plan, dict)
        plan_session = existing_plan.get(PLAN_SESSION_KEY) if existing_plan else None
        status = ""
        if isinstance(plan_session, dict):
            status = str(plan_session.get("status") or "")
            # 兼容旧状态 offer_shown
            if status == "offer_shown":
                plan_session["status"] = "await_offer"
                status = "await_offer"
                updated_plan = dict(existing_plan or {})
                updated_plan[PLAN_SESSION_KEY] = plan_session
                try:
                    memory_io.save_task_plan(task_id, updated_plan)
                except Exception:
                    pass

        if plan_session and status in {"await_confirm", "await_plan_confirm", "collecting"}:
            exit_plan_dialog = await _should_exit_plan_dialog_llm(
                user_message=last_user_msg,
                plan_session=plan_session,
                has_plan=has_existing_plan,
            )
            if exit_plan_dialog:
                updated_plan = dict(existing_plan or {})
                updated_plan[PLAN_SESSION_KEY] = {
                    "status": "idle",
                    "mode": "",
                    "turns": 0,
                    "pending_mode": "",
                    "messages": [],
                }
                try:
                    memory_io.save_task_plan(task_id, updated_plan)
                except Exception:
                    pass
                plan_session = None
        if plan_session and status == "await_offer":
            # 软引导阶段：下一轮交由 plan 节点处理（若用户未响应，将放行普通对话）
            plan_force_request = True
        elif plan_session and status in {"await_confirm", "await_plan_confirm", "collecting", "paused"}:
            if status == "paused":
                # 挂起后的恢复仅由前端按钮控制
                plan_should_pause = True
            else:
                is_plan_related = await _is_plan_related_llm(
                    user_message=last_user_msg,
                    plan_session=plan_session,
                    has_plan=has_existing_plan,
                )
                if not is_plan_related:
                    plan_session["paused_from"] = status
                    plan_session["status"] = "paused"
                    updated_plan = dict(existing_plan or {})
                    updated_plan[PLAN_SESSION_KEY] = plan_session
                    try:
                        memory_io.save_task_plan(task_id, updated_plan)
                    except Exception:
                        pass
                    plan_should_pause = True
    except Exception:
        pass

    sys_msg = SystemMessage(content=sys_msg_content)

    # 绑定结构化输出
    planner = analyzer_model_raw.with_structured_output(ExecutionPlan)

    try:
        # Analyzer 也应该看到上下文摘要，否则它可能听不懂关于旧话题的回答
        # 不过为了简单准确，把 Summary 放在 System Prompt 之后比较好
        inputs = [sys_msg]
        if state.get("conversation_summary"):
             inputs.append(SystemMessage(content=f"Context: {state.get('conversation_summary')}"))

        inputs.extend(recent_context)

        plan: ExecutionPlan = await planner.ainvoke(inputs)
    except Exception as e:
        # Fallback 策略：如果解析失败，默认当作普通提问
        print(f"Analyzer Error: {e}")
        plan = ExecutionPlan(
            needs_tutor_answer=True,
            needs_judge=False,
            needs_inquiry=False,
            request_summary=False,
            request_plan=False,
            is_concluding=False,
            thought_process="Error in planning, defaulting to simple answer."
        )

    # 如果计划已挂起，本轮走普通答疑
    if plan_force_request:
        plan.request_plan = True
    if plan_should_pause:
        plan.request_plan = False
        plan.needs_tutor_answer = True
        plan.needs_judge = False
        plan.needs_inquiry = False

    # 返回计划，并重置临时字段，防止污染
    # 如果计划中包含结束意图，设置 should_exit 信号
    return {
        "plan": plan,
        "should_exit": plan.is_concluding,
        "tutor_output": None,
        "judge_output": None,
        "inquiry_output": None,
        "summary_output": None
    }

async def _run_tool_loop(prompt_content, state):
    """
    具体的 ReAct 循环逻辑：
    1. 调用模型 (带工具)
    2. 如果有 tool_calls -> 执行工具 -> 将结果追加到临时消息 -> 再次调用模型
    3. 如果没有 -> 直接返回结果
    """
    
    # 使用 context.build_context 构造包含 Summary + Recent Window 的消息列表
    # 注意：build_context 返回的是 [System, Summary?, RecentMessages...]
    # prompt_content 这里是 system prompt 正文
    current_messages = context.build_context(state, prompt_content)

    # 第一次调用：让模型思考是否需要工具
    # 注意这里使用的是 runnable list，而不是 state["messages"] 全集
    response = await model_with_tools.ainvoke(current_messages)

    # 检查是否有工具调用请求
    if response.tool_calls:
        # 执行所有请求的工具
        for tool_call in response.tool_calls:
            # 这里简单起见只处理 search_tool，未来可能有更多
            if tool_call["name"] == "baidu_search":
                args = tool_call['args']
                query_str = args.get('query', str(args))
                try:
                    key = retrieval_cache.make_key(query_str)
                    hit = retrieval_cache.get(key) is not None
                except Exception:
                    hit = False
                _mark_retrieval_cache(state, hit)
                rprint(f"[dim italic]   🔍 Searching Baidu for: [cyan]{query_str}[/cyan] ...[/dim italic]")
                
                tool_result = await search_tool_v2.ainvoke(tool_call["args"])
                
                # 构造 ToolMessage 反馈给模型
                tool_msg = ToolMessage(
                    tool_call_id=tool_call["id"],
                    content=str(tool_result),
                    name=tool_call["name"]
                )
                current_messages.append(response) # 把带有 tool_call 的 AIMessage 也加上
                current_messages.append(tool_msg) # 把 ToolMessage 加上
        
        # 第二次调用：基于工具结果生成回答
        # 注意：这里我们只要最终结果，不再绑定工具，防止它死循环一直搜
        final_response = await model.ainvoke(current_messages)
        return final_response.content
    else:
        # 没用工具，直接返回
        return response.content

async def tutor_node(state: AgentState) -> Dict[str, Any]:
    """
    Worker A: 答疑者。支持联网搜索。
    """
    topic = state.get("current_topic", "General Knowledge")
    prompt_str = _inject_profile(prompts.TUTOR_WORKER_PROMPT.format(topic=topic), state)

    cache_key = _gen_cache_key(state, "tutor", prompt_str)
    cached = generation_cache.get(cache_key)
    if cached is not None:
        _mark_gen_cache(state, "tutor", True)
        return {"tutor_output": cached}

    _mark_gen_cache(state, "tutor", False)
    content = await _run_tool_loop(prompt_str, state)
    generation_cache.set(cache_key, content, session_id=state.get("session_id"))
    return {"tutor_output": content}

async def judge_node(state: AgentState) -> Dict[str, Any]:
    """
    Worker B: 评审员。支持联网搜索。
    """
    topic = state.get("current_topic", "General Knowledge")
    prompt_str = _inject_profile(prompts.JUDGE_WORKER_PROMPT.format(topic=topic), state)

    cache_key = _gen_cache_key(state, "judge", prompt_str)
    cached = generation_cache.get(cache_key)
    if cached is not None:
        _mark_gen_cache(state, "judge", True)
        return {"judge_output": cached}

    _mark_gen_cache(state, "judge", False)
    content = await _run_tool_loop(prompt_str, state)
    generation_cache.set(cache_key, content, session_id=state.get("session_id"))
    return {"judge_output": content}

async def inquiry_node(state: AgentState) -> Dict[str, Any]:
    """
    Worker C: 探究者。提出启发式问题。
    """
    topic = state.get("current_topic", "General Knowledge")
    judge_fb = state.get("judge_output") or "无"
    
    # 直接在 Prompt 中注入 Feedback，简单明了
    sys_msg_str = _inject_profile(prompts.INQUIRY_WORKER_PROMPT.format(topic=topic, judge_feedback=judge_fb), state)

    cache_key = _gen_cache_key(state, "inquiry", sys_msg_str)
    cached = generation_cache.get(cache_key)
    if cached is not None:
        _mark_gen_cache(state, "inquiry", True)
        return {"inquiry_output": cached}

    _mark_gen_cache(state, "inquiry", False)
    # 先构建标准上下文 [System, Summary, Recent]
    inputs = context.build_context(state, sys_msg_str)
    response = await model.ainvoke(inputs)
    generation_cache.set(cache_key, response.content, session_id=state.get("session_id"))
    return {"inquiry_output": response.content}


def _make_local_worker_state(state: AgentState) -> AgentState:
    local_state = state.copy()
    base_trace = state.get("_cache_trace") or {}
    local_state["_cache_trace"] = {
        "generation_cache_hit": dict(base_trace.get("generation_cache_hit", {})),
        "retrieval_cache_hit": bool(base_trace.get("retrieval_cache_hit", False)),
    }
    return local_state


def _merge_trace(state: AgentState, worker_trace: dict):
    if not worker_trace:
        return
    merged = _ensure_cache_trace(state)
    merged["retrieval_cache_hit"] = bool(merged.get("retrieval_cache_hit")) or bool(worker_trace.get("retrieval_cache_hit"))
    worker_gen = worker_trace.get("generation_cache_hit", {})
    if isinstance(worker_gen, dict):
        merged["generation_cache_hit"].update(worker_gen)


async def _run_worker_safe(worker_name: str, worker_coro, state: AgentState) -> Dict[str, Any]:
    try:
        result = await asyncio.wait_for(worker_coro, timeout=WORKER_TIMEOUT_SECONDS)
        return result if isinstance(result, dict) else {}
    except Exception as e:
        print(f"⚠️ Worker {worker_name} failed: {e}")
        return {}


async def parallel_workers_node(state: AgentState) -> Dict[str, Any]:
    plan = state.get("plan")
    if not plan:
        return {}

    updates: Dict[str, Any] = {}

    tutor_task = None
    judge_task = None
    tutor_state = None
    judge_state = None

    if plan.needs_tutor_answer:
        tutor_state = _make_local_worker_state(state)
        tutor_task = asyncio.create_task(_run_worker_safe("tutor", tutor_node(tutor_state), state))

    if plan.needs_judge:
        judge_state = _make_local_worker_state(state)
        judge_task = asyncio.create_task(_run_worker_safe("judge", judge_node(judge_state), state))

    if tutor_task or judge_task:
        results = await asyncio.gather(
            *(task for task in [tutor_task, judge_task] if task is not None),
            return_exceptions=True,
        )

        idx = 0
        if tutor_task is not None:
            tutor_res = results[idx]
            idx += 1
            if isinstance(tutor_res, dict):
                updates.update(tutor_res)
            if tutor_state is not None:
                _merge_trace(state, tutor_state.get("_cache_trace", {}))

        if judge_task is not None:
            judge_res = results[idx]
            if isinstance(judge_res, dict):
                updates.update(judge_res)
            if judge_state is not None:
                _merge_trace(state, judge_state.get("_cache_trace", {}))

    if plan.needs_inquiry:
        inquiry_state = _make_local_worker_state(state)
        if updates.get("judge_output"):
            inquiry_state["judge_output"] = updates.get("judge_output")
        inquiry_res = await _run_worker_safe("inquiry", inquiry_node(inquiry_state), state)
        if isinstance(inquiry_res, dict):
            updates.update(inquiry_res)
        _merge_trace(state, inquiry_state.get("_cache_trace", {}))

    return updates


async def plan_node(state: AgentState) -> Dict[str, Any]:
    """
    Plan flow node: reuse Task Plan dialog manager.
    """
    task_id = state.get("task_id", "task_default")
    session_id = state.get("session_id", "")
    user_message = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            user_message = msg.content or ""
            break

    try:
        plan_data = memory.get_task_plan_data(task_id)
    except Exception:
        plan_data = None

    draft_plan = None
    if isinstance(plan_data, dict):
        draft_plan = plan_data.get("draft_plan")
    existing_plan = draft_plan if isinstance(draft_plan, dict) else plan_data
    plan_session = plan_data.get(PLAN_SESSION_KEY) if plan_data else None
    has_plan = memory.has_task_plan(task_id) or isinstance(draft_plan, dict)

    session_state = memory.load_session(session_id) or {}
    history_messages = state.get("messages") or session_state.get("messages", [])
    conversation_summary = state.get("conversation_summary") or session_state.get("conversation_summary") or ""
    if plan_session and plan_session.get("status") in {"await_confirm", "await_plan_confirm", "collecting"}:
        # Use plan-session dialogue only to avoid mixing normal QA context.
        history_messages = []
        for item in plan_session.get("context_messages", []) or []:
            role = item.get("role")
            content = item.get("content") or ""
            if not content:
                continue
            if role == "user":
                history_messages.append(HumanMessage(content=content))
            else:
                history_messages.append(AIMessage(content=content))
        for item in plan_session.get("messages", []) or []:
            role = item.get("role")
            content = item.get("content") or ""
            if not content:
                continue
            if role == "user":
                history_messages.append(HumanMessage(content=content))
            else:
                history_messages.append(AIMessage(content=content))
        conversation_summary = ""

    if plan_session and plan_session.get("status") in {"await_confirm", "await_plan_confirm", "collecting"}:
        exit_plan_dialog = await _should_exit_plan_dialog_llm(
            user_message=user_message,
            plan_session=plan_session,
            has_plan=has_plan,
        )
        if exit_plan_dialog:
            updated_plan = plan_data or {}
            updated_plan[PLAN_SESSION_KEY] = {
                "status": "idle",
                "mode": "",
                "turns": 0,
                "pending_mode": "",
                "messages": [],
            }
            try:
                memory.save_task_plan(task_id, updated_plan)
            except Exception:
                pass
            plan = state.get("plan")
            if plan and getattr(plan, "request_plan", False):
                plan.request_plan = False
            if plan and not any(
                [
                    plan.needs_tutor_answer,
                    plan.needs_judge,
                    plan.needs_inquiry,
                    plan.request_summary,
                ]
            ):
                plan.needs_tutor_answer = True
            return {
                "plan": plan,
                "plan_handled": False,
            }

    seed_user_message = None
    if not plan_session or plan_session.get("status") == "idle":
        last_user = None
        prior_user = None
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, HumanMessage):
                if last_user is None:
                    last_user = (msg.content or "").strip()
                else:
                    prior_user = (msg.content or "").strip()
                    break
        if prior_user and len(prior_user) >= 4:
            seed_user_message = prior_user

    result = await handle_plan_chat(
        task_id=task_id,
        user_message=user_message,
        existing_plan=existing_plan,
        plan_session=plan_session,
        has_plan=has_plan,
        conversation_summary=conversation_summary,
        history_messages=history_messages,
        seed_user_message=seed_user_message,
    )
    if result.get("plan_session"):
        updated_plan = plan_data or {}
        updated_plan[PLAN_SESSION_KEY] = result["plan_session"]
        try:
            memory.save_task_plan(task_id, updated_plan)
        except Exception:
            pass
    if not result.get("handled"):
        plan = state.get("plan")
        if plan and getattr(plan, "request_plan", False):
            plan.request_plan = False
        return {
            "plan": plan,
            "plan_handled": False,
        }

    if result.get("plan_proposal"):
        try:
            memory.save_task_plan(task_id, {"draft_plan": result["plan_proposal"]})
        except Exception:
            pass

    reply = result.get("reply") or "请告诉我你的学习计划需求，比如目标和时间安排。"
    suggested_replies = result.get("suggested_replies")
    if result.get("plan_session"):
        session = result["plan_session"]
        if session.get("status") in {"collecting", "await_plan_confirm"} and not session.get("reminded"):
            reply = "你正在调整学习计划（可随时问普通问题，稍后继续）。\n\n" + reply
            session["reminded"] = True
            result["plan_session"] = session
    ai_reply = AIMessage(content=reply)
    current_messages = state.get("messages", []) + [ai_reply]
    temp_state = state.copy()
    temp_state["messages"] = current_messages
    new_summary, new_cursor = context.manage_memory(temp_state)
    temp_state["conversation_summary"] = new_summary
    temp_state["summarized_msg_count"] = new_cursor
    memory.save_session(temp_state)
    return {
        "messages": [ai_reply],
        "plan_proposal": result.get("plan_proposal"),
        "plan_handled": True,
        "suggested_replies": suggested_replies,
        "conversation_summary": temp_state.get("conversation_summary"),
        "summarized_msg_count": temp_state.get("summarized_msg_count"),
    }

async def aggregator_node(state: AgentState) -> Dict[str, Any]:
    """
    汇总者。将所有 Worker 的输出融合成最终回复。
    """
    tutor_out = state.get("tutor_output") or ""
    judge_out = state.get("judge_output") or ""
    inquiry_out = state.get("inquiry_output") or ""
    summary_out = state.get("summary_output") or ""
    plan_out = state.get("plan_output") or ""

    final_response = None


    # 检查是否需要即时总结（用户在对话中要求总结）
    plan = state.get("plan")
    if plan and plan.request_summary and not state.get("should_exit"):
        # 调用总结生成器生成即时回顾总结
        from app.core.summary.generator import summary_generator

        # 从状态中提取对话历史
        messages = state.get("messages", [])
        conversation_history = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                conversation_history.append({"role": "user", "content": msg.content or ""})
            elif isinstance(msg, AIMessage):
                conversation_history.append({"role": "assistant", "content": msg.content or ""})

        topic = state.get("current_topic", "General")
        summary_text = await asyncio.to_thread(
            summary_generator.generate_review_summary,
            conversation_history=conversation_history,
            topic=topic
        )
        summary_out = summary_text

    # 检查是否需要生成学习计划（用户在对话中要求制定计划）
    # 场景: Ending or Normal
    if state.get("should_exit"):
        # 如果处于 Concluding 状态，生成离场学习笔记
        if not summary_out:  # 如果还没有生成总结
            from app.core.summary.generator import summary_generator

            # 从状态中提取对话历史
            messages = state.get("messages", [])
            conversation_history = []
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    conversation_history.append({"role": "user", "content": msg.content or ""})
                elif isinstance(msg, AIMessage):
                    conversation_history.append({"role": "assistant", "content": msg.content or ""})

            topic = state.get("current_topic", "General")
            summary_text = await asyncio.to_thread(
                summary_generator.generate_session_note,
                conversation_history=conversation_history,
                topic=topic
            )
            summary_out = summary_text
        
        final_response = AIMessage(content=summary_out)
    elif not any([tutor_out, judge_out, inquiry_out, summary_out, plan_out]):
        # 闲聊/低信息量场景：走专用闲聊 Prompt，生成自然回复
        inputs = context.build_context(state, prompts.CHITCHAT_SYSTEM_PROMPT)
        final_response = await model.ainvoke(inputs)
    else:
        # 构造 Prompt
        prompt = prompts.AGGREGATOR_SYSTEM_PROMPT.format(
            tutor_output=tutor_out,
            judge_output=judge_out,
            inquiry_output=inquiry_out,
            summary_output=summary_out
        )

        # 如果有计划输出，追加到 prompt
        if plan_out:
            prompt += f"\n\n[学习计划通知]: {plan_out}"

        # 汇总者目前不需要太长的历史，只看各个模块的输出即可。
        # 传入 System Prompt 即可。
        # 为了语气连贯，传入最近一条用户消息也是好的。
        inputs = [SystemMessage(content=prompt)]
        if state["messages"]:
            inputs.append(state["messages"][-1])

        final_response = await model.ainvoke(inputs)

    
    # --- Plan pause reminder (soft resume) ---
    try:
        if isinstance(final_response, AIMessage) and not state.get("should_exit"):
            task_id = state.get("task_id", "task_default")
            plan_data = memory.get_task_plan_data(task_id)
            plan_session = plan_data.get(PLAN_SESSION_KEY) if isinstance(plan_data, dict) else None
            if plan_session and plan_session.get("status") in {"await_confirm", "await_plan_confirm", "collecting", "paused"}:
                if not (plan and getattr(plan, "request_plan", False)):
                    status = plan_session.get("status")
                    suffix = "当前处于计划调整中，继续提问即可；如需退出可回复“暂不调整计划”。"
                    if status == "paused":
                        suffix = "计划已挂起，可在界面上继续调整或结束计划。"
                    final_response.content = (
                        (final_response.content or "").rstrip()
                        + f"\n\n{suffix}"
                    )
    except Exception:
        pass

# ---------------- 存档与压缩逻辑 (Auto-Save & Compress) ----------------
    # 模拟“状态更新之后”的效果：我们需要把最新的 AI 回复合并进去才能存到完整的记录
    
    current_messages = state["messages"] + [final_response]
    
    # 1. 创建即时快照 (用于计算 Memory)
    temp_state = state.copy()
    temp_state["messages"] = current_messages
    
    # 2. 执行内存压缩 (Maintenance)
    # 检查是否需要压缩旧消息
    new_summary, new_cursor = context.manage_memory(temp_state)
    
    # 3. 更新要保存的状态
    state_to_save = temp_state.copy()
    if new_summary != state.get("conversation_summary"):
        # 发生了压缩，更新状态
        state_to_save["conversation_summary"] = new_summary
        state_to_save["summarized_msg_count"] = new_cursor
        
        # (Optional) Print debug info
        print(f"🧠 Memory Compressed! New summary length: {len(new_summary)}, Cursor: {new_cursor}")
    
    # 4. 附加 cache trace 到 AIMessage
    trace = state.get("_cache_trace", {})
    try:
        if isinstance(final_response, AIMessage):
            if final_response.additional_kwargs is None:
                final_response.additional_kwargs = {}
            final_response.additional_kwargs["cache_trace"] = trace
    except Exception:
        pass

    # 5. 更新学习画像
    try:
        user_id = _get_user_id(state)
        user_text = ""
        for m in reversed(state.get("messages", [])):
            if isinstance(m, HumanMessage):
                user_text = m.content or ""
                break
        assistant_text = final_response.content if isinstance(final_response, AIMessage) else ""
        cards = learning_profile.extract_learning_facts(
            user_text=user_text,
            assistant_text=assistant_text,
            source=user_id
        )
        if cards:
            profile = profile_store.load_profile(user_id)
            profile = learning_profile.upsert_cards(profile, cards)
            profile_store.save_profile(profile)
    except Exception:
        pass

    # 6. 缓存失效检查
    if _should_invalidate_cache(state.get("messages", [])):
        generation_cache.clear_session(state.get("session_id", ""))

    # 7. 执行物理存档
    memory.save_session(state_to_save)

    # 返回给 Graph 的更新 (包括 messages 和 可能更新的 summary/cursor)
    result = {
        "messages": [final_response],
        "conversation_summary": state_to_save["conversation_summary"],
        "summarized_msg_count": state_to_save["summarized_msg_count"],
        "_cache_trace": {},
    }
    # 如果处理了计划请求或总结请求，清除 plan 标志，让下一轮重新意图识别
    if plan and (plan.request_plan or plan.request_summary):
        result["plan"] = None
    return result


# --- 3. Edge Logic (条件路由) ---

def route_from_analyzer(state: AgentState) -> Literal["plan", "parallel_workers", "aggregator"]:
    plan = state.get("plan")
    if not plan: # Should not happen
        return "aggregator"

    if plan.request_plan:
        return "plan"
    # 如果用户要求即时总结，直接路由到 aggregator 处理
    if plan.request_summary:
        return "aggregator"

    if any([plan.needs_tutor_answer, plan.needs_judge, plan.needs_inquiry]):
        return "parallel_workers"
    else:
        return "aggregator"


def route_from_plan(state: AgentState) -> Literal["end", "parallel_workers", "aggregator"]:
    if state.get("plan_handled"):
        return "end"

    plan = state.get("plan")
    if not plan:
        return "aggregator"
    if plan.request_summary:
        return "aggregator"
    if any([plan.needs_tutor_answer, plan.needs_judge, plan.needs_inquiry]):
        return "parallel_workers"
    return "aggregator"
        
# --- 4. Graph Construction ---

def build_agent():
    builder = StateGraph(AgentState)
    
    # Nodes
    builder.add_node("analyzer", analyzer_node)
    builder.add_node("tutor", tutor_node)
    builder.add_node("judge", judge_node)
    builder.add_node("inquiry", inquiry_node)
    builder.add_node("parallel_workers", parallel_workers_node)
    builder.add_node("plan", plan_node)
    builder.add_node("aggregator", aggregator_node)
    
    # Start -> Analyzer
    builder.add_edge(START, "analyzer")
    
    # Analyzer -> ? (Waterfall Flow)
    builder.add_conditional_edges(
        "analyzer",
        route_from_analyzer,
        {
            "plan": "plan",
            "parallel_workers": "parallel_workers",
            "aggregator": "aggregator"
        }
    )

    # Parallel Workers -> Aggregator
    builder.add_edge("parallel_workers", "aggregator")
    
    # Plan -> (Handled End | Fallback Flow)
    builder.add_conditional_edges(
        "plan",
        route_from_plan,
        {
            "end": END,
            "parallel_workers": "parallel_workers",
            "aggregator": "aggregator",
        }
    )
    
    # Aggregator -> End
    builder.add_edge("aggregator", END)
    
    return builder.compile()


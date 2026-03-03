from typing import Dict, Any, Literal
import hashlib

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

def analyzer_node(state: AgentState) -> Dict[str, Any]:
    """
    大脑节点：分析用户意图并制定执行计划 (ExecutionPlan)。
    同时负责清理上一轮的临时输出。
    """
    messages = state["messages"]
    if not messages:
        return {}

    _ensure_cache_trace(state)
    recent_context = messages[-3:]
    
    # 构造 Prompt（注入用户学习画像）
    sys_msg = SystemMessage(content=_inject_profile(prompts.ANALYZER_SYSTEM_PROMPT, state))
    
    # 绑定结构化输出
    planner = analyzer_model_raw.with_structured_output(ExecutionPlan)
    
    try:
        # Analyzer 也应该看到上下文摘要，否则它可能听不懂关于旧话题的回答
        # 不过为了简单准确，把 Summary 放在 System Prompt 之后比较好
        inputs = [sys_msg]
        if state.get("conversation_summary"):
             inputs.append(SystemMessage(content=f"Context: {state.get('conversation_summary')}"))
        
        inputs.extend(recent_context)
        
        plan: ExecutionPlan = planner.invoke(inputs)
    except Exception as e:
        # Fallback 策略：如果解析失败，默认当作普通提问
        print(f"Analyzer Error: {e}")
        plan = ExecutionPlan(
            needs_tutor_answer=True,
            needs_judge=False,
            needs_inquiry=False,
            thought_process="Error in planning, defaulting to simple answer."
        )
    
    # 返回计划，并重置临时字段，防止污染
    return {
        "plan": plan,
        "tutor_output": None,
        "judge_output": None,
        "inquiry_output": None,
        "summary_output": None
    }

def _run_tool_loop(prompt_content, state):
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
    response = model_with_tools.invoke(current_messages)

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
                
                tool_result = search_tool_v2.invoke(tool_call["args"])
                
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
        final_response = model.invoke(current_messages)
        return final_response.content
    else:
        # 没用工具，直接返回
        return response.content

def tutor_node(state: AgentState) -> Dict[str, Any]:
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
    content = _run_tool_loop(prompt_str, state)
    generation_cache.set(cache_key, content, session_id=state.get("session_id"))
    return {"tutor_output": content}

def judge_node(state: AgentState) -> Dict[str, Any]:
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
    content = _run_tool_loop(prompt_str, state)
    generation_cache.set(cache_key, content, session_id=state.get("session_id"))
    return {"judge_output": content}

def inquiry_node(state: AgentState) -> Dict[str, Any]:
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
    response = model.invoke(inputs)
    generation_cache.set(cache_key, response.content, session_id=state.get("session_id"))
    return {"inquiry_output": response.content}

def summary_node(state: AgentState) -> Dict[str, Any]:
    """
    Worker D: 总结者。兼顾 '临时回顾' 和 '离场笔记'。
    """
    plan = state.get("plan")
    
    # 场景1：Ending (离场)
    if plan and plan.is_concluding:
        prompt_str = _inject_profile(prompts.SUMMARIZER_NOTE_PROMPT, state)
        cache_key = _gen_cache_key(state, "summary_note", prompt_str)
        cached = generation_cache.get(cache_key)
        if cached is not None:
            _mark_gen_cache(state, "summary_note", True)
            return {"summary_output": cached, "should_exit": True}

        _mark_gen_cache(state, "summary_note", False)
        inputs = context.build_context(state, prompt_str)
        response = model.invoke(inputs)
        summary_text = response.content
        generation_cache.set(cache_key, summary_text, session_id=state.get("session_id"))
        return {
            "summary_output": summary_text,
            "should_exit": True
        }

    # 场景2：Review (临时回顾)
    elif plan and plan.request_summary:
        prompt_str = _inject_profile(prompts.SUMMARIZER_REVIEW_PROMPT, state)
        cache_key = _gen_cache_key(state, "summary_review", prompt_str)
        cached = generation_cache.get(cache_key)
        if cached is not None:
            _mark_gen_cache(state, "summary_review", True)
            return {"summary_output": cached}

        _mark_gen_cache(state, "summary_review", False)
        inputs = context.build_context(state, prompt_str)
        response = model.invoke(inputs)
        generation_cache.set(cache_key, response.content, session_id=state.get("session_id"))
        return {"summary_output": response.content}

    return {}

def aggregator_node(state: AgentState) -> Dict[str, Any]:
    """
    汇总者。将所有 Worker 的输出融合成最终回复。
    """
    tutor_out = state.get("tutor_output") or ""
    judge_out = state.get("judge_output") or ""
    inquiry_out = state.get("inquiry_output") or ""
    summary_out = state.get("summary_output") or ""
    
    final_response = None

    # 场景: Ending or Normal
    if state.get("should_exit"):
        # 如果处于 Concluding 状态，直接使用 Summary Output
        final_response = AIMessage(content=summary_out)
    elif not any([tutor_out, judge_out, inquiry_out, summary_out]):
        # 闲聊/低信息量场景：走专用闲聊 Prompt，生成自然回复
        inputs = context.build_context(state, prompts.CHITCHAT_SYSTEM_PROMPT)
        final_response = model.invoke(inputs)
    else:
        # 构造 Prompt
        prompt = prompts.AGGREGATOR_SYSTEM_PROMPT.format(
            tutor_output=tutor_out,
            judge_output=judge_out,
            inquiry_output=inquiry_out,
            summary_output=summary_out
        )
        
        # 汇总者目前不需要太长的历史，只看各个模块的输出即可。
        # 传入 System Prompt 即可。
        # 为了语气连贯，传入最近一条用户消息也是好的。
        inputs = [SystemMessage(content=prompt)]
        if state["messages"]:
            inputs.append(state["messages"][-1])
            
        final_response = model.invoke(inputs)

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

    # 8. KG 自动触发：会话结束时在后台构建知识图谱（不阻塞响应）
    if state.get("should_exit"):
        import threading
        _session_id_for_kg = state.get("session_id", "")
        if _session_id_for_kg:
            def _build_kg_background(sid: str):
                try:
                    from app.kg.kg_builder import KnowledgeGraphBuilder
                    import os as _os
                    from app.core import memory as _mem
                    _state = _mem.load_session(sid)
                    if not _state:
                        return
                    msgs = _state.get("messages", [])
                    text = "\n".join(
                        getattr(m, "content", "") for m in msgs
                        if hasattr(m, "content") and getattr(m, "content", "")
                    )
                    if not text.strip():
                        return
                    builder = KnowledgeGraphBuilder(use_advanced_extractor=True)
                    builder.load_models()
                    builder.build_graph(text)
                    _os.makedirs("kg_output", exist_ok=True)
                    builder.visualize_graph(f"kg_output/kg_{sid}.html")
                    builder.export_graph_data(f"kg_output/kg_{sid}.json")
                    print(f"✅ KG built for session {sid}")
                except Exception as _e:
                    print(f"⚠️ KG build failed for session {sid}: {_e}")

            t = threading.Thread(
                target=_build_kg_background,
                args=(_session_id_for_kg,),
                daemon=True,
            )
            t.start()
    # ----------------------------------------------------

    # 返回给 Graph 的更新 (包括 messages 和 可能更新的 summary/cursor)
    return {
        "messages": [final_response],
        "conversation_summary": state_to_save["conversation_summary"], # 可能没变
        "summarized_msg_count": state_to_save["summarized_msg_count"], # 可能没变
        "_cache_trace": {}  # 清零，供下一轮使用
    }


# --- 3. Edge Logic (条件路由) ---

def route_from_analyzer(state: AgentState) -> Literal["tutor", "judge", "inquiry", "summary", "aggregator"]:
    plan = state.get("plan")
    if not plan: # Should not happen
        return "aggregator"
    
    # 特殊处理：如果需要总结或退出，优先路由到 Summary
    if plan.request_summary or plan.is_concluding:
        return "summary"
        
    if plan.needs_tutor_answer:
        return "tutor"
    elif plan.needs_judge:
        return "judge"
    elif plan.needs_inquiry:
        return "inquiry"
    else:
        return "aggregator"

def route_from_tutor(state: AgentState) -> Literal["judge", "inquiry", "aggregator"]:
    plan = state.get("plan")
    if plan.needs_judge:
        return "judge"
    elif plan.needs_inquiry:
        return "inquiry"
    else:
        return "aggregator"

def route_from_judge(state: AgentState) -> Literal["inquiry", "aggregator"]:
    plan = state.get("plan")
    if plan.needs_inquiry:
        return "inquiry"
    else:
        return "aggregator"
        
def route_from_summary(state: AgentState) -> Literal["aggregator"]:
    return "aggregator"

# --- 4. Graph Construction ---

def build_agent():
    builder = StateGraph(AgentState)
    
    # Nodes
    builder.add_node("analyzer", analyzer_node)
    builder.add_node("tutor", tutor_node)
    builder.add_node("judge", judge_node)
    builder.add_node("inquiry", inquiry_node)
    builder.add_node("summary", summary_node)
    builder.add_node("aggregator", aggregator_node)
    
    # Start -> Analyzer
    builder.add_edge(START, "analyzer")
    
    # Analyzer -> ? (Waterfall Flow)
    builder.add_conditional_edges(
        "analyzer",
        route_from_analyzer,
        {
            "tutor": "tutor",
            "judge": "judge",
            "inquiry": "inquiry",
            "summary": "summary",
            "aggregator": "aggregator"
        }
    )
    
    # Tutor -> ?
    builder.add_conditional_edges(
        "tutor",
        route_from_tutor,
        {
            "judge": "judge",
            "inquiry": "inquiry",
            "aggregator": "aggregator"
        }
    )
    
    # Judge -> ?
    builder.add_conditional_edges(
        "judge",
        route_from_judge,
        {
            "inquiry": "inquiry",
            "aggregator": "aggregator"
        }
    )
    
    # Summary -> Aggregator (Always)
    builder.add_edge("summary", "aggregator")
    
    # Inquiry -> Aggregator (Always)
    builder.add_edge("inquiry", "aggregator")
    
    # Aggregator -> End
    builder.add_edge("aggregator", END)
    
    return builder.compile()


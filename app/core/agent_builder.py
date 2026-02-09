from typing import Dict, Any, Literal

from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from rich import print as rprint
from rich.panel import Panel

from langchain_core.messages import ToolMessage

from app.core.config import settings
from app.core.models import AgentState, ExecutionPlan
from app.core import prompts, memory, context
from app.core.tools import search_tool

# --- 1. Model Initialization ---
# 通用模型：用于文本生成 (Tutor, Judge, Inquiry, Aggregator)
model = ChatDeepSeek(
    model=settings.MODEL_NAME,
    api_key=settings.DEEPSEEK_API_KEY,
    temperature=0.7
)

# 绑定了工具的模型 (ReAct Worker)
# DeepSeek 原生支持工具调用，我们把 Search 绑定给它
model_with_tools = model.bind_tools([search_tool])

# 分析模型：用于结构化输出规划 (Analyzer)
# 通常我们可以用稍微低一点的 temperature 保证 JSON 格式稳定
analyzer_model_raw = ChatDeepSeek(
    model=settings.MODEL_NAME, # 或者使用更便宜/快速的模型
    api_key=settings.DEEPSEEK_API_KEY,
    temperature=0.1
)

# --- 2. Node Functions (节点逻辑) ---

def analyzer_node(state: AgentState) -> Dict[str, Any]:
    """
    大脑节点：分析用户意图并制定执行计划 (ExecutionPlan)。
    同时负责清理上一轮的临时输出。
    """
    messages = state["messages"]
    if not messages:
        return {}
    
    recent_context = messages[-3:]
    
    # 构造 Prompt
    sys_msg = SystemMessage(content=prompts.ANALYZER_SYSTEM_PROMPT)
    
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
                # 使用 rich 打印漂亮的搜索状态
                rprint(f"[dim italic]   🔍 Searching Baidu for: [cyan]{query_str}[/cyan] ...[/dim italic]")
                
                tool_result = search_tool.invoke(tool_call["args"])
                
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
    prompt_str = prompts.TUTOR_WORKER_PROMPT.format(topic=topic)
    
    content = _run_tool_loop(prompt_str, state)
    
    return {"tutor_output": content}

def judge_node(state: AgentState) -> Dict[str, Any]:
    """
    Worker B: 评审员。支持联网搜索。
    """
    topic = state.get("current_topic", "General Knowledge")
    prompt_str = prompts.JUDGE_WORKER_PROMPT.format(topic=topic)
    
    content = _run_tool_loop(prompt_str, state)
    
    return {"judge_output": content}

def inquiry_node(state: AgentState) -> Dict[str, Any]:
    """
    Worker C: 探究者。提出启发式问题。
    """
    topic = state.get("current_topic", "General Knowledge")
    judge_fb = state.get("judge_output") or "无"
    
    # 直接在 Prompt 中注入 Feedback，简单明了
    sys_msg_str = prompts.INQUIRY_WORKER_PROMPT.format(topic=topic, judge_feedback=judge_fb)
    
    # 先构建标准上下文 [System, Summary, Recent]
    inputs = context.build_context(state, sys_msg_str)
    
    response = model.invoke(inputs)
    
    return {"inquiry_output": response.content}

def summary_node(state: AgentState) -> Dict[str, Any]:
    """
    Worker D: 总结者。兼顾 '临时回顾' 和 '离场笔记'。
    """
    plan = state.get("plan")
    
    # 场景1：Ending (离场)
    if plan and plan.is_concluding:
        # 1. 强制生成一份学习报告 (Note)
        # 使用专门的结课报告 Prompt
        # 当做总结时，我们应该看尽可能多的历史，所以这里也许不需要太激进的裁剪？
        # 但如果历史太长还是得裁剪。build_context 是安全的。
        inputs = context.build_context(state, prompts.SUMMARIZER_NOTE_PROMPT)
        
        response = model.invoke(inputs)
        summary_text = response.content
        
        # 2. 设置退出标志
        return {
            "summary_output": summary_text, 
            "should_exit": True
        }
        
    # 场景2：Review (临时回顾)
    elif plan and plan.request_summary:
        inputs = context.build_context(state, prompts.SUMMARIZER_REVIEW_PROMPT)
        response = model.invoke(inputs)
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
        # 这里增加一个快速检查：如果所有输出都为空（极端情况），做兜底
        final_response = AIMessage(content="我似乎没听懂你的意思，能再说具体点吗？")
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
        rprint(f"[dim]   🧠 Memory Compressed! New summary length: {len(new_summary)}, Cursor: {new_cursor}[/dim]")
    
    # 4. 执行物理存档
    memory.save_session(state_to_save)
    # ----------------------------------------------------
    
    # 返回给 Graph 的更新 (包括 messages 和 可能更新的 summary/cursor)
    return {
        "messages": [final_response],
        "conversation_summary": state_to_save["conversation_summary"], # 可能没变
        "summarized_msg_count": state_to_save["summarized_msg_count"]  # 可能没变
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


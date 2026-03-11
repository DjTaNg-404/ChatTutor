from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime
import asyncio
import json
import os
import re
from langchain_core.messages import HumanMessage, AIMessage

from app.core.agent_builder import build_agent
from app.core import memory
from app.core.task_plan import (
    PLAN_SESSION_KEY,
    plan_signature,
    generate_task_plan_from_state,
)
from app.core.summary.generator import summary_generator

router = APIRouter()

ENABLE_STREAMING = os.getenv("ENABLE_STREAMING", "true").lower() in {"1", "true", "yes", "on"}
ENABLE_PLAN_PROPOSAL = os.getenv("ENABLE_PLAN_PROPOSAL", "false").lower() in {"1", "true", "yes", "on"}

# Initialize the agent graph once when the module loads
agent_graph = build_agent()

class ChatRequest(BaseModel):
    task_id: Optional[str] = None
    session_id: Optional[str] = None
    message: str
    topic: Optional[str] = "General Knowledge"
    plan_hint: Optional[bool] = None

class ChatResponse(BaseModel):
    task_id: str
    session_id: str
    reply: str
    is_concluded: bool
    plan_proposal: Optional[dict] = None


class StreamEvent(BaseModel):
    event: str
    data: dict


def _normalize_task_id(task_id: Optional[str], session_id: Optional[str]) -> str:
    if task_id and task_id.strip():
        return task_id.strip()
    if session_id and session_id.strip():
        token = session_id.strip().split("__")[0]
        return token if token else "task_default"
    return "task_default"


def _build_session_id(task_id: str, session_id: Optional[str]) -> tuple[str, bool]:
    """
    构建或校验 session_id。

    Returns:
        tuple: (session_id, is_new_session)
            - session_id: 返回会话 ID（可能是新生成的）
            - is_new_session: 是否创建了新会话（用于触发缓存失效）
    """
    now = datetime.now()
    today_date = now.strftime("%Y%m%d")

    if session_id and session_id.strip():
        existing_session = session_id.strip()
        # 解析现有 session_id 中的日期
        parts = existing_session.split("__")
        if len(parts) >= 2:
            session_date = parts[1]  # 格式：YYYYMMDD
            # 如果日期不一致，创建新 session
            if session_date != today_date:
                print(f"📅 检测到跨日对话：原 session 日期 {session_date}，今日日期 {today_date}，创建新 session")
                new_time = now.strftime("%H%M%S")
                return f"{task_id}__{today_date}__{new_time}", True
        # 日期一致或格式不标准，复用原 session
        return existing_session, False

    # 无 session_id，创建新的
    new_time = now.strftime("%H%M%S")
    return f"{task_id}__{today_date}__{new_time}", True


def _collect_recent_user_text(messages, limit: int = 6) -> str:
    chunks = []
    for msg in reversed(messages or []):
        if isinstance(msg, HumanMessage):
            content = msg.content or ""
            if content:
                chunks.append(content.strip())
            if len(chunks) >= limit:
                break
    return " ".join(reversed(chunks)).strip()


def _should_update_plan(text: str) -> bool:
    if not text:
        return False
    # Use unicode escapes to avoid encoding issues in some terminals/editors.
    keywords = [
        "\u8ba1\u5212",  # 计划
        "\u76ee\u6807",  # 目标
        "\u5b89\u6392",  # 安排
        "\u8fdb\u5ea6",  # 进度
        "\u65f6\u95f4",  # 时间
        "\u6bcf\u5929",  # 每天
        "\u6bcf\u5468",  # 每周
        "\u6bcf\u6708",  # 每月
        "\u5b8c\u6210",  # 完成
        "\u8c03\u6574",  # 调整
        "\u6539\u6210",  # 改成
        "\u66f4\u65b0",  # 更新
    ]
    time_patterns = [
        r"\\d+\\s*\\u5929",   # 天
        r"\\d+\\s*\\u5468",   # 周
        r"\\d+\\s*\\u6708",   # 月
        r"\\d+(?:\\.\\d+)?\\s*(?:\\u5c0f\\u65f6|h)",  # 小时/h
    ]
    if any(k in text for k in keywords):
        return True
    return any(re.search(p, text) for p in time_patterns)
    return any(k in text for k in keywords)


def _plan_sig_from_existing(plan_data: dict) -> str:
    return plan_data.get("_plan_sig") or plan_signature(plan_data) if plan_data else ""


async def _build_plan_proposal(
    task_id: str,
    state: dict,
    fallback_text: str = "",
    plan_hint: Optional[bool] = None,
    reply_text: str = "",
) -> Optional[dict]:
    messages = state.get("messages", []) if isinstance(state, dict) else []
    base = fallback_text.strip() if fallback_text else _collect_recent_user_text(messages)
    dialogue = f"{base}\nAI reply: {reply_text}".strip() if reply_text else base
    if not dialogue:
        return None
    should_update = bool(plan_hint) or _should_update_plan(dialogue) or (not memory.has_task_plan(task_id))
    if not should_update:
        return None
    try:
        existing_plan = memory.get_task_plan_data(task_id)
    except Exception:
        existing_plan = None
    plan_state = {
        "messages": messages,
        "conversation_summary": state.get("conversation_summary") if isinstance(state, dict) else "",
        "task_id": task_id,
        "session_id": state.get("session_id") if isinstance(state, dict) else "",
    }
    plan = await asyncio.to_thread(
        generate_task_plan_from_state,
        plan_state,
        dialogue,
        existing_plan,
    )
    return plan


def _build_state(request: ChatRequest, task_id: str, session_id: str):
    current_state = memory.load_session(session_id)
    _defaults = {
        "messages": [],
        "task_id": task_id,
        "current_topic": request.topic,
        "session_id": session_id,
        "user_id": "local_user",
        "conversation_summary": "",
        "summarized_msg_count": 0,
        "plan": None,
        "should_exit": False,
        "tutor_output": None,
        "judge_output": None,
        "inquiry_output": None,
        "summary_output": None,
        "last_intent": None,
    }

    if not current_state:
        current_state = _defaults
    else:
        for key, default_val in _defaults.items():
            current_state.setdefault(key, default_val)
        current_state["task_id"] = task_id
        current_state["session_id"] = session_id
        current_state.setdefault("user_id", "local_user")
        if request.topic:
            current_state["current_topic"] = request.topic

    current_state["messages"].append(HumanMessage(content=request.message))
    return current_state


async def _invoke_agent(current_state):
    try:
        final_state = await agent_graph.ainvoke(current_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")

    messages = final_state.get("messages", [])
    if not messages:
        raise HTTPException(status_code=500, detail="Agent returned no messages")

    last_msg = messages[-1]
    reply_content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
    is_concluded = final_state.get("should_exit", False)

    return final_state, reply_content, is_concluded


def _split_for_stream(text: str):
    parts = [s for s in re.split(r"(?<=[。！？!?\n])", text) if s]
    if not parts:
        return [text]
    return parts


def _chunk_to_text(chunk: Any) -> str:
    if chunk is None:
        return ""
    content = getattr(chunk, "content", chunk)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, str):
                texts.append(item)
            elif isinstance(item, dict):
                text_val = item.get("text")
                if text_val:
                    texts.append(str(text_val))
        return "".join(texts)
    return str(content)


def _is_greeting(text: str) -> bool:
    if not text:
        return True
    trimmed = text.strip()
    greetings = {"\u4f60\u597d", "\u54c8\u55bd", "\u55e8", "\u5728\u5417", "\u65e9\u4e0a\u597d", "\u4e0b\u5348\u597d", "\u665a\u4e0a\u597d"}
    return trimmed in greetings


def _should_offer_plan(text: str, is_new_session: bool, has_plan: bool) -> bool:
    """检查是否应该提供计划建议（仅在新会话且无计划时）"""
    if not is_new_session or has_plan:
        return False
    if _is_greeting(text):
        return False
    return bool(text and text.strip())


def _extract_reply_from_state(final_state: dict) -> str:
    messages = final_state.get("messages", []) if isinstance(final_state, dict) else []
    if not messages:
        return ""
    last_msg = messages[-1]
    if isinstance(last_msg, dict):
        content = last_msg.get("content", "")
        if isinstance(content, list):
            return "".join(str(i.get("text", "")) for i in content if isinstance(i, dict))
        return str(content)
    return str(getattr(last_msg, "content", ""))


def _event_line(event: str, data: dict) -> str:
    return json.dumps(StreamEvent(event=event, data=data).model_dump(), ensure_ascii=False) + "\n"

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    核心对话接口。
    接收用户的输入，加载历史会话状态，调用 Agent，并返回 AI 的回复。
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    task_id = _normalize_task_id(request.task_id, request.session_id)
    session_id, is_new_session = _build_session_id(task_id, request.session_id)

    # 调用主 Agent
    current_state = _build_state(request, task_id, session_id)
    final_state, reply_content, is_concluded = await _invoke_agent(current_state)

    # 检查是否是新会话（用于判断是否提供计划建议）
    is_first_message = len(current_state.get("messages", [])) <= 1
    if _should_offer_plan(request.message, is_first_message, memory.has_task_plan(task_id)):
        reply_content = (
            reply_content.rstrip()
            + '\n\n如果你需要我帮你制定学习计划，直接回复"需要"即可。'
        )
        try:
            memory.save_task_plan(
                task_id=task_id,
                plan={PLAN_SESSION_KEY: {"status": "await_offer"}},
            )
        except Exception:
            pass

    # 如果会话结束，异步调用总结生成器保存总结
    if is_concluded:
        # 检查是否已经在生成总结中（防止重复触发）
        from app.core.memory import is_session_summarizing

        if not is_session_summarizing(session_id):
            # 设置正在总结的标志
            from app.core.memory import set_session_summarizing
            set_session_summarizing(session_id, True)

            # 获取 Agent 生成的总结（如果有的话）
            summary_from_agent = final_state.get("summary_output") or final_state.get("summary_out")
            asyncio.create_task(_call_summary_agent(session_id, task_id, summary_from_agent))
        else:
            print(f"⚠️ 会话 {session_id} 已经在生成总结中，跳过重复请求")

    plan_proposal = None
    if ENABLE_PLAN_PROPOSAL:
        try:
            plan_proposal = await _build_plan_proposal(
                task_id,
                final_state,
                fallback_text=request.message,
                plan_hint=request.plan_hint,
                reply_text=reply_content,
            )
        except Exception as e:
            print(f"[TaskPlan] proposal failed: {e}")

    return ChatResponse(
        task_id=task_id,
        session_id=session_id,
        reply=reply_content,
        is_concluded=is_concluded,
        plan_proposal=plan_proposal,
    )


@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    task_id = _normalize_task_id(request.task_id, request.session_id)
    session_id, is_new_session = _build_session_id(task_id, request.session_id)

    async def _gen():
        try:
            yield _event_line("start", {"task_id": task_id, "session_id": session_id})

            # 发送意图识别开始事件
            yield _event_line("intent", {"status": "analyzing", "text": "正在进行意图识别..."})

            current_state = _build_state(request, task_id, session_id)
            final_state = None
            streamed_any = False

            # 优先使用 LangGraph 事件流（真流式），若上游不支持则自动回退到后处理分片
            async for event in agent_graph.astream_events(current_state, version="v1"):
                event_name = event.get("event", "")
                metadata = event.get("metadata", {}) or {}
                node_name = metadata.get("langgraph_node")

                # 监听意图识别节点（analyzer）
                if node_name == "analyzer" and event_name == "on_chain_end":
                    # 意图识别完成，解析结果
                    output = (event.get("data") or {}).get("output")
                    if isinstance(output, dict) and output.get("plan"):
                        plan = output["plan"]
                        # 处理 Pydantic 模型对象
                        is_pydantic = hasattr(plan, "model_dump")
                        plan_dict = plan.model_dump() if is_pydantic else plan

                        # 构建激活的模块列表
                        modules = []
                        if plan_dict.get("needs_tutor_answer"):
                            modules.append("tutor_answer")
                        if plan_dict.get("needs_judge"):
                            modules.append("judge")
                        if plan_dict.get("needs_inquiry"):
                            modules.append("inquiry")
                        if plan_dict.get("request_summary"):
                            modules.append("summary")
                        if plan_dict.get("request_plan"):
                            modules.append("plan")
                        if plan_dict.get("is_concluding"):
                            modules.append("concluding")

                        # 发送意图识别结果
                        thought = plan_dict.get("thought_process", "")
                        modules_str = " + ".join(modules) if modules else "闲聊"
                        yield _event_line("intent", {
                            "status": "analyzed",
                            "text": f"{thought} → {modules_str}",
                            "modules": modules
                        })

                        # 进入具体模块
                        if modules:
                            yield _event_line("progress", {
                                "status": "processing",
                                "text": f"进入 {modules[0]} 模式..."
                            })

                if event_name == "on_chat_model_stream" and node_name == "aggregator":
                    chunk = (event.get("data") or {}).get("chunk")
                    text_delta = _chunk_to_text(chunk)
                    if text_delta:
                        streamed_any = True
                        yield _event_line("delta", {"text": text_delta})

                if event_name == "on_chain_end" and node_name == "aggregator":
                    output = (event.get("data") or {}).get("output")
                    if isinstance(output, dict):
                        final_state = output

            # 某些运行时不会给到完整 output，这里兜底从持久化会话读取最终状态
            if not isinstance(final_state, dict):
                final_state = await asyncio.to_thread(memory.load_session, session_id) or {}

            reply_content = _extract_reply_from_state(final_state)
            offer_text = ""
            # 检查是否是新会话（用于判断是否提供计划建议）
            is_first_message = len(current_state.get("messages", [])) <= 1
            if _should_offer_plan(request.message, is_first_message, memory.has_task_plan(task_id)):
                offer_text = '\n\n如果你需要我帮你制定学习计划，直接回复"需要"即可。'
                reply_content = reply_content.rstrip() + offer_text
                try:
                    memory.save_task_plan(
                        task_id=task_id,
                        plan={PLAN_SESSION_KEY: {"status": "await_offer"}},
                    )
                except Exception:
                    pass

            # 事件流未产出 token 时，回退到句子分片流
            if not streamed_any and reply_content:
                if ENABLE_STREAMING:
                    for chunk in _split_for_stream(reply_content):
                        yield _event_line("delta", {"text": chunk})
                        await asyncio.sleep(0.02)
                else:
                    yield _event_line("delta", {"text": reply_content})

            if streamed_any and offer_text:
                yield _event_line("delta", {"text": offer_text})

            is_concluded = bool(final_state.get("should_exit", False))

            if is_concluded:
                summary_from_agent = final_state.get("summary_output") or final_state.get("summary_out")
                asyncio.create_task(_call_summary_agent(session_id, task_id, summary_from_agent))

            plan_proposal = None
            if ENABLE_PLAN_PROPOSAL:
                try:
                    plan_proposal = await _build_plan_proposal(
                        task_id,
                        final_state,
                        fallback_text=request.message,
                        plan_hint=request.plan_hint,
                        reply_text=reply_content,
                    )
                except Exception as e:
                    print(f"[TaskPlan] proposal failed: {e}")

            yield _event_line("done", {
                "task_id": task_id,
                "session_id": session_id,
                "is_concluded": is_concluded,
                "plan_proposal": plan_proposal,
            })
        except HTTPException as e:
            yield _event_line("error", {"message": str(e.detail), "status": e.status_code})
        except Exception as e:
            yield _event_line("error", {"message": str(e), "status": 500})

    return StreamingResponse(_gen(), media_type="application/x-ndjson")


async def _call_summary_agent(session_id: str, task_id: str, summary_text: str = None):
    """
    保存会话总结到笔记文件（异步后台任务）

    Args:
        session_id: 会话 ID
        task_id: 任务 ID
        summary_text: 可选的已生成总结文本，如果为 None 则重新生成
    """
    try:
        # 从 memory 加载会话消息
        session_data = await asyncio.to_thread(memory.get_session_messages, session_id)
        if not session_data:
            print(f"⚠️ 会话 {session_id} 不存在")
            return

        # 如果没有传入总结文本，从会话数据生成
        if not summary_text:
            messages = session_data.get("messages", [])
            topic = session_data.get("topic", "General")

            # 生成总结
            summary_text = await asyncio.to_thread(
                summary_generator.generate_session_note,
                conversation_history=messages,
                topic=topic
            )

        # 将总结保存到笔记文件
        if summary_text:
            from app.utils import file_io
            import os

            notes_dir = "memory/notes"
            os.makedirs(notes_dir, exist_ok=True)

            note_filename = f"{session_id}_summary.md"
            note_path = os.path.join(notes_dir, note_filename)

            # 添加元数据头
            header = f"""---
source_session: {session_id}
date: {datetime.now().strftime("%Y-%m-%d")}
topic: {task_id}
---

"""
            await asyncio.to_thread(file_io.save_text, header + summary_text, note_path)
            print(f"✅ 总结已保存：{note_path}")

    except Exception as e:
        print(f"⚠️ 生成总结异常：{e}")
    finally:
        # 清除总结标记（无论成功还是失败）
        from app.core.memory import set_session_summarizing
        set_session_summarizing(session_id, False)

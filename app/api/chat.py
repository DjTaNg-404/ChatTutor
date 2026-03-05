from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import asyncio
import json
import os
import re
from langchain_core.messages import HumanMessage

from app.core.agent_builder import build_agent
from app.core import memory
from app.core.summary.generator import summary_generator

router = APIRouter()

ENABLE_STREAMING = os.getenv("ENABLE_STREAMING", "true").lower() in {"1", "true", "yes", "on"}

# Initialize the agent graph once when the module loads
agent_graph = build_agent()

class ChatRequest(BaseModel):
    task_id: Optional[str] = None
    session_id: Optional[str] = None
    message: str
    topic: Optional[str] = "General Knowledge"

class ChatResponse(BaseModel):
    task_id: str
    session_id: str
    reply: str
    is_concluded: bool


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


def _build_session_id(task_id: str, session_id: Optional[str]) -> str:
    if session_id and session_id.strip():
        return session_id.strip()
    now = datetime.now().strftime("%Y%m%d__%H%M%S")
    return f"{task_id}__{now}"


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
        final_state = await asyncio.to_thread(agent_graph.invoke, current_state)
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
    session_id = _build_session_id(task_id, request.session_id)

    current_state = _build_state(request, task_id, session_id)
    final_state, reply_content, is_concluded = await _invoke_agent(current_state)

    # 7. 如果会话结束，异步调用总结生成器保存总结
    if is_concluded:
        # 获取 Agent 生成的总结（如果有的话）
        summary_from_agent = final_state.get("summary_output") or final_state.get("summary_out")
        asyncio.create_task(_call_summary_agent(session_id, task_id, summary_from_agent))

    return ChatResponse(
        task_id=task_id,
        session_id=session_id,
        reply=reply_content,
        is_concluded=is_concluded
    )


@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    task_id = _normalize_task_id(request.task_id, request.session_id)
    session_id = _build_session_id(task_id, request.session_id)

    async def _gen():
        try:
            yield _event_line("start", {"task_id": task_id, "session_id": session_id})

            current_state = _build_state(request, task_id, session_id)
            final_state, reply_content, is_concluded = await _invoke_agent(current_state)

            if ENABLE_STREAMING:
                for chunk in _split_for_stream(reply_content):
                    yield _event_line("delta", {"text": chunk})
                    await asyncio.sleep(0.02)
            else:
                yield _event_line("delta", {"text": reply_content})

            if is_concluded:
                summary_from_agent = final_state.get("summary_output") or final_state.get("summary_out")
                asyncio.create_task(_call_summary_agent(session_id, task_id, summary_from_agent))

            yield _event_line("done", {
                "task_id": task_id,
                "session_id": session_id,
                "is_concluded": is_concluded,
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
        session_data = memory.get_session_messages(session_id)
        if not session_data:
            print(f"⚠️ 会话 {session_id} 不存在")
            return

        # 如果没有传入总结文本，从会话数据生成
        if not summary_text:
            messages = session_data.get("messages", [])
            topic = session_data.get("topic", "General")

            # 生成总结
            summary_text = summary_generator.generate_session_note(
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
            file_io.save_text(header + summary_text, note_path)
            print(f"✅ 总结已保存：{note_path}")

    except Exception as e:
        print(f"⚠️ 生成总结异常：{e}")

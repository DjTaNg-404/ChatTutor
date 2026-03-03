from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from langchain_core.messages import HumanMessage

from app.core.agent_builder import build_agent
from app.core import memory

router = APIRouter()

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

    # 1. 尝试从本地加载历史会话状态
    current_state = memory.load_session(session_id)
    
    # 2. 如果没有历史记录，初始化一个新的状态；若有历史记录，补全加载时缺失的字段
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
        # 补全旧会话中因版本迭代而新增但尚未持久化的字段
        for key, default_val in _defaults.items():
            current_state.setdefault(key, default_val)
        current_state["task_id"] = task_id
        current_state["session_id"] = session_id
        current_state.setdefault("user_id", "local_user")
        if request.topic:
            current_state["current_topic"] = request.topic
    
    # 3. 将用户的新消息追加到状态中
    user_msg = HumanMessage(content=request.message)
    current_state["messages"].append(user_msg)
    
    # 4. 调用 Agent 图执行逻辑
    try:
        # invoke 会返回最终的状态字典
        final_state = agent_graph.invoke(current_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")
    
    # 5. 提取 AI 的最新回复
    messages = final_state.get("messages", [])
    if not messages:
        raise HTTPException(status_code=500, detail="Agent returned no messages")
        
    last_msg = messages[-1]
    reply_content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
    
    # 6. 检查是否结束对话
    is_concluded = final_state.get("should_exit", False)
    
    return ChatResponse(
        task_id=task_id,
        session_id=session_id,
        reply=reply_content,
        is_concluded=is_concluded
    )

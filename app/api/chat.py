from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from langchain_core.messages import HumanMessage

from app.core.agent_builder import build_agent
from app.core import memory

router = APIRouter()

# Initialize the agent graph once when the module loads
agent_graph = build_agent()

class ChatRequest(BaseModel):
    session_id: str
    message: str
    topic: Optional[str] = "General Knowledge"

class ChatResponse(BaseModel):
    reply: str
    is_concluded: bool

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    核心对话接口。
    接收用户的输入，加载历史会话状态，调用 Agent，并返回 AI 的回复。
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # 1. 尝试从本地加载历史会话状态
    current_state = memory.load_session(request.session_id)
    
    # 2. 如果没有历史记录，初始化一个新的状态
    if not current_state:
        current_state = {
            "messages": [],
            "current_topic": request.topic,
            "session_id": request.session_id,
            "conversation_summary": "",
            "summarized_msg_count": 0,
            "plan": None,
            "should_exit": False,
            "tutor_output": None,
            "judge_output": None,
            "inquiry_output": None,
            "summary_output": None,
            "last_intent": None
        }
    
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
        reply=reply_content,
        is_concluded=is_concluded
    )

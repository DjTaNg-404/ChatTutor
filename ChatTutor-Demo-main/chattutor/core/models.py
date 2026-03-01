from typing import Annotated, Literal, Optional, List, TypedDict
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage

# --- 1. State Definition (Graph的状态) ---
class ExecutionPlan(BaseModel):
    """
    Analyzer 节点生成的执行计划
    """
    needs_tutor_answer: bool = Field(description="是否需要回答用户的疑问")
    needs_judge: bool = Field(description="是否需要评估用户的观点/答案")
    needs_inquiry: bool = Field(description="是否需要进一步提问/探究")
    request_summary: bool = Field(description="用户是否要求总结当前的对话内容")
    is_concluding: bool = Field(description="用户是否想要结束/退出对话")
    thought_process: str = Field(description="做出此计划的简短思考过程")

class AgentState(TypedDict):
    """
    Agent的主状态对象。
    LangGraph 中的状态是累积更新的。
    """
    # 消息历史：使用 add_messages reducer 来追加消息而不是覆盖
    messages: Annotated[List[AnyMessage], add_messages]
    
    # 基础元数据
    current_topic: Optional[str]
    session_id: str
    
    # 上下文记忆
    # 历史对话的压缩总结 (Long-term Context, B部分)
    conversation_summary: Optional[str]
    # 已压缩进摘要的消息游标 (表示 messages[:summarized_msg_count] 已被摘要覆盖)
    summarized_msg_count: int
    
    # 动态规划状态
    plan: Optional[ExecutionPlan]
    should_exit: bool # 信号：通知 CLI 退出主循环
    
    # 各模块的中间输出 (用于 Aggregator 汇总)
    tutor_output: Optional[str]
    judge_output: Optional[str]
    inquiry_output: Optional[str]
    summary_output: Optional[str] # 总结生成的内容
    
    # 临时字段
    last_intent: Optional[str]


# --- 2. Structured Output Models (LLM的结构化输出) ---

class EvaluationOutput(BaseModel):
    """
    评估节点的输出结构。
    用于让 Evaluator LLM 以结构化的 JSON 格式返回判断结果。
    """
    status: Literal["correct", "incorrect", "partial"] = Field(
        description="用户回答的评估结果状态。"
    )
    feedback: str = Field(
        description="给导师Agent的详细反馈。如果错误，解释原因；如果正确，建议更深入的角度。"
    )
    analysis: str = Field(
        description="对用户回答的内部思维链分析。"
    )

class TopicDiscoveryOutput(BaseModel):
    """
    用于从初始对话中提取用户想要学习的话题。
    """
    topic: str = Field(
        description="用户想要学习的核心主题或话题。"
    )

"""
上下文拼装与记忆压缩（供 agent / 计划生成等引用）。

历史相关片段召回仅使用 **Jaccard（字符集合）相似度**，不再使用向量库 / 混合检索。
"""

from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from typing import List, Tuple, Optional
from app.core import models, config

# 上下文管理配置
COMPRESSION_THRESHOLD = 16  # 当"未摘要"的消息超过此数量时触发压缩
KEEP_WINDOW = 5            # 保留最后 N 条消息为原始状态（尚未压缩），以保持对话流畅性
RECALL_TOP_K = 2           # 每次召回最相关的对话对数量
DISPLAY_WINDOW = 12        # 展示给模型的最近消息数量


def retrieve_relevant_messages_v1(
    messages: List[BaseMessage],
    query_text: str,
    exclude_last_n: int,
    top_k: int = 2
) -> str:
    """
    轻量级召回：基于 **Jaccard 相似度**（字符级），从历史里找与当前问题最相关的问答对。
    """
    if not query_text or len(messages) <= exclude_last_n:
        return ""

    searchable_history = messages[:-exclude_last_n]
    query_tokens = set(query_text.lower())

    if not query_tokens:
        return ""

    scored_results = []

    i = 0
    while i < len(searchable_history):
        msg = searchable_history[i]

        if isinstance(msg, HumanMessage):
            content = msg.content.lower()
            msg_tokens = set(content)

            intersection = query_tokens.intersection(msg_tokens)
            union = query_tokens.union(msg_tokens)

            if union:
                score = len(intersection) / len(union)
                if score > 0.05:
                    pair_text = f"User: {msg.content}"
                    if i + 1 < len(searchable_history) and isinstance(searchable_history[i+1], AIMessage):
                        pair_text += f"\nAI: {searchable_history[i+1].content}"
                    scored_results.append((score, pair_text))

        i += 1

    scored_results.sort(key=lambda x: x[0], reverse=True)
    top_items = scored_results[:top_k]

    if not top_items:
        return ""

    result_str = ""
    for idx, (score, text) in enumerate(top_items, 1):
        result_str += f"--- 相关片段 {idx} (相似度: {score:.2f}) ---\n{text}\n"

    return result_str


def retrieve_relevant_messages(
    messages: List[BaseMessage],
    query_text: str,
    exclude_last_n: int,
    top_k: int = 2,
    task_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> str:
    """
    历史片段召回入口（仅 Jaccard）。``task_id`` / ``session_id`` 保留仅为兼容旧调用，不参与检索。
    """
    _ = task_id, session_id
    return retrieve_relevant_messages_v1(
        messages=messages,
        query_text=query_text,
        exclude_last_n=exclude_last_n,
        top_k=top_k,
    )


# ============================================================
# build_context: 构建供 LLM 使用的消息列表
# ============================================================

def build_context(state: models.AgentState, system_prompt: str) -> List[BaseMessage]:
    """
    构建供 LLM 使用的消息列表。
    格式: [System, Summary(如果有), Recall(如果有), Recent Messages]

    这就是"拼装机" (Assembly Machine)。
    """
    final_messages = []

    # 1. 系统提示词 (System Prompt)
    final_messages.append(SystemMessage(content=system_prompt))

    # 2. 长期记忆 (对话摘要)
    summary = state.get("conversation_summary")
    if summary:
        summary_msg = SystemMessage(content=f"【过往对话摘要】\n{summary}\n\n(请利用此摘要作为背景知识，但在回复时请聚焦于最新的对话消息。)")
        final_messages.append(summary_msg)

    # 3. 关联回忆 (从历史中检索相关片段)
    messages = state["messages"]

    if messages and isinstance(messages[-1], HumanMessage):
        current_query = messages[-1].content

        # 使用 Jaccard 相关片段召回
        relevant_context = retrieve_relevant_messages(
            messages=messages,
            query_text=current_query,
            exclude_last_n=DISPLAY_WINDOW,
            top_k=RECALL_TOP_K,
            task_id=state.get("task_id"),
            session_id=state.get("session_id")
        )

        if relevant_context:
            recall_msg = SystemMessage(content=f"【相关历史对话召回】\n(系统自动从历史记录中匹配到的相关信息，辅助本次回答)\n{relevant_context}")
            final_messages.append(recall_msg)

    # 4. 短期记忆 (近期消息)
    recent_messages = state["messages"][-DISPLAY_WINDOW:]
    final_messages.extend(recent_messages)

    return final_messages


# ============================================================
# manage_memory: 检查是否需要压缩并执行
# ============================================================

def manage_memory(state: models.AgentState) -> Tuple[Optional[str], int]:
    """
    检查是否需要压缩并执行。
    返回 (new_summary, new_cursor)。

    这就是"压缩机" (Compression Machine)。
    """
    messages = state["messages"]
    cursor = state.get("summarized_msg_count", 0)
    current_summary = state.get("conversation_summary", "")

    total_count = len(messages)
    unsummarized_count = total_count - cursor

    # 检查触发条件
    if unsummarized_count < COMPRESSION_THRESHOLD:
        return current_summary, cursor

    # 准备压缩数据
    end_index = total_count - KEEP_WINDOW

    # 安全检查
    if end_index <= cursor:
        return current_summary, cursor

    messages_to_compress = messages[cursor:end_index]

    # 将消息转换为字符串
    history_text = ""
    for msg in messages_to_compress:
        role = "User" if isinstance(msg, HumanMessage) else "AI"
        history_text += f"{role}: {msg.content}\n"

    # 通过 LLM 运行压缩
    llm = ChatDeepSeek(
        model=config.settings.MODEL_NAME,
        api_key=config.settings.DEEPSEEK_API_KEY,
        temperature=0.3
    )

    prompt = f"""
你是一名负责维护**Context（上下文）**的精炼记录员。
你的任务是将【新增对话交互】的认知精华，提取并融合进【当前上下文摘要】中。

这是一份**给LLM看的短期记忆索引**，不是给人看的长篇报告。必须在保持信息密度的前提下，极度克制字数。

【当前上下文摘要】:
{current_summary if current_summary else "（尚无记录）"}

【新增对话交互】:
{history_text}

【写作要求】
1. **体现认知递进**：通过逻辑连接词（如"基于此"、"进而"、"反之"），体现用户思维从"疑惑"到"理解"再到"深挖"的路径。
2. **极简主义**：
   - 严禁废话、寒暄和重复。
   - 用词精准，能用一句话说清的，绝不用两句。
   - 只有当新信息真正改变了认知边界时，才增加篇幅；否则请对旧信息进行合并/重写。
3. **动态融合**：将新知"揉"进旧文，而不是简单"追加"在后面。如果之前的某些细节不再重要，请果断删除。

**最终目标**：生成一段**短小精悍**的文本，完美概括我们"目前学到了哪里"以及"思维的上下文脉络"，供系统在下一轮对话中瞬间回溯状态。

【输出】
只输出更新后的上下文摘要文本。
"""

    response = llm.invoke([HumanMessage(content=prompt)])
    new_summary = response.content

    return new_summary, end_index
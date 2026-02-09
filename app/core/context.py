from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from typing import List, Tuple, Optional
from app.core import models, prompts, config

# 上下文管理配置
COMPRESSION_THRESHOLD = 16  # 当“未摘要”的消息超过此数量时触发压缩
KEEP_WINDOW = 5            # 保留最后 N 条消息为原始状态（尚未压缩），以保持对话流畅性
RECALL_TOP_K = 2           # 每次召回最相关的对话对数量

def retrieve_relevant_messages(messages: List[BaseMessage], query_text: str, exclude_last_n: int, top_k: int = 2) -> str:
    """
    轻量级 RAG 召回：基于 Jaccard 相似度（字符级），从历史记录中寻找与当前问题最相关的“问答对”。
    """
    if not query_text or len(messages) <= exclude_last_n:
        return ""

    # 1. 确定搜索范围：排除掉已经在滑动窗口里的消息
    # 我们只搜索 User 消息，然后顺带把它的下一条 AI 回复也带上
    searchable_history = messages[:-exclude_last_n]
    
    # 2. 预处理 Query (字符级 Set，简单有效适应中英文)
    query_tokens = set(query_text.lower())
    if not query_tokens:
        return ""

    scored_results = []
    
    # 遍历历史消息，步长为1，寻找 HumanMessage
    i = 0
    while i < len(searchable_history):
        msg = searchable_history[i]
        
        if isinstance(msg, HumanMessage):
            # 找到一条用户消息，计算相似度
            content = msg.content.lower()
            msg_tokens = set(content)
            
            intersection = query_tokens.intersection(msg_tokens)
            union = query_tokens.union(msg_tokens)
            
            if union:
                score = len(intersection) / len(union)
                # 只有当相似度大于一定阈值（比如有重叠）才考虑
                if score > 0.05: # 稍微设个门槛，哪怕很低
                    # 尝试找到对应的 AI 回复 (它后面紧接着的一条)
                    pair_text = f"User: {msg.content}"
                    if i + 1 < len(messages): 
                         if i + 1 < len(searchable_history) and isinstance(searchable_history[i+1], AIMessage):
                             pair_text += f"\nAI: {searchable_history[i+1].content}"
                    
                    scored_results.append((score, pair_text))
        
        i += 1
        
    # 3. 排序并取 Top K
    scored_results.sort(key=lambda x: x[0], reverse=True)
    top_items = scored_results[:top_k]
    
    if not top_items:
        return ""
        
    # 4. 格式化输出
    result_str = ""
    for idx, (score, text) in enumerate(top_items, 1):
        result_str += f"--- 相关片段 {idx} (相似度: {score:.2f}) ---\n{text}\n"
        
    return result_str

def build_context(state: models.AgentState, system_prompt: str) -> List[BaseMessage]:
    """
    构建供 LLM 使用的消息列表。
    格式: [System, Summary(如果有), Recent Messages]
    
    这就是“拼装机” (Assembly Machine)。
    """
    final_messages = []
    
    # 1. 系统提示词 (System Prompt)
    final_messages.append(SystemMessage(content=system_prompt))
    
    # 2. 长期记忆 (对话摘要)
    summary = state.get("conversation_summary")
    if summary:
        # 将摘要作为系统级上下文或特殊前言注入
        summary_msg = SystemMessage(content=f"【过往对话摘要】\n{summary}\n\n(请利用此摘要作为背景知识，但在回复时请聚焦于最新的对话消息。)")
        final_messages.append(summary_msg)
        
    # 3. 关联回忆 (从旧历史中捞出的相关片段)
    # 假设我们最多展示最后 12 条消息。
    DISPLAY_WINDOW = 12

    messages = state["messages"]
    # 尝试提取用户的当前问题进行召回
    if messages and isinstance(messages[-1], HumanMessage):
        current_query = messages[-1].content
        relevant_context = retrieve_relevant_messages(
            messages, 
            current_query, 
            exclude_last_n=DISPLAY_WINDOW,
            top_k=RECALL_TOP_K
        )
        if relevant_context:
            recall_msg = SystemMessage(content=f"【相关历史对话召回】\n(系统自动从历史记录中匹配到的相关信息，辅助本次回答)\n{relevant_context}")
            final_messages.append(recall_msg)

    # 4. 短期记忆 (近期消息)
    # 策略: 我们相信磁盘中的 state['messages'] 是完整历史。
    # 在运行时，我们只想将最后 N 条消息提供给模型以节省 Token。
    # 我们使用固定窗口大小以保持简单和稳健。
    # (注意: 这与压缩逻辑的游标 cursor 是独立的。即使我们将索引 90 之前的都压缩了，
    # 我们可能仍然展示哪怕是已经压缩过的最后 10 条消息，以获得更好的即时上下文。)
    
    recent_messages = state["messages"][-DISPLAY_WINDOW:]
    final_messages.extend(recent_messages)
    
    return final_messages

def manage_memory(state: models.AgentState) -> Tuple[Optional[str], int]:
    """
    检查是否需要压缩并执行。
    返回 (new_summary, new_cursor)。
    
    这就是“压缩机” (Compression Machine)。
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
    # 我们想要压缩: messages[cursor : total_count - KEEP_WINDOW]
    # 我们保留最后 KEEP_WINDOW 条消息为原始状态留待下次使用。
    end_index = total_count - KEEP_WINDOW
    
    # 安全检查: 确保有内容可以压缩
    if end_index <= cursor:
        return current_summary, cursor
        
    messages_to_compress = messages[cursor:end_index]
    
    # 将消息转换为字符串以供 Prompt 使用
    history_text = ""
    for msg in messages_to_compress:
        role = "User" if isinstance(msg, HumanMessage) else "AI"
        history_text += f"{role}: {msg.content}\n"
        
    # 通过 LLM 运行压缩
    # 我们使用轻量级实例或主实例
    llm = ChatDeepSeek(
        model=config.settings.MODEL_NAME,
        api_key=config.settings.DEEPSEEK_API_KEY,
        temperature=0.3 # Lower temp for stable summarization
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
1. **体现认知递进**：通过逻辑连接词（如“基于此”、“进而”、“反之”），体现用户思维从“疑惑”到“理解”再到“深挖”的路径。
2. **极简主义**：
   - 严禁废话、寒暄和重复。
   - 用词精准，能用一句话说清的，绝不用两句。
   - 只有当新信息真正改变了认知边界时，才增加篇幅；否则请对旧信息进行合并/重写。
3. **动态融合**：将新知“揉”进旧文，而不是简单“追加”在后面。如果之前的某些细节不再重要，请果断删除。

**最终目标**：生成一段**短小精悍**的文本，完美概括我们“目前学到了哪里”以及“思维的上下文脉络”，供系统在下一轮对话中瞬间回溯状态。

【输出】
只输出更新后的上下文摘要文本。
"""
    
    response = llm.invoke([HumanMessage(content=prompt)])
    new_summary = response.content
    
    # Return updated state values
    return new_summary, end_index

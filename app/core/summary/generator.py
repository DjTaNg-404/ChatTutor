"""
总结生成器核心逻辑
"""
from typing import Dict, Any, List, Optional
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import settings
from app.core.summary.prompts import (
    SUMMARIZER_REVIEW_PROMPT,
    SUMMARIZER_NOTE_PROMPT,
    DAILY_SUMMARY_PROMPT,
    TASK_SUMMARY_PROMPT
)


class SummaryGenerator:
    """总结生成器"""

    def __init__(self):
        """初始化总结生成器"""
        self.model = ChatDeepSeek(
            model=settings.MODEL_NAME,
            api_key=settings.DEEPSEEK_API_KEY,
            temperature=0.7
        )

    def generate_review_summary(
        self,
        conversation_history: List[Dict[str, str]],
        topic: str = "General"
    ) -> str:
        """
        生成临时回顾总结（用户在对话中要求的即时总结）

        Args:
            conversation_history: 对话历史列表，每项包含 {"role": "user/assistant", "content": "..."}
            topic: 当前话题

        Returns:
            总结文本
        """
        sys_msg = SystemMessage(content=SUMMARIZER_REVIEW_PROMPT)

        # 构造对话历史消息
        messages = [sys_msg]
        messages.append(SystemMessage(content=f"当前话题：{topic}"))

        # 添加对话历史
        for msg in conversation_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(SystemMessage(content=content))

        # 添加总结指令
        messages.append(HumanMessage(content="请总结我们刚才对话的核心要点。"))

        response = self.model.invoke(messages)
        return response.content

    def generate_session_note(
        self,
        conversation_history: List[Dict[str, str]],
        topic: str = "General"
    ) -> str:
        """
        生成离场学习笔记（会话结束时的深度学习简报）

        Args:
            conversation_history: 对话历史列表
            topic: 当前话题

        Returns:
            学习笔记文本（Markdown 格式）
        """
        sys_msg = SystemMessage(content=SUMMARIZER_NOTE_PROMPT)

        messages = [sys_msg]
        messages.append(SystemMessage(content=f"当前话题：{topic}"))

        # 添加对话历史
        for msg in conversation_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(SystemMessage(content=content))

        messages.append(HumanMessage(content="请生成一份高密度的学习简报。"))

        response = self.model.invoke(messages)
        return response.content

    def generate_daily_summary(
        self,
        sessions: List[Dict[str, Any]],
        task_id: str,
        date: str
    ) -> str:
        """
        生成每日学习总结

        Args:
            sessions: 当天所有会话列表，每项包含会话的完整信息
            task_id: 任务 ID
            date: 日期字符串 (YYYY-MM-DD)

        Returns:
            每日总结文本（Markdown 格式）
        """
        # 构造任务标题
        task_titles = {
            "task_1": "掌握随机森林算法",
            "task_2": "雅思口语备考",
            "task_3": "React Hooks 深入",
            "task_4": "机器学习数学基础",
        }
        task_title = task_titles.get(task_id, task_id)

        # 合并所有会话的对话历史
        all_messages = []
        for session in sessions:
            messages = session.get("messages", [])
            all_messages.extend(messages)

        # 构造 prompt
        prompt_text = DAILY_SUMMARY_PROMPT.format(
            date=date,
            task_title=task_title
        )

        sys_msg = SystemMessage(content=prompt_text)
        messages = [sys_msg]

        # 添加对话历史
        for msg in all_messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(SystemMessage(content=content))

        messages.append(HumanMessage(content="请生成今日学习报告。"))

        response = self.model.invoke(messages)
        return response.content

    def generate_task_summary(
        self,
        sessions: List[Dict[str, Any]],
        task_id: str
    ) -> str:
        """
        生成任务学习总结（对整个任务的所有对话生成总结）

        Args:
            sessions: 任务所有会话列表，每项包含会话的完整信息
            task_id: 任务 ID

        Returns:
            任务总结文本（Markdown 格式）
        """
        # 构造任务标题
        task_titles = {
            "task_1": "掌握随机森林算法",
            "task_2": "雅思口语备考",
            "task_3": "React Hooks 深入",
            "task_4": "机器学习数学基础",
        }
        task_title = task_titles.get(task_id, task_id)

        # 合并所有会话的对话历史
        all_messages = []
        for session in sessions:
            messages = session.get("messages", [])
            all_messages.extend(messages)

        # 构造 prompt
        prompt_text = TASK_SUMMARY_PROMPT.format(
            task_title=task_title
        )

        sys_msg = SystemMessage(content=prompt_text)
        messages = [sys_msg]

        # 添加对话历史
        for msg in all_messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(SystemMessage(content=content))

        messages.append(HumanMessage(content="请生成任务学习总结。"))

        response = self.model.invoke(messages)
        return response.content


# 全局单例
summary_generator = SummaryGenerator()

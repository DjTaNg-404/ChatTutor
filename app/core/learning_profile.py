"""
Learning Profile (事实卡片) 模块

作用：
1) 把"长期学习画像"抽象为结构化 Fact Cards，避免长期保存原始对话。
2) 提供加载/保存/去重/抽取等工具函数，供 Agent 在每轮对话结束后更新画像。

调用链（后续如何被使用）：
- app/core/agent_builder.py
  - _inject_profile(...) 在构建 Prompt 时调用 profile_summary(...) 注入画像摘要
  - aggregator_node(...) 在生成回复后调用 extract_learning_facts(...) -> upsert_cards(...) -> save_profile(...)
"""
import os
import re
import time
from typing import Any, Dict, List

from app.utils import file_io

# 学习画像存储目录（每个 learner_id 一个 JSON）
PROFILE_DIR = "memory/learner_profiles"


def _profile_path(learner_id: str) -> str:
    """计算画像文件路径：memory/learner_profiles/{learner_id}.json"""
    safe_id = learner_id or "anonymous"
    return os.path.join(PROFILE_DIR, f"{safe_id}.json")


def load_profile(learner_id: str) -> Dict[str, Any]:
    """
    加载学习画像；不存在则返回空结构。
    被 agent_builder 的 _inject_profile(...) 调用。
    """
    path = _profile_path(learner_id)
    if not os.path.exists(path):
        return {
            "learner_id": learner_id,
            "updated_at": None,
            "cards": []
        }
    return file_io.load_json(path)


def save_profile(profile: Dict[str, Any]) -> str:
    """
    保存学习画像（覆盖写）。
    被 agent_builder 的 aggregator_node(...) 在每轮对话结束后调用。
    """
    profile["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    return file_io.save_json(profile, _profile_path(profile.get("learner_id", "anonymous")))


def _dedupe_cards(cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按 fact_type + fields 去重，避免重复卡片膨胀。"""
    seen = set()
    out = []
    for c in cards:
        key = (c.get("fact_type"), str(c.get("fields", {})))
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def upsert_cards(profile: Dict[str, Any], new_cards: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    合并并去重卡片。
    被 agent_builder 的 aggregator_node(...) 调用。
    """
    if not new_cards:
        return profile
    merged = profile.get("cards", []) + new_cards
    profile["cards"] = _dedupe_cards(merged)
    return profile


def extract_learning_facts(user_text: str, assistant_text: str, source: str) -> List[Dict[str, Any]]:
    """
    从"本轮用户输入 + 本轮助手回复"中提取学习画像事实卡片（轻量规则版）。
    被 agent_builder 的 aggregator_node(...) 调用。
    """
    text = f"{user_text}\n{assistant_text}"
    cards: List[Dict[str, Any]] = []

    def add_card(ftype: str, fields: Dict[str, Any]):
        # 统一卡片结构，便于后续扩展/序列化
        cards.append({
            "type": "learning_fact",
            "fact_type": ftype,
            "fields": fields,
            "source": source,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S")
        })

    # goal
    m = re.search(r"(?:我想学|我要学|学习目标|目标是|希望|打算)\s*([^\n，。,！!？?]{1,30})", text)
    if m:
        add_card("goal", {"subject": m.group(1)})

    # preference (style/pace)
    m = re.search(r"(?:我喜欢|我更喜欢|请用|能不能用)\s*([^\n，。,！!？?]{1,30})", text)
    if m:
        add_card("preference", {"style": m.group(1)})

    # skill_state (weak/unclear)
    m = re.search(r"(?:我不懂|不理解|不会|不太会|还不明白)\s*([^\n，。,！!？?]{1,30})", text)
    if m:
        add_card("skill_state", {"topic": m.group(1), "level": "weak"})

    # misconception
    m = re.search(r"(?:总是错|老是错|容易混淆)\s*([^\n，。,！!？?]{1,30})", text)
    if m:
        add_card("misconception", {"topic": m.group(1)})

    # progress
    m = re.search(r"(?:已经学完|完成了|学完了)\s*([^\n，。,！!？?]{1,30})", text)
    if m:
        add_card("progress", {"milestone": m.group(1)})

    # assessment (score)
    m = re.search(r"(?:得分|成绩|分数)[:：]?\s*(\d{1,3})", text)
    if m:
        add_card("assessment", {"score": int(m.group(1))})

    return cards


def profile_summary(profile: Dict[str, Any], max_items: int = 6) -> str:
    """
    把画像卡片压缩成可注入 Prompt 的摘要文本。
    被 agent_builder 的 _inject_profile(...) 调用。
    """
    cards = profile.get("cards", [])
    if not cards:
        return ""
    recent = cards[-max_items:]
    lines = []
    for c in recent:
        ftype = c.get("fact_type")
        fields = c.get("fields", {})
        lines.append(f"- {ftype}: {fields}")
    return "\n".join(lines)

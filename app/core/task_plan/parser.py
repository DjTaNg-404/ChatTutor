"""
Task Plan Agent - Parser
"""
import json
import re
from typing import Any, Dict, List, Optional


def _extract_json_block(text: str) -> Optional[str]:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        return match.group(0) if match else None
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    return match.group(0) if match else None


def _parse_plan_response(text: str) -> Optional[Dict[str, Any]]:
    json_block = _extract_json_block(text)
    if not json_block:
        return None
    try:
        data = json.loads(json_block)
    except Exception:
        return None
    if isinstance(data, dict) and "plan" in data and isinstance(data["plan"], dict):
        return data["plan"]
    return data if isinstance(data, dict) else None


def _split_steps_from_text(text: str) -> List[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    steps: List[str] = []
    for line in lines:
        stripped = re.sub(r"^\s*[-*•]\s*", "", line)
        stripped = re.sub(r"^\s*\d+[\.\)\-、]\s*", "", stripped)
        if stripped:
            steps.append(stripped)
    if steps:
        return steps
    return [cleaned]

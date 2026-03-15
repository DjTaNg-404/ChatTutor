"""
知识图谱查看器 - 数据加载工具
"""

import os
import json
import glob
from datetime import datetime
from pathlib import Path


# 获取 kg_viewer 目录的父目录（项目根目录）
KG_VIEWER_DIR = Path(__file__).parent
PROJECT_ROOT = KG_VIEWER_DIR.parent.parent
KG_OUTPUT_DIR = PROJECT_ROOT / "kg_output"


def list_kg_files(kg_dir: str = None) -> list:
    """列出所有知识图谱 JSON 文件"""
    if kg_dir is None:
        kg_dir = str(KG_OUTPUT_DIR)
    pattern = os.path.join(kg_dir, "*.json")
    files = glob.glob(pattern)
    # 按修改时间排序，最新的在前
    files.sort(key=os.path.getmtime, reverse=True)
    return files


def load_kg_data(file_path: str) -> dict:
    """加载知识图谱 JSON 数据"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_file_display_name(file_path: str) -> str:
    """生成文件的显示名称"""
    filename = os.path.basename(file_path)
    # 提取 session_id 部分
    if filename.startswith("kg_"):
        session_id = filename[3:-5]  # 去掉 kg_ 和 .json
        # 尝试解析日期时间
        parts = session_id.split("__")
        if len(parts) >= 2:
            date_str = parts[-2] if len(parts) >= 2 else parts[0]
            time_str = parts[-1] if len(parts) >= 2 else ""
            try:
                dt = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
                return f"{parts[0]} - {dt.strftime('%Y-%m-%d %H:%M')}"
            except ValueError:
                pass
    return filename

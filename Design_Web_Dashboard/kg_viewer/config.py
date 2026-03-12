"""
知识图谱查看器 - 配置常量
"""

# 实体类型颜色映射
ENTITY_TYPE_COLORS = {
    "PER": "#FF6B6B",      # 人名 - 红色
    "ORG": "#4ECDC4",      # 组织 - 青色
    "LOC": "#45B7D1",      # 地点 - 蓝色
    "MISC": "#96CEB4",     # 其他 - 绿色
    "METHOD": "#FFA07A",   # 方法 - 浅橙色
    "TECH": "#9370DB",     # 技术 - 紫色
    "GENERAL": "#B0C4DE",  # 通用 - 浅蓝色
    "DOMAIN": "#FFD93D",   # 领域 - 黄色
}

# 关系类型样式
RELATION_STYLES = {
    "work_for": {"color": "#FF6B6B", "width": 3},
    "located_in": {"color": "#4ECDC4", "width": 2},
    "related_to": {"color": "#96CEB4", "width": 1},
    "associated_with": {"color": "#FFA07A", "width": 2},
    "cooperate_with": {"color": "#45B7D1", "width": 2},
}

# 实体类型中文映射
ENTITY_TYPE_NAMES = {
    "PER": "人名",
    "ORG": "组织",
    "LOC": "地点",
    "MISC": "其他",
    "METHOD": "方法",
    "TECH": "技术",
    "GENERAL": "通用",
    "DOMAIN": "领域",
}

# 关系类型中文映射
RELATION_TYPE_NAMES = {
    "work_for": "工作于",
    "located_in": "位于",
    "related_to": "相关",
    "associated_with": "关联",
    "cooperate_with": "合作",
}

# CSS 样式
CUSTOM_CSS = """
<style>
.stApp {
    background: radial-gradient(ellipse at center, #334155 0%, #1e293b 35%, #0f172a 65%, #020617 100%);
    background-size: 100% 100%;
}
.stApp::before {
    content: '';
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: radial-gradient(ellipse at 50% 50%, rgba(99, 102, 241, 0.1) 0%, transparent 60%),
                radial-gradient(ellipse at 20% 30%, rgba(59, 130, 246, 0.08) 0%, transparent 40%),
                radial-gradient(ellipse at 80% 70%, rgba(139, 92, 246, 0.1) 0%, transparent 45%);
    pointer-events: none;
    z-index: -1;
}
.stMarkdown, .stMetric {
    color: #ffffff;
}
.stSubHeader {
    color: #ffffff !important;
}
div[data-testid="stPlotlyChart"] {
    background-color: transparent !important;
}
div[data-testid="stAltairChart"] {
    background-color: transparent !important;
}
.vega-binding, .vega-controls {
    background-color: transparent !important;
}
div[data-testid="stBarChart"] {
    background-color: transparent !important;
}
.streamlit-expanderHeader {
    background-color: transparent !important;
    color: #ffffff !important;
}
.streamlit-expanderContent {
    background-color: rgba(255, 255, 255, 0.05) !important;
}
.stDataFrame {
    background-color: transparent !important;
}
[data-testid="stMetricLabel"] {
    color: #a0a0a0 !important;
}
[data-testid="stMetricValue"] {
    color: #c0c0c0 !important;
}
[data-testid="stMetricDelta"] {
    color: #909090 !important;
}
</style>
"""

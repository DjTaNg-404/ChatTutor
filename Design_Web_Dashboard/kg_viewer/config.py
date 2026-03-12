"""
知识图谱查看器 - 配置常量
"""

import hashlib

# 实体类型聚合映射 - 将细粒度类型聚合到大的分类
ENTITY_TYPE_CATEGORIES = {
    "学习相关": [
        "学习方法", "学习框架", "学习平台", "学习重点", "教育概念",
        "学习技巧", "学习资源", "学习目标", "学习内容", "学习过程",
        "在线平台", "平台", "教育平台"
    ],
    "技术技能": [
        "技能/技术", "TECH", "SQL 高级主题", "SQL 高级特性", "SQL 高级",
        "编程语言", "开发工具", "技术栈", "框架", "数据库",
        "技能", "能力", "技术能力", "专业能力"
    ],
    "职业发展": [
        "职业角色", "职业目标", "职位", "职业方向", "工作类型",
        "职业", "岗位", "工作", "角色"
    ],
    "基础类型": [
        "PER", "ORG", "LOC", "MISC", "人名", "组织", "地点", "其他"
    ],
    "通用概念": [
        "GENERAL", "DOMAIN", "概念", "工具", "方法", "METHOD",
        "理论", "模型", "标准", "规范"
    ],
}

# 反向映射：具体类型 -> 大类
TYPE_TO_CATEGORY = {}
for category, types in ENTITY_TYPE_CATEGORIES.items():
    for t in types:
        TYPE_TO_CATEGORY[t] = category


def get_entity_category(entity_type: str) -> str:
    """
    获取实体类型所属的大类。

    Args:
        entity_type: 具体的实体类型

    Returns:
        所属的大类名称
    """
    # 如果传入的已经是大类名称，直接返回
    if entity_type in ENTITY_TYPE_CATEGORIES:
        return entity_type
    # 否则查找映射
    return TYPE_TO_CATEGORY.get(entity_type, "通用概念")


# 大类颜色映射 - 每个大类使用不同的颜色
CATEGORY_COLORS = {
    "学习相关": "#FFB347",      # 橙黄色
    "技术技能": "#9370DB",      # 紫色
    "职业发展": "#FF6961",      # 粉红色
    "基础类型": "#4ECDC4",      # 青色
    "通用概念": "#77DD77",      # 绿色
}


# 实体类型颜色映射（扩展版）
ENTITY_TYPE_COLORS = {
    # 基础类型
    "PER": "#FF6B6B",      # 人名 - 红色
    "ORG": "#4ECDC4",      # 组织 - 青色
    "LOC": "#45B7D1",      # 地点 - 蓝色
    "MISC": "#96CEB4",     # 其他 - 绿色

    # 技术和方法
    "TECH": "#9370DB",     # 技术 - 紫色
    "技能/技术": "#9370DB",  # 技术技能 - 紫色
    "METHOD": "#FFA07A",   # 方法 - 浅橙色
    "学习方法": "#FFB347",  # 学习方法 - 橙色

    # 学习和教育
    "学习框架": "#77DD77",  # 学习框架 - 绿色
    "学习平台": "#AEC6CF",  # 学习平台 - 浅蓝色
    "学习重点": "#FFB347",  # 学习重点 - 橙黄色
    "教育概念": "#77DD77",  # 教育概念 - 浅绿色

    # 职业相关
    "职业角色": "#FF6961",  # 职业角色 - 粉红色
    "职业目标": "#FF6961",  # 职业目标 - 粉红色

    # 技术领域
    "SQL 高级主题": "#CBAACB",  # SQL 高级主题 - 浅紫色
    "SQL 高级特性": "#CBAACB",  # SQL 高级特性 - 浅紫色

    # 通用类型
    "GENERAL": "#B0C4DE",  # 通用 - 浅蓝色
    "DOMAIN": "#FFD93D",   # 领域 - 黄色
    "概念": "#B39EB5",     # 概念 - 浅紫色
    "工具": "#87CEEB",     # 工具 - 天蓝色
}

# 颜色调色板（用于动态生成未知类型的颜色）
COLOR_PALETTE = [
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFA07A",
    "#9370DB", "#B0C4DE", "#FFD93D", "#FF6961", "#77DD77",
    "#AEC6CF", "#CBAACB", "#B39EB5", "#87CEEB", "#FFB347",
    "#DAA520", "#FF7F50", "#32CD32", "#00CED1", "#FF1493",
]


def get_entity_type_color(entity_type: str, by_category: bool = True) -> str:
    """
    获取实体类型的颜色。

    Args:
        entity_type: 实体类型字符串
        by_category: 是否按大类返回颜色（True 返回大类颜色，False 返回具体类型颜色）

    Returns:
        十六进制颜色代码
    """
    # 如果按大类着色
    if by_category:
        category = get_entity_category(entity_type)
        if category in CATEGORY_COLORS:
            return CATEGORY_COLORS[category]

    # 首先检查预定义映射（具体类型颜色）
    if entity_type in ENTITY_TYPE_COLORS:
        return ENTITY_TYPE_COLORS[entity_type]

    # 如果不存在，根据类型名称动态生成颜色
    # 使用哈希确保同一类型始终获得相同颜色
    hash_val = int(hashlib.md5(entity_type.encode('utf-8')).hexdigest(), 16)
    color_index = hash_val % len(COLOR_PALETTE)
    return COLOR_PALETTE[color_index]


def get_entity_color_by_type(entity_type: str) -> str:
    """
    根据实体类型的大类获取颜色（用于按大类着色的场景）。

    Args:
        entity_type: 实体类型字符串

    Returns:
        所属大类的颜色
    """
    return get_entity_type_color(entity_type, by_category=True)


# 关系类型样式 - 不同的关系类型使用不同的颜色
RELATION_STYLES = {
    # 结构和组成关系
    "part_of": {"color": "#9370DB", "width": 3},       # 紫色 - 部分与整体
    "contains": {"color": "#9370DB", "width": 3},      # 紫色 - 包含
    "包含": {"color": "#9370DB", "width": 3},          # 紫色 - 包含

    # 分类和归属关系
    "is_a": {"color": "#FF6B6B", "width": 2},          # 红色 - 类型
    "belongs_to": {"color": "#FF6B6B", "width": 2},    # 红色 - 归属
    "属于": {"color": "#FF6B6B", "width": 2},          # 红色 - 属于

    # 使用和依赖关系
    "uses": {"color": "#77DD77", "width": 2},          # 绿色 - 使用
    "depends_on": {"color": "#FFB347", "width": 2},    # 橙色 - 依赖

    # 位置和工作关系
    "located_in": {"color": "#4ECDC4", "width": 2},    # 青色 - 位置
    "work_for": {"color": "#45B7D1", "width": 2},      # 蓝色 - 工作

    # 合作和关联关系
    "cooperate_with": {"color": "#AEC6CF", "width": 2}, # 浅蓝色 - 合作
    "associated_with": {"color": "#FFA07A", "width": 2}, # 浅橙色 - 关联

    # 因果关系
    "causes": {"color": "#FF6961", "width": 2},        # 粉红色 - 导致
    "enables": {"color": "#87CEEB", "width": 2},       # 天蓝色 - 使能

    # 应用关系
    "应用于": {"color": "#B39EB5", "width": 2},        # 浅紫色 - 应用
    "应用": {"color": "#B39EB5", "width": 2},          # 浅紫色 - 应用

    # 学习关系
    "学习": {"color": "#CBAACB", "width": 2},          # 浅紫色 - 学习

    # 默认关系
    "related_to": {"color": "#96CEB4", "width": 1},    # 浅绿色 - 一般相关（默认）
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

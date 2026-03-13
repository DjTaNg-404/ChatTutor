"""
知识图谱查看器 - 侧边栏组件
"""

import streamlit as st
from pathlib import Path

from data_loader import list_kg_files, get_file_display_name

# 获取静态资源路径
STATIC_DIR = Path(__file__).parent / "static"
THINK_ICON_PATH = STATIC_DIR / "think.png"


def render_sidebar():
    """渲染侧边栏"""
    # 图标和标题在同一行
    col1, col2 = st.sidebar.columns([1, 5], gap="small")
    with col1:
        st.image(str(THINK_ICON_PATH), width=40)
    with col2:
        st.sidebar.title("知识图谱查看器")

    # 选择知识图谱文件
    kg_files = list_kg_files()

    if not kg_files:
        st.sidebar.warning("未找到知识图谱文件")
        st.sidebar.info("请先运行对话并结束会话，知识图谱将在会话结束后自动生成")
        return None

    # 文件选择器
    file_options = [get_file_display_name(f) for f in kg_files]
    selected = st.sidebar.selectbox(
        "选择知识图谱",
        options=file_options,
        index=0
    )

    # 获取选中的文件路径
    selected_idx = file_options.index(selected)
    return kg_files[selected_idx]


def render_settings_panel(kg_file: str):
    """渲染设置面板"""
    # st.sidebar.markdown("---")
    st.sidebar.subheader("🎯 置信度过滤")
    confidence_threshold = st.sidebar.slider(
        "实体置信度阈值",
        min_value=0.0,
        max_value=1.0,
        value=0.8,
        step=0.05,
        help="低于此阈值的节点将被隐藏"
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("🔗 关系过滤")
    relation_strength_threshold = st.sidebar.slider(
        "关系强度阈值",
        min_value=0.0,
        max_value=1.0,
        value=0.8,
        step=0.002,
        help="低于此强度的关系边将被隐藏"
    )

    # 孤立节点过滤（只显示有连接的节点）
    hide_isolated_nodes = st.sidebar.checkbox(
        "隐藏孤立节点",
        value=True,
        help="不显示没有任何连接的节点"
    )

    return confidence_threshold, relation_strength_threshold, hide_isolated_nodes


def render_entity_legend(entity_types: dict):
    """渲染实体类型图例（直接使用基础类型）"""
    from config import get_entity_color_by_type

    st.sidebar.markdown("---")
    st.sidebar.subheader("🏷️ 实体类型")

    # 直接使用实体类型计数，不再聚合到大类
    # 按计数排序
    sorted_types = sorted(entity_types.items(), key=lambda x: x[1], reverse=True)

    for etype, count in sorted_types:
        color = get_entity_color_by_type(etype)
        col1, col2 = st.sidebar.columns([1, 3], gap="small")
        with col1:
            st.markdown(
                f"<div style='background-color:{color};width:20px;height:20px;"
                f"border-radius:50%;display:inline-block;'></div>",
                unsafe_allow_html=True
            )
        with col2:
            st.markdown(f"<span style='color:{color}'>{etype} ({count})</span>", unsafe_allow_html=True)


def render_relation_legend(relation_types: dict):
    """渲染关系类型图例"""
    from config import RELATION_STYLES

    st.sidebar.markdown("---")
    st.sidebar.subheader("🔗 关系类型")

    # 按类型名称排序
    sorted_types = sorted(relation_types.items(), key=lambda x: x[1], reverse=True)

    for rtype, count in sorted_types:
        style = RELATION_STYLES.get(rtype, {"color": "#888", "width": 1})
        color = style["color"]
        col1, col2 = st.sidebar.columns([1, 3], gap="small")
        with col1:
            st.markdown(
                f"<div style='background-color:{color};"
                f"width:20px;height:5px;display:inline-block;'></div>",
                unsafe_allow_html=True
            )
        with col2:
            st.markdown(f"<span style='color:{color}'>{rtype} ({count})</span>", unsafe_allow_html=True)


def render_data_browser():
    """渲染数据浏览器"""
    st.sidebar.markdown("---")
    if st.sidebar.button("📂 刷新文件列表"):
        st.rerun()

"""
知识图谱查看器 - 主程序
"""

import streamlit as st

from config import CUSTOM_CSS
from sidebar import render_sidebar, render_settings_panel, render_entity_legend, render_relation_legend, render_data_browser
from main_view import render_main_view
from data_loader import load_kg_data
from stats_utils import calculate_stats


def main():
    """主函数"""
    st.set_page_config(
        page_title="ChatTutor 知识图谱查看器",
        page_icon="🕸️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # 自定义 CSS 样式
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # 渲染侧边栏
    selected_file = render_sidebar()

    if selected_file is None:
        st.title("🕸️ 知识图谱查看器")
        st.write("暂无可用的知识图谱数据")
        return

    # 渲染设置面板
    confidence_threshold, relation_strength_threshold, hide_isolated_nodes = render_settings_panel(selected_file)

    # 渲染数据浏览器
    render_data_browser()

    # 渲染主视图
    render_main_view(selected_file, confidence_threshold, relation_strength_threshold, hide_isolated_nodes)

    # 渲染图例
    kg_data = load_kg_data(selected_file)
    stats = calculate_stats(kg_data.get("nodes", []), kg_data.get("edges", []))

    if stats["entity_types"]:
        render_entity_legend(stats["entity_types"])

    if stats["relation_types"]:
        render_relation_legend(stats["relation_types"])


if __name__ == "__main__":
    main()

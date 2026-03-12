"""
知识图谱查看器 - 主程序
"""

import streamlit as st
import os

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

    # 检查 URL 参数中的 task_id
    query_params = st.query_params
    task_id = query_params.get("task_id", None)

    # 确定 KG 文件路径
    selected_file = None
    found_via_task_id = False

    # 如果有 task_id，查找对应的 KG 文件（支持带时间戳的文件名）
    if task_id:
        kg_output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "kg_output")

        # 使用 glob 匹配：kg_task_{task_id}*.json 或 kg_{task_id}*.json
        import glob
        pattern1 = os.path.join(kg_output_dir, f"kg_task_{task_id}*.json")
        pattern2 = os.path.join(kg_output_dir, f"kg_{task_id}*.json")
        matching_files = glob.glob(pattern1) + glob.glob(pattern2)

        if matching_files:
            # 按修改时间排序，选择最新的
            matching_files.sort(key=os.path.getmtime, reverse=True)
            selected_file = matching_files[0]
            found_via_task_id = True
        else:
            # 文件不存在，显示警告，但仍然渲染侧边栏供用户选择
            st.sidebar.warning(f"未找到 task_id={task_id} 对应的知识图谱文件")
            st.sidebar.info("请先点击「更新知识图谱」按钮生成知识图谱")
            # 继续渲染侧边栏，让用户可以选择其他文件

    # 如果没有通过 task_id 找到文件，使用侧边栏选择
    if not found_via_task_id:
        selected_file = render_sidebar()

    if selected_file is None:
        st.write("暂无可用的知识图谱数据")
        return

    if not os.path.exists(selected_file):
        st.error(f"文件不存在：{selected_file}")
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

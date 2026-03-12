"""
知识图谱查看器 - 主视图组件
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from stats_utils import calculate_stats, filter_nodes_by_confidence
from graph_renderer import calculate_graph_layout, create_plotly_figure
from data_loader import load_kg_data


def render_main_view(kg_file: str, confidence_threshold: float,
                    relation_strength_threshold: float, hide_isolated_nodes: bool = True):
    """渲染主视图"""
    # 加载数据
    kg_data = load_kg_data(kg_file)
    nodes = kg_data.get("nodes", [])
    edges = kg_data.get("edges", [])

    if not nodes:
        st.error("知识图谱为空，没有可显示的数据")
        return

    # 根据置信度、关系强度过滤
    filtered_nodes, filtered_edges = filter_nodes_by_confidence(
        nodes, edges, confidence_threshold, relation_strength_threshold, hide_isolated_nodes
    )

    # 显示过滤提示
    if confidence_threshold > 0:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info(f"当前置信度阈值：{confidence_threshold:.2f}，显示 {len(filtered_nodes)}/{len(nodes)} 个节点")
        with col2:
            if st.button("重置阈值"):
                st.session_state["confidence_threshold"] = 0.0
                st.rerun()

    if not filtered_nodes:
        st.warning("当前阈值下没有可显示的节点，请降低置信度阈值")
        return

    # 使用 Plotly 渲染
    show_labels = True
    node_size = 1.0
    layout_method = "force"
    pos, _ = calculate_graph_layout(filtered_nodes, filtered_edges, layout_method)
    fig = create_plotly_figure(filtered_nodes, filtered_edges, pos, show_labels, node_size)
    st.plotly_chart(fig, width='stretch', key="kg_graph")

    # 显示统计信息（使用过滤后的数据）
    stats = calculate_stats(filtered_nodes, filtered_edges)
    total_stats = calculate_stats(nodes, edges)  # 保留总数统计

    # 详细信息展开栏
    with st.expander("📈 详细统计信息"):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("显示节点", f"{stats['total_nodes']}/{total_stats['total_nodes']}")
        col2.metric("显示边", f"{stats['total_edges']}/{total_stats['total_edges']}")
        col3.metric("平均置信度", f"{stats['avg_score']:.3f}")
        col4.metric("最高置信度", f"{stats['max_score']:.3f}")

        if stats["entity_types"]:
            # 直接使用实体类型统计，不再聚合到大类
            types = list(stats["entity_types"].keys())
            counts = list(stats["entity_types"].values())

            fig = go.Figure(data=[
                go.Bar(x=types, y=counts, marker_color='#3674BA', showlegend=False)
            ])
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False, tickfont=dict(color='white')),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)', tickfont=dict(color='white')),
                margin=dict(l=0, r=0, t=0, b=0),
                height=250
            )
            st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})
            st.caption("实体类型分布")

        if stats["relation_types"]:
            # 关系类型统计 - 使用对应颜色
            from config import RELATION_STYLES
            types = list(stats["relation_types"].keys())
            counts = list(stats["relation_types"].values())
            colors = [RELATION_STYLES.get(t, {"color": "#888"})["color"] for t in types]

            fig = go.Figure(data=[
                go.Bar(x=types, y=counts, marker_color=colors, showlegend=False)
            ])
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False, tickfont=dict(color='white')),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)', tickfont=dict(color='white')),
                margin=dict(l=0, r=0, t=0, b=0),
                height=250
            )
            st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})

    # 数据表格（使用过滤后的数据）
    with st.expander("📋 原始数据"):
        st.subheader("节点列表")
        # 格式化节点列表，确保 name 和 description 字段正确显示
        nodes_df = pd.DataFrame(filtered_nodes)
        if not nodes_df.empty:
            # 确保 name 列存在（如果没有则从 label 复制）
            if 'name' not in nodes_df.columns and 'label' in nodes_df.columns:
                nodes_df['name'] = nodes_df['label']
            # 确保 description 列存在
            if 'description' not in nodes_df.columns:
                nodes_df['description'] = ''
            # 选择要显示的列
            display_cols = ['name', 'type', 'description', 'score', 'method']
            display_cols = [c for c in display_cols if c in nodes_df.columns]
            st.dataframe(
                nodes_df[display_cols].style.map(lambda _: 'color: #4ECDC4', subset=['type'])
            )
        else:
            st.dataframe(nodes_df)

        if filtered_edges:
            st.subheader("边列表")
            # 格式化边列表，type 列使用统一颜色
            edges_df = pd.DataFrame(filtered_edges)
            if not edges_df.empty and 'type' in edges_df.columns:
                st.dataframe(
                    edges_df.style.map(lambda _: 'color: #FFA07A', subset=['type'])
                )
            else:
                st.dataframe(edges_df)

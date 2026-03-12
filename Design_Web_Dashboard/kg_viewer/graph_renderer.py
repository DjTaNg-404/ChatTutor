"""
知识图谱查看器 - 图谱布局计算和 Plotly 渲染
"""

import networkx as nx
import plotly.graph_objects as go
import numpy as np

from config import ENTITY_TYPE_COLORS, RELATION_STYLES, get_entity_color_by_type


def calculate_graph_layout(nodes: list, edges: list, layout_method: str = "force", is_3d: bool = False) -> tuple:
    """
    计算图谱节点布局

    Args:
        nodes: 节点列表
        edges: 边列表
        layout_method: 布局方法 ("force", "circular", "spring", "random", "shell")
        is_3d: 是否使用 3D 布局

    Returns:
        包含节点坐标的字典 (2D 返回 (x,y), 3D 返回 (x,y,z))
    """
    # 构建 networkx 图
    G = nx.Graph()

    # 添加节点
    for node in nodes:
        G.add_node(
            node["id"],
            label=node["label"],
            type=node["type"],
            score=node["score"]
        )

    # 添加边
    for edge in edges:
        G.add_edge(
            edge["source"],
            edge["target"],
            type=edge.get("type", "related"),
            strength=edge.get("strength", 1.0)
        )

    # 计算布局
    if layout_method == "circular":
        if is_3d:
            pos_2d = nx.circular_layout(G)
            pos = {k: (*v, 0) for k, v in pos_2d.items()}
        else:
            pos = nx.circular_layout(G)
    elif layout_method == "shell":
        if is_3d:
            pos_2d = nx.shell_layout(G)
            pos = {k: (*v, 0) for k, v in pos_2d.items()}
        else:
            pos = nx.shell_layout(G)
    elif layout_method == "spring":
        if is_3d:
            pos = nx.spring_layout(G, dim=3, k=2, iterations=50, seed=42)
        else:
            pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
    elif layout_method == "random":
        if is_3d:
            pos = {n: (np.random.rand(3) * 2 - 1) for n in G.nodes()}
        else:
            pos = nx.random_layout(G, seed=42)
    else:  # force-directed (使用 spring 作为近似)
        if is_3d:
            pos = nx.spring_layout(G, dim=3, k=1.5, iterations=100, seed=42)
        else:
            pos = nx.spring_layout(G, k=1.5, iterations=100, seed=42)

    return pos, G


def create_plotly_figure(nodes: list, edges: list, pos: dict,
                        show_labels: bool = True,
                        node_size_factor: float = 1.0) -> go.Figure:
    """
    创建 Plotly 交互式图谱

    Args:
        nodes: 节点列表
        edges: 边列表
        pos: 节点位置字典
        show_labels: 是否显示标签
        node_size_factor: 节点大小系数

    Returns:
        Plotly Figure 对象
    """
    # 节点追踪列表
    node_x, node_y = [], []
    node_colors = []
    node_labels = []
    node_types = []
    node_scores = []

    # 构建节点 ID 到数据的映射
    node_map = {n["id"]: n for n in nodes}

    for node in nodes:
        x, y = pos.get(node["id"], (0, 0))
        node_x.append(x)
        node_y.append(y)
        # 使用大类颜色进行着色
        node_colors.append(
            get_entity_color_by_type(node["type"])
        )
        # 优先使用 name 作为标签，如果没有则使用 label
        display_label = node.get("name", node.get("label", node["id"]))
        node_labels.append(display_label)
        node_types.append(node["type"])
        node_scores.append(node["score"])

    # 创建节点散点图
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text' if show_labels else 'markers',
        hoverinfo='text',
        marker=dict(
            showscale=False,
            color=node_colors,
            size=[15 + s * 20 for s in node_scores] if node_size_factor == 1.0
                  else [15 + s * 20 * node_size_factor for s in node_scores],
            line=dict(width=2, color='white')
        ),
        text=node_labels if show_labels else None,
        textposition="top center",
        textfont=dict(size=10, color='white'),
        hovertext=[
            f"<b>{label}</b><br>类型：{ntype}<br>置信度：{score:.2f}"
            for label, ntype, score in zip(node_labels, node_types, node_scores)
        ]
    )

    # 如果有 description 字段，添加更丰富的 hover 信息
    has_descriptions = any(node_map.get(n["id"], {}).get("description") for n in nodes)
    if has_descriptions:
        node_trace.hovertemplate = (
            "<b>%{text}</b><br>"
            "类型：%{customdata[0]}<br>"
            "置信度：%{customdata[1]:.2f}<br>"
            "描述：%{customdata[2]}<extra></extra>"
        )
        node_trace.customdata = [
            [
                node_map.get(n["id"], {}).get("type", ""),
                node_map.get(n["id"], {}).get("score", 0),
                node_map.get(n["id"], {}).get("description", "无描述")
            ]
            for n in nodes
        ]

    # 创建边线 - 为每条边创建单独的 trace 以支持不同的颜色
    edge_traces = []

    for edge in edges:
        x0, y0 = pos.get(edge["source"], (0, 0))
        x1, y1 = pos.get(edge["target"], (0, 0))

        # 根据关系类型获取对应的颜色和宽度
        edge_type = edge.get("type", "related")
        style = RELATION_STYLES.get(edge_type, {"color": "#888", "width": 1})

        # 每条边单独的 trace，这样才能使用不同的颜色
        edge_trace = go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            mode='lines',
            line=dict(width=style["width"], color=style["color"]),
            hoverinfo='text',
            hovertext=edge_type,
            hovertemplate='<b>%{text}</b><extra></extra>',
            opacity=0.8
        )
        edge_traces.append(edge_trace)

    # 创建图形 - 将所有边 trace 和节点 trace 合并
    fig = go.Figure(
        data=edge_traces + [node_trace],
        layout=go.Layout(
            showlegend=False,
            hovermode='closest',
            margin=dict(b=0, l=0, r=0, t=0),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white')
        )
    )

    return fig

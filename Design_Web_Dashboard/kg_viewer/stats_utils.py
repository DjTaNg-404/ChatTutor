"""
知识图谱查看器 - 统计工具
"""


def calculate_stats(nodes: list, edges: list) -> dict:
    """计算图谱统计信息"""
    stats = {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "entity_types": {},
        "relation_types": {},
        "avg_score": 0,
        "max_score": 0,
        "min_score": float('inf') if nodes else 0
    }

    # 实体类型统计
    for node in nodes:
        etype = node["type"]
        stats["entity_types"][etype] = stats["entity_types"].get(etype, 0) + 1
        score = node["score"]
        stats["avg_score"] += score
        stats["max_score"] = max(stats["max_score"], score)
        stats["min_score"] = min(stats["min_score"], score)

    if nodes:
        stats["avg_score"] /= len(nodes)

    # 关系类型统计
    for edge in edges:
        rtype = edge.get("type", "unknown")
        stats["relation_types"][rtype] = stats["relation_types"].get(rtype, 0) + 1

    return stats


def filter_nodes_by_confidence(nodes: list, edges: list, threshold: float,
                               relation_strength_threshold: float = 0.0,
                               hide_isolated: bool = True) -> tuple:
    """
    根据置信度阈值、关系强度过滤节点和边

    Args:
        nodes: 节点列表
        edges: 边列表
        threshold: 实体置信度阈值
        relation_strength_threshold: 关系强度阈值
        hide_isolated: 是否隐藏孤立节点（没有任何连接的节点）

    Returns:
        (filtered_nodes, filtered_edges) 过滤后的节点和边
    """
    # 过滤节点：置信度
    filtered_nodes = [
        n for n in nodes
        if n.get("score", 0) >= threshold
    ]
    filtered_node_ids = {n["id"] for n in filtered_nodes}

    # 过滤边：两端节点都在过滤后 + 关系强度
    filtered_edges = [
        e for e in edges
        if e.get("source") in filtered_node_ids
        and e.get("target") in filtered_node_ids
        and e.get("strength", 1.0) >= relation_strength_threshold
    ]

    # 如果需要隐藏孤立节点，过滤出有连接的节点
    if hide_isolated:
        connected_ids = set()
        for e in filtered_edges:
            connected_ids.add(e.get("source"))
            connected_ids.add(e.get("target"))
        # 只保留有连接的节点
        filtered_nodes = [n for n in filtered_nodes if n["id"] in connected_ids]

    return filtered_nodes, filtered_edges

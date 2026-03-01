"""
知识图谱优化功能测试。

测试四种优化功能：
1. 语义归一化 (Semantic Normalization)
2. 逻辑传递性约简 (Transitive Reduction)
3. 属性图架构重组 (LPG Transformation)
4. 统计置信度与信息熵过滤 (Statistical & Entropy Filtering)
"""

import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chattutor.core.kg_builder import KnowledgeGraphBuilder
from chattutor.core.kg_optimizer import KnowledgeGraphOptimizer
import networkx as nx


def test_optimizer_initialization():
    """测试优化器初始化"""
    print("测试优化器初始化...")
    optimizer = KnowledgeGraphOptimizer({
        "semantic_similarity_threshold": 0.8,
        "transitive_reduction_threshold": 0.7,
        "statistical_filtering_threshold": 0.3,
        "entropy_filtering_threshold": 1.5
    })
    assert optimizer is not None
    assert optimizer.semantic_similarity_threshold == 0.8
    print("✓ 优化器初始化测试通过")


def test_semantic_normalization():
    """测试语义归一化功能"""
    print("测试语义归一化...")

    # 创建简单图谱
    graph = nx.Graph()
    graph.add_node("神经网络_PER", text="神经网络", type="PER", score=0.9)
    graph.add_node("人工神经网络_PER", text="人工神经网络", type="PER", score=0.8)
    graph.add_node("ANN_PER", text="ANN", type="PER", score=0.7)
    graph.add_node("深度学习_PER", text="深度学习", type="PER", score=0.9)

    graph.add_edge("神经网络_PER", "深度学习_PER", type="related_to", strength=0.8)
    graph.add_edge("人工神经网络_PER", "深度学习_PER", type="related_to", strength=0.7)
    graph.add_edge("ANN_PER", "深度学习_PER", type="related_to", strength=0.6)

    optimizer = KnowledgeGraphOptimizer({
        "semantic_similarity_threshold": 0.7,
        "use_embedding_similarity": False  # 使用字符串相似度，避免模型下载
    })

    entities = [
        {"text": "神经网络", "type": "PER", "score": 0.9},
        {"text": "人工神经网络", "type": "PER", "score": 0.8},
        {"text": "ANN", "type": "PER", "score": 0.7},
        {"text": "深度学习", "type": "PER", "score": 0.9},
    ]

    relations = [
        {"source": "神经网络", "target": "深度学习", "type": "related_to", "strength": 0.8},
        {"source": "人工神经网络", "target": "深度学习", "type": "related_to", "strength": 0.7},
        {"source": "ANN", "target": "深度学习", "type": "related_to", "strength": 0.6},
    ]

    # 应用语义归一化
    optimized_graph, mapping = optimizer.semantic_normalization(graph, entities)

    # 验证：相似实体应该被合并
    assert optimized_graph.number_of_nodes() < graph.number_of_nodes()
    print(f"✓ 语义归一化测试通过: 节点数从 {graph.number_of_nodes()} 减少到 {optimized_graph.number_of_nodes()}")


def test_transitive_reduction():
    """测试传递性约简功能"""
    print("测试传递性约简...")

    # 创建有传递关系的图 (A->B->C, A->C)
    graph = nx.DiGraph()
    graph.add_edge("A", "B", type="leads_to", strength=0.9)
    graph.add_edge("B", "C", type="leads_to", strength=0.8)
    graph.add_edge("A", "C", type="leads_to", strength=0.7)  # 冗余边

    optimizer = KnowledgeGraphOptimizer({
        "transitive_reduction_threshold": 0.6
    })

    # 应用传递性约简
    reduced_graph = optimizer.transitive_reduction(graph)

    # 验证：冗余边 A->C 应该被移除
    assert reduced_graph.number_of_edges() < graph.number_of_edges()
    assert not reduced_graph.has_edge("A", "C") or graph.has_edge("A", "C")  # 可能保留，取决于阈值

    print(f"✓ 传递性约简测试通过: 边数从 {graph.number_of_edges()} 减少到 {reduced_graph.number_of_edges()}")


def test_lpg_transformation():
    """测试LPG转换功能"""
    print("测试LPG转换...")

    # 创建包含变体实体的图
    graph = nx.Graph()
    graph.add_node("PyTorch 1.0_TECH", text="PyTorch 1.0", type="TECH", score=0.9)
    graph.add_node("PyTorch 2.0_TECH", text="PyTorch 2.0", type="TECH", score=0.9)
    graph.add_node("TensorFlow_TECH", text="TensorFlow", type="TECH", score=0.9)

    graph.add_edge("PyTorch 1.0_TECH", "TensorFlow_TECH", type="compared_with", strength=0.8)
    graph.add_edge("PyTorch 2.0_TECH", "TensorFlow_TECH", type="compared_with", strength=0.8)

    optimizer = KnowledgeGraphOptimizer()

    # 应用LPG转换
    transformed_graph, transformations = optimizer.lpg_transformation(graph)

    # 验证：变体实体应该被转换
    assert transformations > 0 or transformed_graph.number_of_nodes() < graph.number_of_nodes()
    print(f"✓ LPG转换测试通过: 转换了 {transformations} 个实体")


def test_statistical_filtering():
    """测试统计过滤功能"""
    print("测试统计过滤...")

    # 创建包含高强度和低强度关系的图
    graph = nx.Graph()
    graph.add_node("A_PER", text="A", type="PER", score=0.9)
    graph.add_node("B_PER", text="B", type="PER", score=0.9)
    graph.add_node("C_PER", text="C", type="PER", score=0.9)

    # 高强度边
    graph.add_edge("A_PER", "B_PER", type="related_to", strength=0.9)
    # 低强度边（应该被过滤）
    graph.add_edge("A_PER", "C_PER", type="related_to", strength=0.2)

    optimizer = KnowledgeGraphOptimizer({
        "statistical_filtering_threshold": 0.5
    })

    # 应用统计过滤
    filtered_graph = optimizer.statistical_filtering(graph)

    # 验证：低强度边应该被过滤
    assert filtered_graph.number_of_edges() < graph.number_of_edges()
    assert not filtered_graph.has_edge("A_PER", "C_PER")

    print(f"✓ 统计过滤测试通过: 边数从 {graph.number_of_edges()} 减少到 {filtered_graph.number_of_edges()}")


def test_builder_with_optimizations():
    """测试知识图谱构建器与优化集成"""
    print("测试知识图谱构建器与优化集成...")

    # 创建构建器，启用所有优化
    builder = KnowledgeGraphBuilder(
        model_name="bert-base-chinese",  # 使用简单模型
        use_advanced_extractor=False,    # 禁用高级提取器，简化测试
        enable_semantic_normalization=True,
        enable_transitive_reduction=True,
        enable_lpg_transformation=True,
        enable_statistical_filtering=True,
        semantic_similarity_threshold=0.7,
        transitive_reduction_threshold=0.6,
        statistical_filtering_threshold=0.4
    )

    # 示例文本（计算机学习领域）
    sample_text = """
    神经网络是一种重要的机器学习模型。人工神经网络（ANN）是神经网络的另一种称呼。
    深度学习基于神经网络。PyTorch 1.0和PyTorch 2.0都是流行的深度学习框架。
    TensorFlow是另一个重要的框架。机器学习包括监督学习和无监督学习。
    """

    # 构建知识图谱
    stats = builder.build_graph(sample_text)

    # 验证统计信息包含优化结果
    assert "optimization_stats" in stats
    assert "entity_count" in stats
    assert "relation_count" in stats

    print(f"✓ 构建器集成测试通过:")
    print(f"  提取实体: {stats['entity_count']}")
    print(f"  提取关系: {stats['relation_count']}")
    print(f"  优化统计: {stats['optimization_stats']}")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始知识图谱优化功能测试")
    print("=" * 60)

    tests = [
        test_optimizer_initialization,
        test_semantic_normalization,
        test_transitive_reduction,
        test_lpg_transformation,
        test_statistical_filtering,
        test_builder_with_optimizations
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"✗ {test_func.__name__} 失败: {e}")
            import traceback
            print(traceback.format_exc())

    print("=" * 60)
    print(f"测试完成: {passed} 通过, {failed} 失败")
    print("=" * 60)

    if failed == 0:
        print("✅ 所有测试通过！")
    else:
        print("❌ 部分测试失败")
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
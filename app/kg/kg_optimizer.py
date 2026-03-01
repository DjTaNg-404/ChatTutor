"""
知识图谱优化器模块。

提供四种知识图谱优化功能：
1. 语义归一化 (Semantic Normalization) - 消除"一义多词"，合并语义相同实体
2. 逻辑传递性约简 (Transitive Reduction) - 消除"路径冗余"，移除间接关系边
3. 属性图架构重组 (LPG Transformation) - 消除"组合爆炸"，将变体信息降级为边属性
4. 统计置信度与信息熵过滤 (Statistical & Entropy Filtering) - 消除"噪音与废话"，过滤低质量关系
"""

import re
import numpy as np
from typing import List, Dict, Any, Tuple, Set, Optional
from collections import defaultdict
import networkx as nx
import math

try:
    from sklearn.cluster import DBSCAN
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False


class KnowledgeGraphOptimizer:
    """
    知识图谱优化器，实现四种优化功能。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化优化器。

        Args:
            config: 优化配置字典，包含：
                - semantic_similarity_threshold: 语义相似度阈值 (默认: 0.8)
                - transitive_reduction_threshold: 传递性约简阈值 (默认: 0.7)
                - statistical_filtering_threshold: 统计过滤阈值 (默认: 0.3)
                - entropy_filtering_threshold: 信息熵阈值 (默认: 1.5)
                - use_embedding_similarity: 是否使用嵌入向量相似度 (默认: True)
                - embedding_model: 嵌入模型名称 (默认: "paraphrase-multilingual-MiniLM-L12-v2")
                - max_path_length: 最大路径长度 (默认: 3)
        """
        self.config = config or {}
        self.semantic_similarity_threshold = self.config.get("semantic_similarity_threshold", 0.8)
        self.transitive_reduction_threshold = self.config.get("transitive_reduction_threshold", 0.7)
        self.statistical_filtering_threshold = self.config.get("statistical_filtering_threshold", 0.3)
        self.entropy_filtering_threshold = self.config.get("entropy_filtering_threshold", 1.5)
        self.use_embedding_similarity = self.config.get("use_embedding_similarity", True)
        self.embedding_model_name = self.config.get("embedding_model", "paraphrase-multilingual-MiniLM-L12-v2")
        self.max_path_length = self.config.get("max_path_length", 3)

        self.domain_lexicon = None
        self.similarity_model = None
        self._load_dependencies()

        # 缓存
        self.similarity_cache = {}
        self.entity_embeddings = {}

    def _load_dependencies(self):
        """加载依赖的模块和模型"""
        try:
            from app.kg.domain_lexicon import DomainLexicon
            self.domain_lexicon = DomainLexicon()
        except ImportError:
            print("警告: 无法加载领域词典，语义归一化功能受限")

        # 延迟加载相似度模型
        if self.use_embedding_similarity and HAS_SENTENCE_TRANSFORMERS:
            try:
                # 实际模型加载延迟到第一次使用时
                pass
            except Exception as e:
                print(f"警告: 无法加载句子嵌入模型: {e}")
                self.use_embedding_similarity = False

    def optimize(self, graph: nx.Graph, entities: List[Dict[str, Any]],
                relations: List[Dict[str, Any]], enabled_optimizations: Dict[str, bool]) -> Tuple[nx.Graph, Dict[str, Any]]:
        """
        执行启用的优化。

        Args:
            graph: 原始知识图谱 (networkx.Graph)
            entities: 实体列表
            relations: 关系列表
            enabled_optimizations: 启用哪些优化的字典
                - semantic_normalization: 语义归一化
                - transitive_reduction: 传递性约简
                - lpg_transformation: 属性图架构重组
                - statistical_filtering: 统计过滤

        Returns:
            Tuple[优化后的图, 优化统计信息]
        """
        optimized_graph = graph.copy()
        stats = {}

        # 语义归一化
        if enabled_optimizations.get("semantic_normalization", False):
            optimized_graph, mapping = self.semantic_normalization(optimized_graph, entities)
            stats["semantic_normalization"] = {
                "entities_merged": len(mapping),
                "entity_mapping": mapping
            }

        # 传递性约简
        if enabled_optimizations.get("transitive_reduction", False):
            edge_count_before = optimized_graph.number_of_edges()
            optimized_graph = self.transitive_reduction(optimized_graph)
            stats["transitive_reduction"] = {
                "edges_removed": edge_count_before - optimized_graph.number_of_edges()
            }

        # LPG转换
        if enabled_optimizations.get("lpg_transformation", False):
            optimized_graph, transformations = self.lpg_transformation(optimized_graph)
            stats["lpg_transformation"] = {
                "entities_demoted": transformations
            }

        # 统计过滤
        if enabled_optimizations.get("statistical_filtering", False):
            edge_count_before = optimized_graph.number_of_edges()
            optimized_graph = self.statistical_filtering(optimized_graph)
            stats["statistical_filtering"] = {
                "edges_filtered": edge_count_before - optimized_graph.number_of_edges()
            }

        return optimized_graph, stats

    # ==================== 语义归一化 ====================

    def semantic_normalization(self, graph: nx.Graph, entities: List[Dict[str, Any]]) -> Tuple[nx.Graph, Dict[str, str]]:
        """
        语义归一化：合并语义相同但表达不同的实体。

        Args:
            graph: 原始图
            entities: 实体列表

        Returns:
            Tuple[优化后的图, 实体映射字典 {原始实体ID: 规范实体ID}]
        """
        print("执行语义归一化...")

        # 获取所有节点ID
        node_ids = list(graph.nodes())

        # 1. 基于领域词典的精确匹配
        exact_mapping = self._semantic_normalization_by_lexicon(node_ids)

        # 2. 基于相似度的聚类合并
        similarity_mapping = self._semantic_normalization_by_similarity(node_ids, exact_mapping)

        # 合并映射
        entity_mapping = {**exact_mapping, **similarity_mapping}

        # 3. 应用实体合并
        optimized_graph = self._apply_entity_merging(graph, entity_mapping)

        print(f"语义归一化完成: 合并了 {len(entity_mapping)} 个实体")
        return optimized_graph, entity_mapping

    def _semantic_normalization_by_lexicon(self, node_ids: List[str]) -> Dict[str, str]:
        """基于领域词典的精确匹配"""
        mapping = {}

        if self.domain_lexicon is None:
            return mapping

        for node_id in node_ids:
            # 提取实体文本（节点ID格式: "文本_类型"）
            entity_text = node_id.split("_")[0] if "_" in node_id else node_id

            # 获取规范形式
            canonical_form = self.domain_lexicon.get_canonical_form(entity_text)

            # 如果规范形式不同，则建立映射
            if canonical_form != entity_text:
                canonical_id = f"{canonical_form}_{node_id.split('_')[1]}" if "_" in node_id else canonical_form
                mapping[node_id] = canonical_id

        return mapping

    def _semantic_normalization_by_similarity(self, node_ids: List[str],
                                            existing_mapping: Dict[str, str]) -> Dict[str, str]:
        """基于相似度的聚类合并"""
        mapping = {}

        if len(node_ids) < 2:
            return mapping

        # 过滤已映射的节点
        unmapped_ids = [nid for nid in node_ids if nid not in existing_mapping]

        if len(unmapped_ids) < 2:
            return mapping

        # 提取实体文本
        entity_texts = []
        for node_id in unmapped_ids:
            entity_text = node_id.split("_")[0] if "_" in node_id else node_id
            entity_texts.append(entity_text)

        # 计算相似度矩阵（简化实现，使用字符串相似度）
        similarity_matrix = self._compute_similarity_matrix(entity_texts)

        # 聚类合并
        clusters = self._cluster_entities_by_similarity(unmapped_ids, similarity_matrix)

        # 为每个集群选择规范实体
        for cluster in clusters:
            if len(cluster) > 1:
                canonical_id = self._select_canonical_entity(cluster, graph=None)  # 简化，实际需要图信息
                for entity_id in cluster:
                    if entity_id != canonical_id:
                        mapping[entity_id] = canonical_id

        return mapping

    def _compute_similarity_matrix(self, texts: List[str]) -> np.ndarray:
        """计算文本相似度矩阵"""
        n = len(texts)
        similarity_matrix = np.eye(n)  # 对角线为1

        # 简单实现：使用字符串编辑距离
        for i in range(n):
            for j in range(i+1, n):
                # 字符串相似度（简化）
                if self.use_embedding_similarity and HAS_SENTENCE_TRANSFORMERS:
                    similarity = self._embedding_similarity(texts[i], texts[j])
                else:
                    similarity = self._string_similarity(texts[i], texts[j])

                similarity_matrix[i, j] = similarity
                similarity_matrix[j, i] = similarity

        return similarity_matrix

    def _string_similarity(self, text1: str, text2: str) -> float:
        """计算字符串相似度（基于编辑距离）"""
        import difflib
        return difflib.SequenceMatcher(None, text1, text2).ratio()

    def _embedding_similarity(self, text1: str, text2: str) -> float:
        """计算嵌入向量相似度（延迟加载模型）"""
        cache_key = (text1, text2)
        if cache_key in self.similarity_cache:
            return self.similarity_cache[cache_key]

        if self.similarity_model is None:
            try:
                self.similarity_model = SentenceTransformer(self.embedding_model_name)
            except Exception as e:
                print(f"无法加载嵌入模型: {e}")
                self.use_embedding_similarity = False
                return self._string_similarity(text1, text2)

        # 计算嵌入向量
        if text1 not in self.entity_embeddings:
            self.entity_embeddings[text1] = self.similarity_model.encode(text1)
        if text2 not in self.entity_embeddings:
            self.entity_embeddings[text2] = self.similarity_model.encode(text2)

        # 计算余弦相似度
        emb1 = self.entity_embeddings[text1]
        emb2 = self.entity_embeddings[text2]
        similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))

        self.similarity_cache[cache_key] = similarity
        return similarity

    def _cluster_entities_by_similarity(self, node_ids: List[str],
                                      similarity_matrix: np.ndarray) -> List[List[str]]:
        """基于相似度矩阵聚类实体"""
        clusters = []

        if not HAS_SKLEARN or len(node_ids) < 2:
            # 回退到简单阈值聚类
            return self._simple_threshold_clustering(node_ids, similarity_matrix)

        try:
            # 使用DBSCAN聚类
            clustering = DBSCAN(eps=self.semantic_similarity_threshold,
                              min_samples=1,
                              metric="precomputed").fit(1 - similarity_matrix)

            # 分组聚类结果
            labels = clustering.labels_
            n_clusters = max(labels) + 1 if len(set(labels)) > 1 else 1

            for i in range(n_clusters):
                cluster_indices = np.where(labels == i)[0]
                cluster = [node_ids[idx] for idx in cluster_indices]
                clusters.append(cluster)

        except Exception as e:
            print(f"DBSCAN聚类失败: {e}")
            clusters = self._simple_threshold_clustering(node_ids, similarity_matrix)

        return clusters

    def _simple_threshold_clustering(self, node_ids: List[str],
                                   similarity_matrix: np.ndarray) -> List[List[str]]:
        """简单阈值聚类（DBSCAN不可用时使用）"""
        clusters = []
        assigned = set()

        for i, node_id in enumerate(node_ids):
            if node_id in assigned:
                continue

            cluster = [node_id]
            assigned.add(node_id)

            for j, other_id in enumerate(node_ids):
                if i != j and other_id not in assigned:
                    if similarity_matrix[i, j] >= self.semantic_similarity_threshold:
                        cluster.append(other_id)
                        assigned.add(other_id)

            clusters.append(cluster)

        return clusters

    def _select_canonical_entity(self, cluster: List[str], graph: Optional[nx.Graph] = None) -> str:
        """为实体集群选择规范实体"""
        # 简单策略：选择最长的实体文本
        if graph is None:
            # 没有图信息时，选择最长的实体名
            return max(cluster, key=lambda x: len(x.split("_")[0]))

        # 有图信息时，考虑度中心性和置信度
        best_entity = cluster[0]
        best_score = 0

        for entity_id in cluster:
            # 提取实体文本和类型
            parts = entity_id.split("_")
            entity_text = parts[0]
            entity_type = parts[1] if len(parts) > 1 else "UNKNOWN"

            # 评分因素：度中心性、置信度、长度、是否在领域词典中
            degree = graph.degree(entity_id) if entity_id in graph else 0
            confidence = graph.nodes[entity_id].get("score", 0.5) if entity_id in graph.nodes else 0.5

            lexicon_score = 1.0 if (self.domain_lexicon and
                                  self.domain_lexicon.is_domain_term(entity_text)) else 0.5

            score = (0.3 * degree + 0.4 * confidence + 0.2 * len(entity_text) + 0.1 * lexicon_score)

            if score > best_score:
                best_score = score
                best_entity = entity_id

        return best_entity

    def _apply_entity_merging(self, graph: nx.Graph, entity_mapping: Dict[str, str]) -> nx.Graph:
        """应用实体合并到图中"""
        if not entity_mapping:
            return graph

        optimized_graph = nx.Graph()

        # 1. 添加所有节点（映射后的）
        for node_id, data in graph.nodes(data=True):
            if node_id in entity_mapping:
                target_id = entity_mapping[node_id]
                # 如果目标节点不存在，创建它
                if target_id not in optimized_graph:
                    # 合并节点属性（取平均值）
                    optimized_graph.add_node(target_id, **data)
                else:
                    # 更新现有节点属性（合并）
                    self._merge_node_attributes(optimized_graph.nodes[target_id], data)
            else:
                optimized_graph.add_node(node_id, **data)

        # 2. 添加所有边（更新节点ID）
        for u, v, data in graph.edges(data=True):
            source = entity_mapping.get(u, u)
            target = entity_mapping.get(v, v)

            # 避免自环
            if source == target:
                continue

            # 如果边已存在，合并属性
            if optimized_graph.has_edge(source, target):
                self._merge_edge_attributes(optimized_graph[source][target], data)
            else:
                optimized_graph.add_edge(source, target, **data)

        return optimized_graph

    def _merge_node_attributes(self, target_attrs: Dict[str, Any], source_attrs: Dict[str, Any]):
        """合并节点属性"""
        # 对于数值属性取平均值
        for key, value in source_attrs.items():
            if key in target_attrs and isinstance(value, (int, float)):
                if isinstance(target_attrs[key], (int, float)):
                    target_attrs[key] = (target_attrs[key] + value) / 2
            else:
                target_attrs[key] = value

    def _merge_edge_attributes(self, target_attrs: Dict[str, Any], source_attrs: Dict[str, Any]):
        """合并边属性"""
        # 对于强度取最大值
        if "strength" in source_attrs and "strength" in target_attrs:
            target_attrs["strength"] = max(target_attrs["strength"], source_attrs["strength"])

        # 合并上下文
        if "context" in source_attrs:
            if "context" in target_attrs:
                # 保留较长的上下文
                if len(source_attrs["context"]) > len(target_attrs["context"]):
                    target_attrs["context"] = source_attrs["context"]
            else:
                target_attrs["context"] = source_attrs["context"]

        # 合并其他属性
        for key, value in source_attrs.items():
            if key not in ["strength", "context"]:
                target_attrs[key] = value

    # ==================== 逻辑传递性约简 ====================

    def transitive_reduction(self, graph: nx.Graph) -> nx.Graph:
        """
        逻辑传递性约简：移除冗余的间接关系边。

        对于三元组 (A→B, B→C, A→C)，如果 A→C 可通过 A→B→C 推导，
        且间接路径强度 ≥ 直接关系强度 × threshold，则移除 A→C。

        Args:
            graph: 原始图

        Returns:
            约简后的图
        """
        print("执行逻辑传递性约简...")

        if graph.number_of_edges() < 2:
            return graph

        optimized_graph = graph.copy()

        # 按关系类型分组处理
        relation_types = self._extract_relation_types(optimized_graph)

        for rel_type in relation_types:
            # 提取该关系类型的子图
            subgraph = self._extract_subgraph_by_type(optimized_graph, rel_type)

            if subgraph.number_of_edges() < 2:
                continue

            # 对有向无环图使用标准算法
            if nx.is_directed_acyclic_graph(subgraph):
                reduced_subgraph = self._transitive_reduction_dag(subgraph)
            else:
                # 对有环图使用启发式算法
                reduced_subgraph = self._transitive_reduction_heuristic(subgraph)

            # 将约简后的子图合并回原图
            optimized_graph = self._merge_reduced_subgraph(optimized_graph, reduced_subgraph, rel_type)

        print(f"传递性约简完成: 移除了 {graph.number_of_edges() - optimized_graph.number_of_edges()} 条边")
        return optimized_graph

    def _extract_relation_types(self, graph: nx.Graph) -> Set[str]:
        """提取图中所有的关系类型"""
        relation_types = set()
        for _, _, data in graph.edges(data=True):
            rel_type = data.get("type", "related_to")
            relation_types.add(rel_type)
        return relation_types

    def _extract_subgraph_by_type(self, graph: nx.Graph, rel_type: str) -> nx.DiGraph:
        """提取指定关系类型的子图（有向）"""
        subgraph = nx.DiGraph()

        for u, v, data in graph.edges(data=True):
            if data.get("type", "related_to") == rel_type:
                subgraph.add_edge(u, v, **data)

        return subgraph

    def _transitive_reduction_dag(self, dag: nx.DiGraph) -> nx.DiGraph:
        """对有向无环图进行传递性约简"""
        try:
            # 使用networkx的传递性约简算法
            reduced_dag = nx.algorithms.dag.transitive_reduction(dag)

            # 恢复边属性（强度取原值）
            for u, v in reduced_dag.edges():
                if dag.has_edge(u, v):
                    reduced_dag[u][v].update(dag[u][v])

            return reduced_dag
        except Exception as e:
            print(f"DAG传递性约简失败: {e}")
            return dag

    def _transitive_reduction_heuristic(self, graph: nx.DiGraph) -> nx.DiGraph:
        """对有环图进行启发式传递性约简"""
        reduced_graph = graph.copy()
        removed_edges = set()

        # 计算所有节点对之间的最短路径（考虑强度）
        for source in graph.nodes():
            for target in graph.nodes():
                if source == target:
                    continue

                # 检查是否存在直接边
                if graph.has_edge(source, target):
                    direct_strength = graph[source][target].get("strength", 1.0)

                    # 查找间接路径
                    indirect_paths = self._find_indirect_paths(graph, source, target,
                                                             max_length=self.max_path_length)

                    # 计算间接路径的最大强度
                    max_indirect_strength = 0
                    for path in indirect_paths:
                        path_strength = self._calculate_path_strength(graph, path)
                        max_indirect_strength = max(max_indirect_strength, path_strength)

                    # 判断是否移除直接边
                    if (max_indirect_strength > 0 and
                        max_indirect_strength >= direct_strength * self.transitive_reduction_threshold):
                        removed_edges.add((source, target))

        # 移除冗余边
        for u, v in removed_edges:
            if reduced_graph.has_edge(u, v):
                reduced_graph.remove_edge(u, v)

        return reduced_graph

    def _find_indirect_paths(self, graph: nx.DiGraph, source: str, target: str,
                           max_length: int = 3) -> List[List[str]]:
        """查找间接路径（排除直接边）"""
        paths = []

        # 临时移除直接边以查找间接路径
        has_direct_edge = graph.has_edge(source, target)
        if has_direct_edge:
            direct_edge_data = graph[source][target]
            graph.remove_edge(source, target)

        try:
            # 查找所有简单路径
            for path in nx.all_simple_paths(graph, source, target, cutoff=max_length):
                if len(path) > 2:  # 至少包含一个中间节点
                    paths.append(path)
        except Exception:
            pass

        # 恢复直接边
        if has_direct_edge:
            graph.add_edge(source, target, **direct_edge_data)

        return paths

    def _calculate_path_strength(self, graph: nx.DiGraph, path: List[str]) -> float:
        """计算路径的强度（几何平均）"""
        if len(path) < 2:
            return 0

        strengths = []
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            if graph.has_edge(u, v):
                strength = graph[u][v].get("strength", 1.0)
                strengths.append(strength)

        if not strengths:
            return 0

        # 几何平均
        product = 1.0
        for strength in strengths:
            product *= strength

        return product ** (1.0 / len(strengths))

    def _merge_reduced_subgraph(self, original_graph: nx.Graph, reduced_subgraph: nx.DiGraph,
                              rel_type: str) -> nx.Graph:
        """将约简后的子图合并回原图"""
        result_graph = original_graph.copy()

        # 移除该关系类型的所有边
        edges_to_remove = []
        for u, v, data in result_graph.edges(data=True):
            if data.get("type", "related_to") == rel_type:
                edges_to_remove.append((u, v))

        for u, v in edges_to_remove:
            result_graph.remove_edge(u, v)

        # 添加约简后的边
        for u, v, data in reduced_subgraph.edges(data=True):
            result_graph.add_edge(u, v, **data)

        return result_graph

    # ==================== 属性图架构重组 (LPG转换) ====================

    def lpg_transformation(self, graph: nx.Graph) -> Tuple[nx.Graph, int]:
        """
        属性图架构重组：将变体信息降级为边属性。

        识别模式：
        1. 版本模式: "实体名 版本号" -> 核心实体 + version属性
        2. 环境模式: "实体名 环境后缀" -> 核心实体 + environment属性
        3. 变体模式: "基础概念 修饰词" -> 核心概念 + variant属性

        Args:
            graph: 原始图

        Returns:
            Tuple[转换后的图, 转换的实体数量]
        """
        print("执行属性图架构重组 (LPG转换)...")

        optimized_graph = graph.copy()
        transformations = 0

        # 识别变体实体
        variant_entities = self._identify_variant_entities(optimized_graph)

        # 为每个变体组执行转换
        for core_entity, variants in variant_entities.items():
            if not variants:
                continue

            # 执行转换
            optimized_graph, transformed = self._transform_variant_group(
                optimized_graph, core_entity, variants
            )
            transformations += transformed

        print(f"LPG转换完成: 转换了 {transformations} 个实体")
        return optimized_graph, transformations

    def _identify_variant_entities(self, graph: nx.Graph) -> Dict[str, List[str]]:
        """识别变体实体"""
        variant_groups = defaultdict(list)

        # 正则表达式模式
        version_pattern = r'^(.*?)\s+(\d+\.\d+|\d+)$'  # 版本号
        environment_patterns = [
            r'^(.*?)\s+(GPU|CPU|TPU)$',  # 硬件环境
            r'^(.*?)\s+(Linux|Windows|macOS)$',  # 操作系统
        ]

        for node_id in graph.nodes():
            # 提取实体文本
            parts = node_id.split("_")
            entity_text = parts[0]
            entity_type = parts[1] if len(parts) > 1 else "UNKNOWN"

            # 检查版本模式
            version_match = re.match(version_pattern, entity_text)
            if version_match:
                core_text = version_match.group(1)
                version = version_match.group(2)
                core_id = f"{core_text}_{entity_type}"
                variant_groups[core_id].append((node_id, "version", version))
                continue

            # 检查环境模式
            for pattern in environment_patterns:
                env_match = re.match(pattern, entity_text)
                if env_match:
                    core_text = env_match.group(1)
                    environment = env_match.group(2)
                    core_id = f"{core_text}_{entity_type}"
                    variant_groups[core_id].append((node_id, "environment", environment))
                    break

        # 简化数据结构
        result = {}
        for core_id, variants in variant_groups.items():
            result[core_id] = [v[0] for v in variants]  # 只保留节点ID

        return result

    def _transform_variant_group(self, graph: nx.Graph, core_entity: str,
                               variants: List[str]) -> Tuple[nx.Graph, int]:
        """转换一个变体组"""
        transformed = 0

        # 确保核心实体存在
        if core_entity not in graph:
            # 创建核心实体（使用第一个变体的属性）
            first_variant = variants[0]
            if first_variant in graph.nodes():
                core_attrs = dict(graph.nodes[first_variant])
                # 移除变体特定信息
                core_attrs["text"] = core_entity.split("_")[0]
                graph.add_node(core_entity, **core_attrs)

        # 处理每个变体
        for variant_id in variants:
            if variant_id not in graph.nodes():
                continue

            # 获取变体属性
            variant_text = variant_id.split("_")[0]
            variant_type = variant_id.split("_")[1] if "_" in variant_id else "UNKNOWN"

            # 分析变体信息
            attributes = self._analyze_variant_attributes(variant_text, core_entity.split("_")[0])

            # 重定向边：将连接到变体的边重定向到核心实体，并添加属性
            self._redirect_edges_to_core(graph, variant_id, core_entity, attributes)

            # 移除变体实体
            graph.remove_node(variant_id)
            transformed += 1

        return graph, transformed

    def _analyze_variant_attributes(self, variant_text: str, core_text: str) -> Dict[str, str]:
        """分析变体属性"""
        attributes = {}

        # 版本属性
        version_match = re.match(r'^(.*?)\s+(\d+\.\d+|\d+)$', variant_text)
        if version_match and version_match.group(1) == core_text:
            attributes["version"] = version_match.group(2)

        # 环境属性
        env_patterns = [
            (r'^(.*?)\s+(GPU|CPU|TPU)$', "environment"),
            (r'^(.*?)\s+(Linux|Windows|macOS)$', "os"),
        ]

        for pattern, attr_name in env_patterns:
            env_match = re.match(pattern, variant_text)
            if env_match and env_match.group(1) == core_text:
                attributes[attr_name] = env_match.group(2)
                break

        # 变体类型
        if "变体" in variant_text or "variant" in variant_text.lower():
            attributes["variant_type"] = "variant"

        return attributes

    def _redirect_edges_to_core(self, graph: nx.Graph, variant_id: str,
                              core_entity: str, attributes: Dict[str, str]):
        """将连接到变体的边重定向到核心实体，并添加属性"""
        # 获取所有连接到变体的边
        edges_to_redirect = []
        for neighbor in list(graph.neighbors(variant_id)):
            edge_data = graph[variant_id][neighbor]
            edges_to_redirect.append((neighbor, dict(edge_data)))

        # 移除连接到变体的边
        for neighbor in list(graph.neighbors(variant_id)):
            graph.remove_edge(variant_id, neighbor)

        # 添加重定向的边（带有属性）
        for neighbor, edge_data in edges_to_redirect:
            # 添加变体属性
            edge_data["attributes"] = {**edge_data.get("attributes", {}), **attributes}

            # 添加边（如果不存在）
            if not graph.has_edge(core_entity, neighbor):
                graph.add_edge(core_entity, neighbor, **edge_data)
            else:
                # 合并边属性
                self._merge_edge_attributes(graph[core_entity][neighbor], edge_data)

    # ==================== 统计置信度与信息熵过滤 ====================

    def statistical_filtering(self, graph: nx.Graph) -> nx.Graph:
        """
        统计置信度与信息熵过滤：移除低质量关系。

        综合评分 = 0.4×置信度 + 0.3×信息熵 + 0.3×结构重要性
        过滤掉综合评分 < statistical_filtering_threshold 的关系。

        Args:
            graph: 原始图

        Returns:
            过滤后的图
        """
        print("执行统计置信度与信息熵过滤...")

        if graph.number_of_edges() == 0:
            return graph

        # 计算关系类型分布（用于信息熵）
        relation_type_distribution = self._calculate_relation_type_distribution(graph)

        # 计算结构重要性（PageRank）
        node_importance = self._calculate_node_importance(graph)

        # 计算每条边的综合评分
        edge_scores = {}
        for u, v, data in graph.edges(data=True):
            # 置信度评分
            confidence_score = data.get("strength", 0.5)

            # 信息熵评分
            rel_type = data.get("type", "related_to")
            entropy_score = self._calculate_entropy_score(rel_type, relation_type_distribution)

            # 结构重要性评分
            importance_score = (node_importance.get(u, 0.5) + node_importance.get(v, 0.5)) / 2

            # 综合评分
            composite_score = (
                0.4 * confidence_score +
                0.3 * entropy_score +
                0.3 * importance_score
            )

            edge_scores[(u, v)] = composite_score

        # 过滤低评分边
        optimized_graph = graph.copy()
        edges_to_remove = []

        for (u, v), score in edge_scores.items():
            if score < self.statistical_filtering_threshold:
                edges_to_remove.append((u, v))

        # 移除低质量边
        for u, v in edges_to_remove:
            if optimized_graph.has_edge(u, v):
                optimized_graph.remove_edge(u, v)

        print(f"统计过滤完成: 移除了 {len(edges_to_remove)} 条边")
        return optimized_graph

    def _calculate_relation_type_distribution(self, graph: nx.Graph) -> Dict[str, float]:
        """计算关系类型分布"""
        type_counts = defaultdict(int)
        total_edges = graph.number_of_edges()

        if total_edges == 0:
            return {}

        for _, _, data in graph.edges(data=True):
            rel_type = data.get("type", "related_to")
            type_counts[rel_type] += 1

        # 计算概率分布
        distribution = {}
        for rel_type, count in type_counts.items():
            distribution[rel_type] = count / total_edges

        return distribution

    def _calculate_entropy_score(self, rel_type: str, distribution: Dict[str, float]) -> float:
        """计算信息熵评分"""
        if not distribution:
            return 0.5

        # 该关系类型的概率
        p = distribution.get(rel_type, 0)

        if p == 0:
            # 罕见关系类型，给予较高熵评分
            return 0.8

        # 计算信息熵: H = -p * log(p)
        entropy = -p * math.log(p) if p > 0 else 0

        # 归一化到 [0, 1] 范围
        max_entropy = - (1/len(distribution)) * math.log(1/len(distribution)) if len(distribution) > 0 else 1
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0

        return normalized_entropy

    def _calculate_node_importance(self, graph: nx.Graph) -> Dict[str, float]:
        """计算节点重要性（使用PageRank）"""
        if graph.number_of_nodes() == 0:
            return {}

        try:
            # 计算PageRank
            pagerank = nx.pagerank(graph, alpha=0.85)

            # 归一化到 [0, 1] 范围
            max_pr = max(pagerank.values()) if pagerank.values() else 1
            min_pr = min(pagerank.values()) if pagerank.values() else 0

            if max_pr == min_pr:
                normalized_pr = {node: 0.5 for node in pagerank}
            else:
                normalized_pr = {}
                for node, pr in pagerank.items():
                    normalized_pr[node] = (pr - min_pr) / (max_pr - min_pr)

            return normalized_pr
        except Exception as e:
            print(f"PageRank计算失败: {e}")
            # 回退到度中心性
            return self._calculate_degree_centrality(graph)

    def _calculate_degree_centrality(self, graph: nx.Graph) -> Dict[str, float]:
        """计算度中心性（PageRank失败时使用）"""
        if graph.number_of_nodes() == 0:
            return {}

        degrees = dict(graph.degree())
        max_degree = max(degrees.values()) if degrees.values() else 1
        min_degree = min(degrees.values()) if degrees.values() else 0

        if max_degree == min_degree:
            normalized_degrees = {node: 0.5 for node in degrees}
        else:
            normalized_degrees = {}
            for node, degree in degrees.items():
                normalized_degrees[node] = (degree - min_degree) / (max_degree - min_degree)

        return normalized_degrees
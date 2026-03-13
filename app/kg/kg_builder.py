"""
知识图谱构建模块。

提供从文本中提取实体、关系和构建可视化知识图谱的功能。
"""

import json
import os
from typing import List, Dict, Any, Tuple, Optional
import networkx as nx
from collections import defaultdict
import numpy as np
import re

try:
    from app.kg.kg_extractor import KGEntityExtractor
    HAS_ADVANCED_EXTRACTOR = True
except ImportError:
    HAS_ADVANCED_EXTRACTOR = False

# 尝试导入 DeepSeek LLM 提取器
try:
    from app.kg.deepseek_extractor import DeepSeekKGExtractor
    HAS_DEEPSEEK_EXTRACTOR = True
except ImportError:
    HAS_DEEPSEEK_EXTRACTOR = False


class KnowledgeGraphBuilder:
    """
    知识图谱构建器，从文本中提取实体和关系，构建知识图谱。
    """

    def __init__(
        self,
        model_name: str = "ckiplab/bert-base-chinese-ner",
        min_confidence: float = 0.5,
        min_entity_length: int = 2,
        merge_adjacent: bool = True,
        use_advanced_extractor: bool = True,
        use_keybert: bool = True,
        use_spacy: bool = True,
        use_lexicon: bool = True,
        # DeepSeek 配置
        use_deepseek: bool = True,              # 默认使用 DeepSeek LLM
        deepseek_model: str = "deepseek-chat",
        deepseek_api_key: Optional[str] = None,
        # 优化参数（默认禁用以保持向后兼容性）
        enable_semantic_normalization: bool = False,
        enable_transitive_reduction: bool = False,
        enable_lpg_transformation: bool = False,
        enable_statistical_filtering: bool = False,
        semantic_similarity_threshold: float = 0.8,
        transitive_reduction_threshold: float = 0.7,
        statistical_filtering_threshold: float = 0.3,
        entropy_filtering_threshold: float = 1.5
    ):
        """
        初始化知识图谱构建器。

        Args:
            model_name: 用于NER的预训练模型名称（推荐使用专门的中文NER模型）
            min_confidence: 实体置信度阈值，低于此值的实体将被过滤
            min_entity_length: 最小实体长度（字符数），短于此长度的实体将被过滤
            merge_adjacent: 是否合并相邻的相同类型实体
            use_advanced_extractor: 是否使用高级提取器（整合NER、KeyBERT、spaCy、领域词典）
            use_keybert: 是否使用KeyBERT提取关键词
            use_spacy: 是否使用spaCy提取名词短语
            use_lexicon: 是否使用领域词典匹配
            enable_semantic_normalization: 是否启用语义归一化（消除"一义多词"）
            enable_transitive_reduction: 是否启用逻辑传递性约简（消除"路径冗余"）
            enable_lpg_transformation: 是否启用属性图架构重组（消除"组合爆炸"）
            enable_statistical_filtering: 是否启用统计置信度与信息熵过滤（消除"噪音与废话"）
            semantic_similarity_threshold: 语义相似度阈值（0.0-1.0），越高越严格
            transitive_reduction_threshold: 传递性约简阈值（0.0-1.0），关系强度低于此值可能被间接关系替代
            statistical_filtering_threshold: 统计过滤阈值（0.0-1.0），关系强度低于此值被过滤
            entropy_filtering_threshold: 信息熵阈值，关系信息熵低于此值被过滤
        """
        self.model_name = model_name
        self.min_confidence = min_confidence
        self.min_entity_length = min_entity_length
        self.merge_adjacent = merge_adjacent
        self.use_advanced_extractor = use_advanced_extractor
        self.use_keybert = use_keybert
        self.use_spacy = use_spacy
        self.use_lexicon = use_lexicon
        # DeepSeek 配置
        self.use_deepseek = use_deepseek
        self.deepseek_model = deepseek_model
        self.deepseek_api_key = deepseek_api_key
        self.deepseek_extractor = None
        # 优化参数
        self.enable_semantic_normalization = enable_semantic_normalization
        self.enable_transitive_reduction = enable_transitive_reduction
        self.enable_lpg_transformation = enable_lpg_transformation
        self.enable_statistical_filtering = enable_statistical_filtering
        self.semantic_similarity_threshold = semantic_similarity_threshold
        self.transitive_reduction_threshold = transitive_reduction_threshold
        self.statistical_filtering_threshold = statistical_filtering_threshold
        self.entropy_filtering_threshold = entropy_filtering_threshold
        self.ner_pipeline = None
        self.advanced_extractor = None
        self.graph = nx.Graph()
        self.entities = {}  # 实体ID到实体的映射
        self.relations = []  # 关系列表

    def load_models(self):
        """加载必要的NLP模型（延迟加载）"""
        try:
            from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification
            import torch

            # 加载NER模型，添加重试逻辑
            max_retries = 2
            for retry in range(max_retries):
                try:
                    print(f"正在加载NER模型: {self.model_name}...")
                    self.ner_pipeline = pipeline(
                        "ner",
                        model=self.model_name,
                        tokenizer=self.model_name,
                        aggregation_strategy="simple"
                    )
                    print("NER模型加载完成")
                    break  # 成功则跳出重试循环
                except RuntimeError as e:
                    if "client has been closed" in str(e):
                        print(f"警告: HTTP客户端错误 (尝试 {retry+1}/{max_retries}) - {e}")
                        if retry < max_retries - 1:
                            print("等待后重试...")
                            import time
                            time.sleep(1)  # 等待1秒后重试
                            continue
                        else:
                            print("NER模型加载失败")
                            raise
                    else:
                        # 其他RuntimeError
                        raise
                except Exception as e:
                    # 其他异常直接抛出
                    raise
            else:
                # 循环正常结束（所有重试都失败）
                print("NER模型加载失败")
                raise RuntimeError("NER模型加载失败，所有重试都未成功")
        except ImportError as e:
            print(f"错误: 缺少依赖 - {e}")
            print("请安装: pip install transformers torch")
            raise

    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        从文本中提取命名实体。

        Args:
            text: 输入文本

        Returns:
            实体列表，每个实体包含文本、类型、位置等信息
        """
        # 根据设置选择提取方法
        # 优先使用 DeepSeek LLM（如果启用）
        print(f"[DEBUG] extract_entities: use_deepseek={self.use_deepseek}, HAS_DEEPSEEK_EXTRACTOR={HAS_DEEPSEEK_EXTRACTOR}, use_advanced_extractor={self.use_advanced_extractor}")
        if self.use_deepseek and HAS_DEEPSEEK_EXTRACTOR:
            print("[DEBUG] 使用 DeepSeek 提取实体")
            return self._extract_entities_deepseek(text)
        elif self.use_advanced_extractor and HAS_ADVANCED_EXTRACTOR:
            print("[DEBUG] 使用高级提取器提取实体")
            # 延迟加载模型
            return self._extract_entities_advanced(text)
        else:
            print("[DEBUG] 使用 NER 提取实体")
            # 延迟加载模型
            return self._extract_entities_ner(text)

    def _extract_entities_deepseek(self, text: str) -> List[Dict[str, Any]]:
        """
        使用 DeepSeek LLM 提取实体。
        """
        if self.deepseek_extractor is None:
            self._load_deepseek_extractor()

        if self.deepseek_extractor is None:
            print("警告：DeepSeek 提取器加载失败，回退到 NER 方法")
            return self._extract_entities_ner(text)

        try:
            # 使用 DeepSeek 提取器提取所有实体和关系
            print("[DEBUG] 正在调用 DeepSeek API 提取实体...")
            result = self.deepseek_extractor.extract_entities_and_relations(text)

            # 保存 DeepSeek 返回的关系供后续使用
            self._deepseek_relations = result.get("relations", [])
            print(f"[DEBUG] DeepSeek 返回 {len(self._deepseek_relations)} 个关系")

            # 转换为与旧格式兼容的格式
            formatted_entities = []
            for entity in result.get("entities", []):
                formatted_entities.append({
                    "text": entity.get("text", ""),
                    "type": entity.get("type", "MISC"),
                    "start": entity.get("start", 0),
                    "end": entity.get("end", len(entity.get("text", ""))),
                    "score": entity.get("score", entity.get("confidence", 0.8)),
                    "method": "DeepSeek"
                })

            if not formatted_entities:
                print("[DEBUG] DeepSeek 返回空结果，回退到高级提取器")
                return self._extract_entities_advanced(text)

            print(f"[DEBUG] DeepSeek 提取成功：{len(formatted_entities)} 个实体")
            return formatted_entities

        except Exception as e:
            print(f"[DEBUG] DeepSeek 提取失败：{e}，回退到高级提取器")
            return self._extract_entities_advanced(text)

    def _extract_entities_advanced(self, text: str) -> List[Dict[str, Any]]:
        """
        使用高级提取器（整合多种方法）提取实体。
        """
        if self.advanced_extractor is None:
            self._load_advanced_extractor()

        if self.advanced_extractor is None:
            print("警告：高级提取器加载失败，回退到 NER 方法")
            return self._extract_entities_ner(text)

        # 使用高级提取器提取所有实体
        entities = self.advanced_extractor.extract_all_entities(text)

        # 转换为与旧格式兼容的格式
        formatted_entities = []
        for entity in entities:
            formatted_entities.append({
                "text": entity["text"],
                "type": entity["type"],
                "start": entity.get("start", 0),
                "end": entity.get("end", len(entity["text"])),
                "score": entity["score"],
                "method": entity.get("method", "ADVANCED")
            })

        return formatted_entities

    def _load_deepseek_extractor(self):
        """
        加载 DeepSeek LLM 提取器。
        """
        try:
            if HAS_DEEPSEEK_EXTRACTOR:
                self.deepseek_extractor = DeepSeekKGExtractor(
                    api_key=self.deepseek_api_key,
                    model=self.deepseek_model
                )
                print(f"DeepSeek 提取器已初始化 (model: {self.deepseek_model})")
            else:
                print("警告：DeepSeek 提取器不可用，请安装所需依赖")
        except Exception as e:
            print(f"加载 DeepSeek 提取器失败：{e}")
            self.deepseek_extractor = None

    def _extract_entities_ner(self, text: str) -> List[Dict[str, Any]]:
        """
        使用传统的NER方法提取实体。
        """
        if self.ner_pipeline is None:
            self.load_models()

        # 预处理文本：清理空白字符和特殊格式
        cleaned_text = self._preprocess_text(text)

        # 如果文本太长，分段处理
        max_length = 512
        if len(cleaned_text) > max_length * 0.9:  # 留一些余量
            chunks = [cleaned_text[i:i+max_length] for i in range(0, len(cleaned_text), max_length)]
            all_entities = []
            for chunk in chunks:
                entities = self.ner_pipeline(chunk)
                all_entities.extend(entities)
        else:
            entities = self.ner_pipeline(cleaned_text)

        # 格式化实体信息并应用后处理
        formatted_entities = self._format_and_filter_entities(entities, cleaned_text)

        return formatted_entities

    def _extract_entities_advanced(self, text: str) -> List[Dict[str, Any]]:
        """
        使用高级提取器（整合多种方法）提取实体。
        """
        if self.advanced_extractor is None:
            self._load_advanced_extractor()

        if self.advanced_extractor is None:
            print("警告: 高级提取器加载失败，回退到NER方法")
            return self._extract_entities_ner(text)

        # 使用高级提取器提取所有实体
        entities = self.advanced_extractor.extract_all_entities(text)

        # 转换为与旧格式兼容的格式
        formatted_entities = []
        for entity in entities:
            formatted_entities.append({
                "text": entity["text"],
                "type": entity["type"],
                "start": entity.get("start", 0),
                "end": entity.get("end", len(entity["text"])),
                "score": entity["score"],
                "method": entity.get("method", "ADVANCED")
            })

        return formatted_entities

    def _load_advanced_extractor(self):
        """
        加载高级提取器。
        """
        try:
            if HAS_ADVANCED_EXTRACTOR:
                self.advanced_extractor = KGEntityExtractor(
                    model_name=self.model_name,
                    min_confidence=self.min_confidence,
                    min_entity_length=self.min_entity_length,
                    use_keybert=self.use_keybert,
                    use_spacy=self.use_spacy,
                    use_lexicon=self.use_lexicon
                )
                print("高级实体提取器已初始化")
            else:
                print("警告: 高级提取器不可用，请安装所需依赖")
        except Exception as e:
            print(f"加载高级提取器失败: {e}")
            self.advanced_extractor = None

    def _preprocess_text(self, text: str) -> str:
        """
        预处理文本：清理PDF提取的常见问题。

        Args:
            text: 原始文本

        Returns:
            清理后的文本
        """
        if not text:
            return text

        # 1. 替换多个连续空白字符为单个空格
        import re
        text = re.sub(r'\s+', ' ', text)

        # 2. 移除PDF中常见的无意义字符和乱码
        # 常见乱码模式：控制字符、特殊符号等
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

        # 3. 清理行尾的连字符（PDF换行导致的）
        text = re.sub(r'-\s*\n\s*', '', text)

        # 4. 合并被错误分割的单词
        text = re.sub(r'\s*-\s*', '', text)  # 移除连字符周围的空格

        # 5. 标准化标点符号
        text = re.sub(r'[。，；：？！、]', lambda m: {'。': '.', '，': ',', '；': ';', '：': ':', '？': '?', '！': '!', '、': ','}[m.group()], text)

        return text.strip()

    def _format_and_filter_entities(self, raw_entities: List[Dict[str, Any]], text: str) -> List[Dict[str, Any]]:
        """
        格式化实体并应用过滤规则。

        Args:
            raw_entities: 原始NER模型输出
            text: 原始文本（用于验证实体位置）

        Returns:
            过滤和格式化后的实体列表
        """
        if not raw_entities:
            return []

        formatted_entities = []
        for entity in raw_entities:
            # 获取实体信息
            entity_text = entity.get("word", "").strip()
            entity_type = entity.get("entity_group", "")
            entity_score = float(entity.get("score", 0))
            start = int(entity.get("start", 0))
            end = int(entity.get("end", 0))

            # 1. 映射实体类型（如果模型输出数字标签）
            mapped_type = self._map_entity_type(entity_type)

            # 2. 置信度过滤
            if entity_score < self.min_confidence:
                continue

            # 3. 长度过滤
            if len(entity_text) < self.min_entity_length:
                continue

            # 4. 内容过滤：移除无意义的实体（纯数字、单个字符等）
            if self._is_meaningless_entity(entity_text, mapped_type):
                continue

            # 5. 验证实体文本是否与原始文本匹配
            if start < len(text) and end <= len(text):
                actual_text = text[start:end]
                if actual_text != entity_text:
                    # 如果模型返回的文本与原始文本不匹配，使用原始文本
                    entity_text = actual_text

            formatted_entities.append({
                "text": entity_text,
                "type": mapped_type,
                "start": start,
                "end": end,
                "score": entity_score
            })

        # 6. 合并相邻的相同类型实体
        if self.merge_adjacent and formatted_entities:
            formatted_entities = self._merge_adjacent_entities(formatted_entities)

        return formatted_entities

    def _map_entity_type(self, entity_type: str) -> str:
        """
        映射实体类型标签。
        有些模型输出数字标签（如LABEL_0, LABEL_1），需要映射为有意义的类型。

        Args:
            entity_type: 原始实体类型标签

        Returns:
            映射后的实体类型
        """
        # 常见的中文NER标签映射
        type_mapping = {
            "LABEL_0": "PER",      # 人名
            "LABEL_1": "ORG",      # 组织
            "LABEL_2": "LOC",      # 地点
            "LABEL_3": "MISC",     # 其他
            "B-PER": "PER",
            "I-PER": "PER",
            "B-ORG": "ORG",
            "I-ORG": "ORG",
            "B-LOC": "LOC",
            "I-LOC": "LOC",
            "B-MISC": "MISC",
            "I-MISC": "MISC",
            "PER": "PER",
            "ORG": "ORG",
            "LOC": "LOC",
            "MISC": "MISC"
        }

        return type_mapping.get(entity_type, entity_type)

    def _is_meaningless_entity(self, entity_text: str, entity_type: str) -> bool:
        """
        判断实体是否无意义。

        Args:
            entity_text: 实体文本
            entity_type: 实体类型

        Returns:
            如果实体无意义返回True
        """
        # 1. 纯数字（除非是年份、日期等）
        if entity_text.isdigit():
            # 检查是否为有意义的数字（年份、日期等）
            if len(entity_text) == 4 and 1000 <= int(entity_text) <= 2100:  # 年份
                return False
            return True

        # 2. 单个字符（除非是特殊符号或有意义的单个字）
        if len(entity_text) == 1:
            # 中文单个字可能是人名的一部分，但单独的单个字通常无意义
            # 这里可以更精确地判断，暂时先过滤
            return True

        # 3. 常见无意义模式
        meaningless_patterns = [
            r'^\W+$',  # 全是标点符号
            r'^\d+[.,]\d+$',  # 数字加标点
            r'^[a-zA-Z]{1,2}$',  # 1-2个英文字母
        ]

        import re
        for pattern in meaningless_patterns:
            if re.match(pattern, entity_text):
                return True

        # 4. 检查是否包含太多特殊字符
        special_char_ratio = sum(1 for c in entity_text if not c.isalnum()) / len(entity_text)
        if special_char_ratio > 0.5:  # 超过50%的特殊字符
            return True

        return False

    def _merge_adjacent_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        合并相邻的相同类型实体。

        Args:
            entities: 实体列表（按起始位置排序）

        Returns:
            合并后的实体列表
        """
        if not entities:
            return []

        # 按起始位置排序
        sorted_entities = sorted(entities, key=lambda x: x["start"])

        merged_entities = []
        current_entity = sorted_entities[0]

        for i in range(1, len(sorted_entities)):
            next_entity = sorted_entities[i]

            # 检查是否相邻且类型相同
            is_adjacent = current_entity["end"] >= next_entity["start"] - 1  # 允许1个字符的间隔
            same_type = current_entity["type"] == next_entity["type"]

            if is_adjacent and same_type:
                # 合并实体
                current_entity["text"] = current_entity["text"] + " " + next_entity["text"]
                current_entity["end"] = next_entity["end"]
                current_entity["score"] = (current_entity["score"] + next_entity["score"]) / 2
            else:
                merged_entities.append(current_entity)
                current_entity = next_entity

        # 添加最后一个实体
        merged_entities.append(current_entity)

        return merged_entities

    def extract_relations(self, text: str, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从文本中提取实体间的关系。
        优先使用 DeepSeek 返回的关系（如果有），否则使用基于距离的共现关系提取。

        Args:
            text: 输入文本
            entities: 提取的实体列表

        Returns:
            关系列表，每个关系包含源实体、目标实体和关系类型
        """
        if not entities:
            return []

        # 优先使用 DeepSeek 返回的关系（如果有）
        if hasattr(self, '_deepseek_relations') and self._deepseek_relations:
            print(f"[DEBUG] 使用 DeepSeek 返回的 {len(self._deepseek_relations)} 个关系")
            relations = []
            seen_pairs = set()

            for rel in self._deepseek_relations:
                source = rel.get("source", "")
                target = rel.get("target", "")
                rel_type = rel.get("type", "related_to")
                strength = rel.get("strength", rel.get("confidence", 0.8))

                # 避免重复关系
                pair_key = (source, target, rel_type)
                reverse_key = (target, source, rel_type)
                if pair_key in seen_pairs or reverse_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                # 查找对应的实体类型
                source_type = "MISC"
                target_type = "MISC"
                for ent in entities:
                    if ent["text"] == source:
                        source_type = ent["type"]
                    if ent["text"] == target:
                        target_type = ent["type"]

                relations.append({
                    "source": source,
                    "target": target,
                    "type": rel_type,
                    "source_type": source_type,
                    "target_type": target_type,
                    "strength": float(strength),
                    "method": "DeepSeek"
                })

            return relations

        # 改进的关系提取（基于距离的共现关系）
        relations = []
        seen_pairs = set()  # 避免重复关系

        # 将文本按句子分割（简单实现）
        sentences = self._split_into_sentences(text)

        for sentence in sentences:
            # 找到在当前句子中的实体
            sentence_entities = []
            for entity in entities:
                if sentence["start"] <= entity["start"] <= sentence["end"]:
                    sentence_entities.append(entity)

            # 如果句子中实体太少，跳过
            if len(sentence_entities) < 2:
                continue

            # 为同一句子中的实体创建关系
            for i in range(len(sentence_entities)):
                for j in range(i + 1, len(sentence_entities)):
                    ent1 = sentence_entities[i]
                    ent2 = sentence_entities[j]

                    # 创建关系键（有序对）避免重复
                    pair_key = (ent1["text"], ent2["text"], ent1["type"], ent2["type"])
                    reverse_key = (ent2["text"], ent1["text"], ent2["type"], ent1["type"])

                    if pair_key in seen_pairs or reverse_key in seen_pairs:
                        continue

                    seen_pairs.add(pair_key)

                    # 计算实体之间的距离（字符数）
                    distance = abs(ent1["start"] - ent2["start"])

                    # 计算关系强度：距离越近，强度越高
                    # 使用句子长度作为参考，使得同一句子内的实体距离也能产生差异化
                    sentence_length = sentence["end"] - sentence["start"]
                    max_distance = max(30, sentence_length / 3)  # 最小 30 或句子 1/3 长度
                    distance_strength = max(0, 1 - distance / max_distance)

                    # 结合实体置信度（使用差异化的置信度）
                    confidence_strength = (ent1["score"] + ent2["score"]) / 2

                    # 综合强度 - 增加距离的权重，使得关系更有区分度
                    # 距离权重 60%，置信度权重 40%
                    strength = 0.6 * distance_strength + 0.4 * confidence_strength

                    # 确定关系类型（可以根据实体类型组合）
                    rel_type = self._determine_relation_type(ent1["type"], ent2["type"])

                    # 仅当关系强度足够高时才添加
                    if strength > 0.3:
                        relations.append({
                            "source": ent1["text"],
                            "target": ent2["text"],
                            "type": rel_type,
                            "source_type": ent1["type"],
                            "target_type": ent2["type"],
                            "context": sentence["text"],
                            "strength": float(strength),  # 动态计算的关系强度
                            "distance": distance
                        })

        return relations

    def _split_into_sentences(self, text: str) -> List[Dict[str, Any]]:
        """
        将文本分割成句子（简单实现）。

        Args:
            text: 输入文本

        Returns:
            句子列表，每个句子包含文本和位置信息
        """
        # 简单的句子分割：基于中文标点
        sentence_delimiters = ['。', '！', '？', '；', '……', '\n', '.', '!', '?', ';']

        sentences = []
        start = 0
        for i, char in enumerate(text):
            if char in sentence_delimiters:
                if i > start:
                    sentence_text = text[start:i+1].strip()
                    if sentence_text:
                        sentences.append({
                            "text": sentence_text,
                            "start": start,
                            "end": i
                        })
                start = i + 1

        # 处理最后一句
        if start < len(text):
            sentence_text = text[start:].strip()
            if sentence_text:
                sentences.append({
                    "text": sentence_text,
                    "start": start,
                    "end": len(text) - 1
                })

        return sentences

    def _determine_relation_type(self, type1: str, type2: str) -> str:
        """
        根据实体类型确定关系类型。

        Args:
            type1: 实体1类型
            type2: 实体2类型

        Returns:
            关系类型字符串
        """
        # 扩展的映射规则
        type_mapping = {
            ("PER", "ORG"): "work_for",           # 人在组织工作
            ("PER", "LOC"): "located_in",         # 人位于地点
            ("ORG", "LOC"): "located_in",         # 组织位于地点
            ("PER", "PER"): "related_to",         # 人与人相关
            ("ORG", "ORG"): "cooperate_with",     # 组织间合作
            ("LOC", "LOC"): "near",               # 地点相近
            ("PER", "MISC"): "associated_with",   # 人与其他事物关联
            ("ORG", "MISC"): "related_to",        # 组织与其他事物相关
            ("LOC", "MISC"): "contains",          # 地点包含事物
            ("MISC", "MISC"): "related_to",       # 事物间相关
        }

        # 标准化类型（确保大写）
        t1 = type1.upper() if type1 else "MISC"
        t2 = type2.upper() if type2 else "MISC"

        # 如果类型不在标准集合中，使用MISC
        standard_types = {"PER", "ORG", "LOC", "MISC"}
        t1 = t1 if t1 in standard_types else "MISC"
        t2 = t2 if t2 in standard_types else "MISC"

        key = (t1, t2)
        reverse_key = (t2, t1)

        if key in type_mapping:
            return type_mapping[key]
        elif reverse_key in type_mapping:
            return type_mapping[reverse_key]
        else:
            # 基于类型的通用关系
            if t1 == t2:
                return f"{t1.lower()}_related"
            else:
                return f"{t1.lower()}_{t2.lower()}_related"

    def build_graph(self, text: str) -> Dict[str, Any]:
        """
        从文本构建完整的知识图谱。

        Args:
            text: 输入文本

        Returns:
            包含图谱信息的字典
        """
        print("正在提取实体...")
        entities = self.extract_entities(text)
        print(f"提取到 {len(entities)} 个实体")

        print("正在提取关系...")
        relations = self.extract_relations(text, entities)
        print(f"提取到 {len(relations)} 个关系")

        # 构建networkx图
        self.graph = nx.Graph()

        # 添加节点（实体）
        for entity in entities:
            # 构建实体 ID：优先使用 text 字段，如果没有则使用 name
            entity_text = entity.get('text', entity.get('name', ''))
            entity_type = entity.get('type', 'UNKNOWN')
            entity_id = f"{entity_text}_{entity_type}"

            # 确保节点包含所有必要的字段
            node_data = {
                'text': entity_text,
                'name': entity.get('name', entity_text),  # 保留 name 字段
                'type': entity_type,
                'score': entity.get('score', entity.get('confidence', 0.8)),
                'method': entity.get('method', 'unknown'),
                'description': entity.get('description', ''),  # 保留 description 字段
                'start': entity.get('start', 0),
                'end': entity.get('end', len(entity_text))
            }
            self.graph.add_node(entity_id, **node_data)

        # 添加边（关系）
        # 先构建 text -> node_id 的映射，方便查找
        text_to_node = {}
        for node_id, node_data in self.graph.nodes(data=True):
            text = node_data.get('text', '')
            if text:
                if text not in text_to_node:
                    text_to_node[text] = []
                text_to_node[text].append(node_id)

        for relation in relations:
            source_text = relation['source']
            target_text = relation['target']

            # 尝试直接使用 source_type 构建 ID
            source_id = f"{source_text}_{relation['source_type']}"
            target_id = f"{target_text}_{relation['target_type']}"

            # 如果找不到，尝试使用 text_to_node 映射查找
            if source_id not in self.graph and source_text in text_to_node:
                # 选择第一个匹配的节点 ID
                source_id = text_to_node[source_text][0]

            if target_id not in self.graph and target_text in text_to_node:
                target_id = text_to_node[target_text][0]

            if source_id in self.graph and target_id in self.graph:
                self.graph.add_edge(source_id, target_id, **relation)
            else:
                # 调试信息：记录无法添加的边
                print(f"[DEBUG] 无法添加边：{source_text} -> {target_text}, source_id={source_id}, target_id={target_id}")
                if source_id not in self.graph:
                    print(f"  - source_id '{source_id}' 不在图中")
                if target_id not in self.graph:
                    print(f"  - target_id '{target_id}' 不在图中")

        # 应用优化（如果启用）
        optimization_stats = {}
        if any([self.enable_semantic_normalization, self.enable_transitive_reduction,
                self.enable_lpg_transformation, self.enable_statistical_filtering]):
            try:
                from app.kg.kg_optimizer import KnowledgeGraphOptimizer

                optimizer_config = {
                    "semantic_similarity_threshold": self.semantic_similarity_threshold,
                    "transitive_reduction_threshold": self.transitive_reduction_threshold,
                    "statistical_filtering_threshold": self.statistical_filtering_threshold,
                    "entropy_filtering_threshold": self.entropy_filtering_threshold
                }
                optimizer = KnowledgeGraphOptimizer(optimizer_config)

                enabled_optimizations = {
                    "semantic_normalization": self.enable_semantic_normalization,
                    "transitive_reduction": self.enable_transitive_reduction,
                    "lpg_transformation": self.enable_lpg_transformation,
                    "statistical_filtering": self.enable_statistical_filtering
                }

                optimized_graph, optimization_stats = optimizer.optimize(
                    self.graph, entities, relations, enabled_optimizations
                )

                # 更新图
                self.graph = optimized_graph

                print("知识图谱优化完成！")
                for opt_name, opt_stats in optimization_stats.items():
                    print(f"  {opt_name}: {opt_stats}")

            except ImportError as e:
                print(f"警告: 无法导入优化器模块，跳过优化: {e}")
            except Exception as e:
                print(f"警告: 知识图谱优化失败，跳过优化: {e}")
                import traceback
                print(traceback.format_exc())

        # 收集统计信息（包含优化统计）
        stats = {
            "entity_count": len(entities),
            "relation_count": len(relations),
            "node_count": self.graph.number_of_nodes(),
            "edge_count": self.graph.number_of_edges(),
            "entities": entities[:20],  # 限制数量避免数据过大
            "relations": relations[:20],
            "optimization_stats": optimization_stats
        }

        return stats

    def visualize_graph(self, output_path: str = "knowledge_graph.html"):
        """
        生成知识图谱的可视化HTML文件。

        Args:
            output_path: 输出HTML文件路径
        """
        try:
            from pyvis.network import Network

            # 检查图形是否为空
            if self.graph.number_of_nodes() == 0:
                print("警告: 图形为空，无法生成可视化")
                return None

            # 创建pyvis网络
            net = Network(height="750px", width="100%", bgcolor="#222222", font_color="white")
            net.barnes_hut()

            # 添加节点
            for node, data in self.graph.nodes(data=True):
                # 根据实体类型设置颜色
                color_map = {
                    "PER": "#FF6B6B",  # 红色
                    "ORG": "#4ECDC4",  # 青色
                    "LOC": "#45B7D1",  # 蓝色
                    "MISC": "#96CEB4",  # 绿色
                }
                color = color_map.get(data.get("type", "MISC"), "#95A5A6")  # 默认灰色

                net.add_node(
                    node,
                    label=data.get("text", node),
                    title=f"类型: {data.get('type', '未知')}\n置信度: {float(data.get('score', 0)):.2f}",
                    color=color,
                    size=20 + float(data.get("score", 0)) * 10  # 根据置信度调整大小
                )

            # 添加边
            for u, v, data in self.graph.edges(data=True):
                net.add_edge(
                    u, v,
                    title=f"关系: {data.get('type', '相关')}\n上下文: {data.get('context', '')[:50]}...",
                    width=1 + float(data.get("strength", 1)) * 2  # 根据强度调整宽度
                )

            # 生成HTML - 使用更稳健的方法
            try:
                # 先尝试生成HTML字符串
                html = net.generate_html()

                # 保存到文件
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(html)

                print(f"知识图谱可视化已保存到: {output_path}")
                return output_path

            except AttributeError as e:
                # 如果 generate_html 方法不存在，回退到 show 方法
                print(f"使用 generate_html 失败，尝试使用 show 方法: {e}")
                net.show(output_path)
                print(f"知识图谱可视化已保存到: {output_path}")
                return output_path

            except Exception as e:
                print(f"生成HTML文件失败: {e}")
                # 尝试直接使用 show 方法
                try:
                    net.show(output_path)
                    print(f"知识图谱可视化已保存到: {output_path}")
                    return output_path
                except Exception as e2:
                    print(f"使用 show 方法也失败: {e2}")
                    return None

        except ImportError as e:
            print(f"错误: 缺少可视化依赖 - {e}")
            print("请安装: pip install pyvis")
            return None
        except Exception as e:
            print(f"可视化过程中出现未知错误: {e}")
            return None

    def export_graph_data(self, output_path: str = "knowledge_graph.json") -> Dict[str, Any]:
        """
        导出图谱数据为JSON格式。

        Args:
            output_path: 输出JSON文件路径

        Returns:
            图谱数据字典
        """
        # 构建可序列化的图数据
        graph_data = {
            "nodes": [],
            "edges": [],
            "metadata": {
                "model": self.model_name,
                "node_count": self.graph.number_of_nodes(),
                "edge_count": self.graph.number_of_edges(),
            }
        }

        # 节点数据
        for node, data in self.graph.nodes(data=True):
            graph_data["nodes"].append({
                "id": node,
                "label": data.get("text", data.get("name", node)),  # 优先使用 text，其次 name
                "name": data.get("text", data.get("name", "")),  # 保留 name 字段供前端使用
                "type": data.get("type", "未知"),
                "score": float(data.get("score", 0)),
                "description": data.get("description", ""),  # 保留 description 字段（DeepSeek 返回）
                "method": data.get("method", "unknown")  # 标注提取方法
            })

        # 边数据
        for u, v, data in self.graph.edges(data=True):
            graph_data["edges"].append({
                "source": u,
                "target": v,
                "type": data.get("type", "相关"),
                "strength": float(data.get("strength", 1)),
                "context": data.get("context", "")[:100]  # 限制长度
            })

        # 保存到文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)

        print(f"图谱数据已导出到: {output_path}")
        return graph_data


def build_knowledge_graph_from_pdf(
    pdf_path: str,
    output_dir: str = "./kg_output",
    model_name: str = "ckiplab/bert-base-chinese-ner",
    use_advanced_extractor: bool = True,
    use_keybert: bool = True,
    use_spacy: bool = True,
    use_lexicon: bool = True,
    # DeepSeek 配置
    use_deepseek: bool = True,              # 默认使用 DeepSeek LLM
    deepseek_model: str = "deepseek-chat",
    deepseek_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    从PDF文件构建知识图谱的便捷函数。

    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录
        model_name: NER模型名称
        use_advanced_extractor: 是否使用高级提取器
        use_keybert: 是否使用KeyBERT提取关键词
        use_spacy: 是否使用spaCy提取名词短语
        use_lexicon: 是否使用领域词典
        use_deepseek: 是否使用 DeepSeek LLM 提取实体和关系
        deepseek_model: DeepSeek 模型名称 ("deepseek-chat" 或 "deepseek-v3")
        deepseek_api_key: DeepSeek API 密钥

    Returns:
        图谱构建结果
    """
    import os
    from langchain_community.document_loaders import PyPDFLoader

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    # 加载PDF
    print(f"正在加载PDF: {pdf_path}")
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()

    if not docs:
        print("未从PDF中提取到内容")
        return {"error": "无法提取PDF内容"}

    # 合并所有页面文本
    full_text = "\n".join([doc.page_content for doc in docs])
    print(f"提取到 {len(full_text)} 个字符的文本")

    # 构建知识图谱
    builder = KnowledgeGraphBuilder(
        model_name=model_name,
        use_advanced_extractor=use_advanced_extractor,
        use_keybert=use_keybert,
        use_spacy=use_spacy,
        use_lexicon=use_lexicon,
        use_deepseek=use_deepseek,
        deepseek_model=deepseek_model,
        deepseek_api_key=deepseek_api_key
    )

    try:
        stats = builder.build_graph(full_text)

        # 生成可视化
        html_path = os.path.join(output_dir, "knowledge_graph.html")
        builder.visualize_graph(html_path)

        # 导出数据
        json_path = os.path.join(output_dir, "knowledge_graph.json")
        graph_data = builder.export_graph_data(json_path)

        # 返回结果
        result = {
            "success": True,
            "text_length": len(full_text),
            "stats": stats,
            "visualization": html_path,
            "data": json_path,
            "graph": graph_data
        }

        return result

    except Exception as e:
        print(f"构建知识图谱时出错: {e}")
        return {"error": str(e), "success": False}
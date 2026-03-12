"""
知识图谱提取器模块。

提供多种实体提取方法：
1. 基于NER的提取
2. 基于KeyBERT的关键词提取
3. 基于spaCy的名词短语提取
4. 领域词典增强
"""

import json
import os
from typing import List, Dict, Any, Tuple, Optional, Set
import re


class KGEntityExtractor:
    """
    知识图谱实体提取器，集成多种提取方法。
    """

    def __init__(
        self,
        model_name: str = "ckiplab/bert-base-chinese-ner",
        min_confidence: float = 0.5,
        min_entity_length: int = 2,
        use_keybert: bool = True,
        use_spacy: bool = True,
        use_lexicon: bool = True,
        keybert_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    ):
        """
        初始化提取器。

        Args:
            model_name: NER模型名称
            min_confidence: 实体置信度阈值
            min_entity_length: 最小实体长度
            use_keybert: 是否使用KeyBERT
            use_spacy: 是否使用spaCy
            use_lexicon: 是否使用领域词典
            keybert_model: KeyBERT模型名称
        """
        self.model_name = model_name
        self.min_confidence = min_confidence
        self.min_entity_length = min_entity_length
        self.use_keybert = use_keybert
        self.use_spacy = use_spacy
        self.use_lexicon = use_lexicon
        self.keybert_model = keybert_model

        self.ner_pipeline = None
        self.spacy_nlp = None
        self.keybert_model_instance = None

    def load_models(self):
        """加载所有必要的模型（延迟加载）"""
        try:
            # 加载NER模型
            if self.model_name:
                from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification
                import torch

                print(f"正在加载NER模型: {self.model_name}...")
                self.ner_pipeline = pipeline(
                    "ner",
                    model=self.model_name,
                    tokenizer=self.model_name,
                    aggregation_strategy="simple"
                )
                print("NER模型加载完成")
        except ImportError as e:
            print(f"警告: 缺少NER依赖 - {e}")
            print("请安装: pip install transformers torch")

        try:
            # 加载spaCy模型
            if self.use_spacy:
                import spacy
                print("正在加载spaCy中文模型...")
                try:
                    self.spacy_nlp = spacy.load("zh_core_web_sm")
                except OSError:
                    print("未找到spaCy中文模型，请运行: python -m spacy download zh_core_web_sm")
                    print("暂时禁用spaCy提取")
                    self.use_spacy = False
                print("spaCy模型加载完成")
        except ImportError as e:
            print(f"警告: 缺少spaCy依赖 - {e}")
            print("请安装: pip install spacy")
            self.use_spacy = False

        try:
            # 加载KeyBERT模型
            if self.use_keybert:
                from keybert import KeyBERT
                print(f"正在加载KeyBERT模型: {self.keybert_model}...")

                # 尝试加载KeyBERT，处理可能的HTTP客户端错误
                max_retries = 2
                for retry in range(max_retries):
                    try:
                        # 在重试时，如果是第二次尝试，使用更简单的模型
                        if retry == 1:
                            print("首次尝试失败，尝试使用更简单的模型...")
                            model_name = "all-MiniLM-L6-v2"
                        else:
                            model_name = self.keybert_model

                        self.keybert_model_instance = KeyBERT(model_name)
                        print("KeyBERT模型加载完成")
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
                                print("KeyBERT加载失败，禁用KeyBERT提取")
                                self.use_keybert = False
                                break
                        else:
                            # 其他RuntimeError
                            print(f"警告: KeyBERT加载失败 - {e}")
                            print("禁用KeyBERT提取")
                            self.use_keybert = False
                            break
                    except Exception as e:
                        print(f"警告: KeyBERT加载失败 - {e}")
                        print("禁用KeyBERT提取")
                        self.use_keybert = False
                        break
                else:
                    # 循环正常结束（所有重试都失败）
                    print("KeyBERT加载失败，禁用KeyBERT提取")
                    self.use_keybert = False
        except ImportError as e:
            print(f"警告: 缺少KeyBERT依赖 - {e}")
            print("请安装: pip install keybert")
            self.use_keybert = False

    def _preprocess_text(self, text: str) -> str:
        """
        预处理文本。

        Args:
            text: 原始文本

        Returns:
            清理后的文本
        """
        if not text:
            return text

        # 1. 替换多个连续空白字符为单个空格
        text = re.sub(r'\s+', ' ', text)

        # 2. 移除PDF中常见的无意义字符和乱码
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

        # 3. 清理行尾的连字符（PDF换行导致的）
        text = re.sub(r'-\s*\n\s*', '', text)

        # 4. 合并被错误分割的单词
        text = re.sub(r'\s*-\s*', '', text)  # 移除连字符周围的空格

        return text.strip()

    def extract_entities_with_ner(self, text: str) -> List[Dict[str, Any]]:
        """
        使用NER模型提取实体。

        Args:
            text: 输入文本

        Returns:
            实体列表
        """
        if self.ner_pipeline is None:
            self.load_models()
            if self.ner_pipeline is None:
                return []

        cleaned_text = self._preprocess_text(text)

        # 如果文本太长，分段处理
        max_length = 512
        if len(cleaned_text) > max_length * 0.9:
            chunks = [cleaned_text[i:i+max_length] for i in range(0, len(cleaned_text), max_length)]
            all_entities = []
            for chunk in chunks:
                entities = self.ner_pipeline(chunk)
                all_entities.extend(entities)
        else:
            entities = self.ner_pipeline(cleaned_text)

        # 格式化实体
        formatted_entities = self._format_ner_entities(entities, cleaned_text)
        return formatted_entities

    def _format_ner_entities(self, raw_entities: List[Dict[str, Any]], text: str) -> List[Dict[str, Any]]:
        """
        格式化NER实体。

        Args:
            raw_entities: 原始NER输出
            text: 原始文本

        Returns:
            格式化后的实体列表
        """
        if not raw_entities:
            return []

        formatted_entities = []
        for entity in raw_entities:
            entity_text = entity.get("word", "").strip()
            entity_type = entity.get("entity_group", "")
            entity_score = float(entity.get("score", 0))
            start = int(entity.get("start", 0))
            end = int(entity.get("end", 0))

            # 置信度过滤
            if entity_score < self.min_confidence:
                continue

            # 长度过滤
            if len(entity_text) < self.min_entity_length:
                continue

            # 内容过滤
            if self._is_meaningless_entity(entity_text):
                continue

            # 映射实体类型
            mapped_type = self._map_entity_type(entity_type)

            formatted_entities.append({
                "text": entity_text,
                "type": mapped_type,
                "start": start,
                "end": end,
                "score": entity_score,
                "method": "NER"
            })

        return formatted_entities

    def extract_keywords_with_keybert(self, text: str, top_n: int = 20) -> List[Dict[str, Any]]:
        """
        使用KeyBERT提取关键词。

        Args:
            text: 输入文本
            top_n: 返回的关键词数量

        Returns:
            关键词列表
        """
        if not self.use_keybert:
            return []

        if self.keybert_model_instance is None:
            self.load_models()
            if self.keybert_model_instance is None:
                return []

        cleaned_text = self._preprocess_text(text)

        try:
            # KeyBERT支持中文
            keywords = self.keybert_model_instance.extract_keywords(
                cleaned_text,
                keyphrase_ngram_range=(1, 3),  # 支持1-3个词的关键词
                stop_words=None,  # 中文停用词处理
                top_n=top_n,
                use_mmr=True,  # 使用最大边缘相关性增加多样性
                diversity=0.7
            )

            formatted_keywords = []
            for keyword, score in keywords:
                # 过滤太短的或无意义的关键词
                if len(keyword) < self.min_entity_length:
                    continue
                if self._is_meaningless_entity(keyword):
                    continue

                # 尝试确定关键词类型
                keyword_type = self._determine_keyword_type(keyword)

                formatted_keywords.append({
                    "text": keyword,
                    "type": keyword_type,
                    "score": float(score),
                    "method": "KeyBERT"
                })

            return formatted_keywords

        except Exception as e:
            print(f"KeyBERT提取失败: {e}")
            return []

    def extract_noun_phrases_with_spacy(self, text: str) -> List[Dict[str, Any]]:
        """
        使用spaCy提取名词短语。

        Args:
            text: 输入文本

        Returns:
            名词短语列表
        """
        if not self.use_spacy:
            return []

        if self.spacy_nlp is None:
            self.load_models()
            if self.spacy_nlp is None:
                return []

        cleaned_text = self._preprocess_text(text)

        try:
            # 处理文本
            doc = self.spacy_nlp(cleaned_text)

            noun_phrases = []
            for chunk in doc.noun_chunks:
                phrase_text = chunk.text.strip()
                if not phrase_text:
                    continue

                # 过滤太短的短语
                if len(phrase_text) < self.min_entity_length:
                    continue

                # 过滤无意义的短语
                if self._is_meaningless_entity(phrase_text):
                    continue

                # 确定短语类型
                phrase_type = self._determine_noun_phrase_type(chunk)

                noun_phrases.append({
                    "text": phrase_text,
                    "type": phrase_type,
                    "score": 0.8,  # 名词短语的默认置信度
                    "method": "spaCy"
                })

            return noun_phrases

        except Exception as e:
            print(f"spaCy提取失败: {e}")
            return []

    def extract_domain_terms(self, text: str) -> List[Dict[str, Any]]:
        """
        从领域词典中匹配术语。

        Args:
            text: 输入文本

        Returns:
            领域术语列表
        """
        if not self.use_lexicon:
            return []

        try:
            from app.kg.domain_lexicon import DomainLexicon
            lexicon = DomainLexicon()
            all_terms = lexicon.terms

            found_terms = []
            for term in all_terms:
                # 简单的字符串匹配（可以改进为正则表达式）
                if term in text:
                    # 检查是否已经包含在其他方法中
                    found_terms.append({
                        "text": term,
                        "type": "DOMAIN",
                        "score": 0.9,  # 领域术语的高置信度
                        "method": "Lexicon",
                        "categories": lexicon.categorize_term(term)
                    })

            return found_terms

        except ImportError:
            print("警告: 未找到领域词典模块")
            return []
        except Exception as e:
            print(f"领域术语提取失败: {e}")
            return []

    def extract_all_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        使用所有方法提取实体，并合并结果。

        Args:
            text: 输入文本

        Returns:
            合并后的实体列表
        """
        all_entities = []

        # 1. NER提取
        ner_entities = self.extract_entities_with_ner(text)
        all_entities.extend(ner_entities)

        # 2. KeyBERT提取
        keybert_keywords = self.extract_keywords_with_keybert(text)
        all_entities.extend(keybert_keywords)

        # 3. spaCy名词短语提取
        spacy_phrases = self.extract_noun_phrases_with_spacy(text)
        all_entities.extend(spacy_phrases)

        # 4. 领域词典匹配
        domain_terms = self.extract_domain_terms(text)
        all_entities.extend(domain_terms)

        # 合并和去重
        merged_entities = self._merge_and_deduplicate_entities(all_entities)

        return merged_entities

    def _merge_and_deduplicate_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        合并和去重实体。

        Args:
            entities: 原始实体列表

        Returns:
            合并后的实体列表
        """
        if not entities:
            return []

        # 按文本分组
        entity_dict = {}
        for entity in entities:
            text = entity["text"]
            if text not in entity_dict:
                entity_dict[text] = entity
            else:
                # 合并重复实体
                existing = entity_dict[text]
                # 取最高置信度
                if entity["score"] > existing["score"]:
                    existing["score"] = entity["score"]
                # 合并类型
                if existing["type"] != entity["type"]:
                    # 如果类型不同，使用更具体的类型
                    type_priority = {"DOMAIN": 4, "CONCEPT": 3, "TECH": 2, "METHOD": 1, "GENERAL": 0}
                    existing_priority = type_priority.get(existing["type"], 0)
                    new_priority = type_priority.get(entity["type"], 0)
                    if new_priority > existing_priority:
                        existing["type"] = entity["type"]
                # 合并方法
                methods = set(existing.get("methods", [existing.get("method", "UNKNOWN")]))
                methods.add(entity.get("method", "UNKNOWN"))
                existing["methods"] = list(methods)

        # 返回去重后的实体列表
        return list(entity_dict.values())

    def _is_meaningless_entity(self, entity_text: str) -> bool:
        """
        判断实体是否无意义。

        Args:
            entity_text: 实体文本

        Returns:
            如果实体无意义返回True
        """
        # 1. 纯数字
        if entity_text.isdigit():
            # 检查是否为有意义的数字（年份、日期等）
            if len(entity_text) == 4 and 1000 <= int(entity_text) <= 2100:
                return False
            return True

        # 2. 单个字符
        if len(entity_text) == 1:
            return True

        # 3. 常见无意义模式
        meaningless_patterns = [
            r'^\W+$',  # 全是标点符号
            r'^\d+[.,]\d+$',  # 数字加标点
            r'^[a-zA-Z]{1,2}$',  # 1-2个英文字母
        ]

        for pattern in meaningless_patterns:
            if re.match(pattern, entity_text):
                return True

        # 4. 检查是否包含太多特殊字符
        special_char_ratio = sum(1 for c in entity_text if not c.isalnum()) / len(entity_text)
        if special_char_ratio > 0.5:
            return True

        return False

    def _map_entity_type(self, entity_type: str) -> str:
        """
        映射实体类型标签。

        Args:
            entity_type: 原始实体类型

        Returns:
            映射后的类型
        """
        type_mapping = {
            "LABEL_0": "PER",
            "LABEL_1": "ORG",
            "LABEL_2": "LOC",
            "LABEL_3": "MISC",
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

        return type_mapping.get(entity_type, "MISC")

    def _determine_keyword_type(self, keyword: str) -> str:
        """
        确定关键词类型。

        Args:
            keyword: 关键词

        Returns:
            类型标签
        """
        # 简单的规则判断（可以根据需要扩展）
        tech_keywords = ["神经网络", "深度学习", "机器学习", "算法", "模型", "框架"]
        method_keywords = ["训练", "测试", "验证", "优化", "评估", "分析"]
        concept_keywords = ["特征", "标签", "数据", "样本", "参数", "超参数"]

        keyword_lower = keyword.lower()

        for tech in tech_keywords:
            if tech in keyword:
                return "TECH"

        for method in method_keywords:
            if method in keyword:
                return "METHOD"

        for concept in concept_keywords:
            if concept in keyword:
                return "CONCEPT"

        # 默认返回 CONCEPT 而不是 GENERAL
        return "CONCEPT"

    def _determine_noun_phrase_type(self, chunk) -> str:
        """
        确定名词短语类型。

        Args:
            chunk: spaCy的名词短语chunk

        Returns:
            类型标签
        """
        # 简单的规则：检查包含的关键词
        text = chunk.text

        tech_keywords = ["网络", "模型", "算法", "系统", "框架"]
        concept_keywords = ["数据", "特征", "参数", "结果", "性能"]

        for tech in tech_keywords:
            if tech in text:
                return "TECH"

        for concept in concept_keywords:
            if concept in text:
                return "CONCEPT"

        return "NOUN_PHRASE"
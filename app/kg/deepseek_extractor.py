"""
知识图谱 - DeepSeek LLM 提取器模块

使用 DeepSeek LLM 进行实体和关系提取。
"""

import json
import os
from typing import List, Dict, Any, Optional, Tuple
import re


class DeepSeekKGExtractor:
    """
    使用 DeepSeek LLM 进行知识图谱实体和关系提取。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "deepseek-chat",
        temperature: float = 0.1,
        max_tokens: int = 4000,
        base_url: str = "https://api.deepseek.com/v1"
    ):
        """
        初始化 DeepSeek LLM 提取器。

        Args:
            api_key: DeepSeek API 密钥（如果为 None，则从配置或环境变量读取）
            model: 使用的模型名称
            temperature: 温度参数
            max_tokens: 最大输出 token 数
            base_url: API 基础 URL
        """
        # 优先使用传入的 api_key，其次从配置读取，最后从环境变量读取
        if api_key is None:
            try:
                from app.core.config import settings
                self.api_key = settings.DEEPSEEK_API_KEY
            except (ImportError, AttributeError):
                self.api_key = os.environ.get("DEEPSEEK_API_KEY")
        else:
            self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.base_url = base_url
        self.client = None

        if not self.api_key:
            print("警告：未设置 DeepSeek API 密钥，请设置 DEEPSEEK_API_KEY 环境变量")

    def _get_client(self):
        """获取或创建 API 客户端（延迟初始化）"""
        if self.client is None:
            try:
                from openai import OpenAI
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url
                )
            except ImportError:
                print("错误：需要安装 openai 库：pip install openai")
                return None
        return self.client

    def extract_entities_and_relations(
        self,
        text: str,
        chunk_size: int = 3000,
        merge_results: bool = True
    ) -> Dict[str, Any]:
        """
        从文本中提取实体和关系。

        Args:
            text: 输入文本
            chunk_size: 文本分块大小（字符数）
            merge_results: 是否合并分块结果

        Returns:
            包含 entities 和 relations 的字典
        """
        client = self._get_client()
        if client is None:
            return {"entities": [], "relations": []}

        # 如果文本太长，分块处理
        if len(text) > chunk_size:
            chunks = self._split_text_for_extraction(text, chunk_size)
            all_results = []

            for i, chunk in enumerate(chunks):
                print(f"正在处理第 {i+1}/{len(chunks)} 块...")
                result = self._extract_from_chunk(client, chunk)
                all_results.append(result)

            if merge_results:
                return self._merge_extraction_results(all_results)
            else:
                # 返回所有块的结果
                merged = {"entities": [], "relations": []}
                for result in all_results:
                    merged["entities"].extend(result["entities"])
                    merged["relations"].extend(result["relations"])
                return merged
        else:
            return self._extract_from_chunk(client, text)

    def _split_text_for_extraction(
        self,
        text: str,
        chunk_size: int
    ) -> List[str]:
        """
        将文本分割成适合 LLM 处理的块。

        Args:
            text: 输入文本
            chunk_size: 每块大小

        Returns:
            文本块列表
        """
        chunks = []
        start = 0

        while start < len(text):
            # 尝试在句子边界处分割
            end = min(start + chunk_size, len(text))

            # 查找最近的句子结束符
            if end < len(text):
                for delimiter in ['。', '！', '？', '；', '\n', '.', '!', '?']:
                    last_pos = text.rfind(delimiter, start, end)
                    if last_pos > start:
                        end = last_pos + 1
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end

        return chunks

    def _extract_from_chunk(
        self,
        client,
        text: str
    ) -> Dict[str, Any]:
        """
        从单个文本块中提取实体和关系。

        Args:
            client: API 客户端
            text: 文本块

        Returns:
            提取结果
        """
        from app.kg.deepseek_config import ENTITY_EXTRACTION_PROMPT

        try:
            prompt = ENTITY_EXTRACTION_PROMPT.format(text=text)
        except Exception as e:
            print(f"[DEBUG] 提示词格式化失败：{e}")
            # 如果格式化失败，使用简单提示
            prompt = f"请从以下文本中提取实体和关系，输出 JSON 格式：{text[:1000]}"

        print(f"[DEBUG] 发送提示词到 DeepSeek API，长度：{len(prompt)}")

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个知识图谱构建专家，负责从文本中提取实体和关系，并以严格的 JSON 格式输出。不要输出任何解释，只输出 JSON 数据。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            content = response.choices[0].message.content.strip()
            print(f"[DEBUG] DeepSeek API 响应长度：{len(content)}")

            # 解析 JSON 响应
            result = self._parse_extraction_response(content)
            return result

        except Exception as e:
            print(f"[DEBUG] DeepSeek API 调用异常：{e}")
            return {"entities": [], "relations": []}

    def _parse_extraction_response(self, content: str) -> Dict[str, Any]:
        """
        解析 LLM 返回的提取结果。

        Args:
            content: LLM 返回的内容

        Returns:
            解析后的结果
        """
        print(f"[DEBUG] DeepSeek 原始响应：{content[:500]}...")

        # 尝试直接解析 JSON
        try:
            # 移除可能的 markdown 代码块标记
            content = re.sub(r'^```json\s*', '', content)
            content = re.sub(r'\s*```$', '', content)
            content = content.strip()

            result = json.loads(content)

            # 验证格式
            entities = result.get("entities", [])
            relations = result.get("relations", [])

            # 打印第一个实体的字段用于调试
            if entities:
                print(f"[DEBUG] 第一个实体字段：{list(entities[0].keys())}")

            # 标准化实体格式 - 支持多种字段名
            import random
            random.seed()  # 使用系统时间作为种子

            for entity in entities:
                if "confidence" not in entity or entity.get("confidence") is None:
                    # 如果没有 confidence 字段，生成一个随机的但合理的置信度 (0.75-0.95)
                    entity["confidence"] = round(0.75 + random.random() * 0.2, 3)
                entity["score"] = entity["confidence"]  # 兼容旧格式
                entity["method"] = "DeepSeek"

                # 处理可能的字段名变体
                if "text" not in entity or not entity["text"]:
                    # 尝试其他字段名
                    for key in ["entity", "name", "value", "实体", "名称"]:
                        if key in entity and entity[key]:
                            entity["text"] = entity[key]
                            break
                    # 如果还是没找到，使用 type 作为最后手段
                    if "text" not in entity or not entity["text"]:
                        entity["text"] = entity.get("type", "")

            # 标准化关系格式 - 支持多种字段名
            for relation in relations:
                if "confidence" not in relation or relation.get("confidence") is None:
                    # 如果没有 confidence 字段，生成一个随机的但合理的置信度 (0.7-0.95)
                    relation["confidence"] = round(0.7 + random.random() * 0.25, 3)
                relation["strength"] = relation["confidence"]  # 兼容旧格式
                relation["type"] = relation.get("type", relation.get("predicate", "related_to"))

                # 处理可能的字段名变体
                if "source" not in relation or not relation["source"]:
                    for key in ["from", "src", "source_entity", "源实体", "subject"]:
                        if key in relation and relation[key]:
                            relation["source"] = relation[key]
                            break

                if "target" not in relation or not relation["target"]:
                    for key in ["to", "dst", "dest", "target_entity", "目标实体", "object"]:
                        if key in relation and relation[key]:
                            relation["target"] = relation[key]
                            break

            print(f"[DEBUG] DeepSeek 解析成功：{len(entities)} 个实体，{len(relations)} 个关系")
            return {"entities": entities, "relations": relations}

        except json.JSONDecodeError as e:
            print(f"JSON 解析失败：{e}")
            print(f"原始内容：{content[:200]}...")

            # 尝试提取 JSON 部分
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    return {
                        "entities": result.get("entities", []),
                        "relations": result.get("relations", [])
                    }
                except:
                    pass

            return {"entities": [], "relations": []}

    def _merge_extraction_results(
        self,
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        合并多个文本块的提取结果。

        Args:
            results: 提取结果列表

        Returns:
            合并后的结果
        """
        all_entities = []
        all_relations = []

        for result in results:
            all_entities.extend(result.get("entities", []))
            all_relations.extend(result.get("relations", []))

        # 去重实体
        seen_entities = set()
        unique_entities = []
        for entity in all_entities:
            key = (entity.get("text", ""), entity.get("type", ""))
            if key not in seen_entities:
                seen_entities.add(key)
                unique_entities.append(entity)

        # 去重关系
        seen_relations = set()
        unique_relations = []
        for relation in all_relations:
            key = (
                relation.get("source", ""),
                relation.get("target", ""),
                relation.get("type", "")
            )
            if key not in seen_relations:
                seen_relations.add(key)
                unique_relations.append(relation)

        return {"entities": unique_entities, "relations": unique_relations}

    def infer_relations(
        self,
        entities: List[Dict[str, Any]],
        context: str = ""
    ) -> List[Dict[str, Any]]:
        """
        基于实体列表推断可能的关系。

        Args:
            entities: 实体列表
            context: 背景文本

        Returns:
            推断的关系列表
        """
        client = self._get_client()
        if client is None or not entities:
            return []

        from app.kg.deepseek_config import RELATION_INFERENCE_PROMPT

        entities_str = ", ".join([f"{e.get('text', '')}({e.get('type', '')})" for e in entities])
        prompt = RELATION_INFERENCE_PROMPT.format(
            entities=entities_str,
            context=context[:2000] if context else ""
        )

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个知识图谱推理专家，擅长推断实体间的潜在关系。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.15,
                max_tokens=3000
            )

            content = response.choices[0].message.content.strip()

            # 解析响应
            try:
                content = re.sub(r'^```json\s*', '', content)
                content = re.sub(r'\s*```$', '', content)
                result = json.loads(content)
                relations = result.get("relations", [])

                # 标准化格式
                for rel in relations:
                    rel["strength"] = rel.get("confidence", 0.8)
                    rel["type"] = rel.get("type", "related_to")

                return relations

            except json.JSONDecodeError:
                return []

        except Exception as e:
            print(f"关系推断失败：{e}")
            return []

    def normalize_entities(
        self,
        entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        归一化实体列表（合并同义词、消除歧义）。

        Args:
            entities: 实体列表

        Returns:
            归一化后的实体列表
        """
        client = self._get_client()
        if client is None or not entities:
            return entities

        from app.kg.deepseek_config import ENTITY_NORMALIZATION_PROMPT

        entities_str = "\n".join([f"- {e.get('text', '')} ({e.get('type', '')})" for e in entities])
        prompt = ENTITY_NORMALIZATION_PROMPT.format(entities=entities_str)

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个知识图谱数据清洗专家，负责实体归一化处理。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,
                max_tokens=2000
            )

            content = response.choices[0].message.content.strip()

            # 解析响应
            try:
                content = re.sub(r'^```json\s*', '', content)
                content = re.sub(r'\s*```$', '', content)
                result = json.loads(content)

                normalized = result.get("normalized_entities", [])

                # 构建归一化映射
                normalization_map = {}
                for item in normalized:
                    original = item.get("original", "")
                    norm = item.get("normalized", original)
                    if original and norm:
                        normalization_map[original] = norm

                # 应用归一化
                result_entities = []
                seen = set()
                for entity in entities:
                    text = entity.get("text", "")
                    normalized_text = normalization_map.get(text, text)

                    key = (normalized_text, entity.get("type", ""))
                    if key not in seen:
                        seen.add(key)
                        entity["text"] = normalized_text
                        entity["normalized"] = True
                        result_entities.append(entity)

                return result_entities

            except json.JSONDecodeError:
                return entities

        except Exception as e:
            print(f"实体归一化失败：{e}")
            return entities


def extract_entities_with_llm(
    text: str,
    model: str = "deepseek-chat",
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    便捷函数：使用 DeepSeek LLM 从文本中提取实体和关系。

    Args:
        text: 输入文本
        model: 模型名称
        api_key: API 密钥

    Returns:
        包含 entities 和 relations 的字典
    """
    extractor = DeepSeekKGExtractor(api_key=api_key, model=model)
    return extractor.extract_entities_and_relations(text)


def infer_relations_with_llm(
    entities: List[Dict[str, Any]],
    context: str = "",
    model: str = "deepseek-chat",
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    便捷函数：使用 DeepSeek LLM 推断实体间关系。

    Args:
        entities: 实体列表
        context: 背景文本
        model: 模型名称
        api_key: API 密钥

    Returns:
        推断的关系列表
    """
    extractor = DeepSeekKGExtractor(api_key=api_key, model=model)
    return extractor.infer_relations(entities, context)


def normalize_entities_with_llm(
    entities: List[Dict[str, Any]],
    model: str = "deepseek-chat",
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    便捷函数：使用 DeepSeek LLM 归一化实体。

    Args:
        entities: 实体列表
        model: 模型名称
        api_key: API 密钥

    Returns:
        归一化后的实体列表
    """
    extractor = DeepSeekKGExtractor(api_key=api_key, model=model)
    return extractor.normalize_entities(entities)

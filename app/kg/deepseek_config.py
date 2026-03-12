"""
知识图谱 - DeepSeek LLM 配置模块

提供使用 DeepSeek LLM 进行知识图谱构建的配置和函数。
"""

# ============================================
# DeepSeek 模型配置
# ============================================

DEEPSEEK_MODELS = {
    # 实体和关系提取 - 使用 DeepSeek-V3（最强理解能力）
    "entity_extraction": {
        "model": "deepseek-chat",        # 或 "deepseek-v3"
        "temperature": 0.1,               # 低温度保证输出稳定性
        "max_tokens": 4000,               # 足够输出所有实体和关系
    },

    # 实体归一化/消歧 - 使用 DeepSeek-Chat（性价比高）
    "entity_normalization": {
        "model": "deepseek-chat",
        "temperature": 0.2,
        "max_tokens": 2000,
    },

    # 关系推断/补全 - 使用 DeepSeek-V3
    "relation_inference": {
        "model": "deepseek-v3",
        "temperature": 0.15,
        "max_tokens": 3000,
    },

    # 知识图谱总结 - 使用 DeepSeek-Chat
    "graph_summarization": {
        "model": "deepseek-chat",
        "temperature": 0.3,
        "max_tokens": 2000,
    },
}

# 默认配置
DEFAULT_MODEL_FOR_EXTRACTION = "deepseek-chat"   # 默认用于提取
DEFAULT_MODEL_FOR_INFERENCE = "deepseek-v3"      # 默认用于推理

# ============================================
# 提示词模板
# ============================================

ENTITY_EXTRACTION_PROMPT = """你是一个知识图谱构建专家。你的任务是从给定文本中提取实体和关系。

请按照以下 JSON 格式输出：
{
  "entities": [
    {"text": "实体文本", "type": "实体类型", "confidence": 0.9}
  ],
  "relations": [
    {"source": "源实体", "target": "目标实体", "type": "关系类型", "confidence": 0.9}
  ]
}

实体类型（必须从以下 7 种类型中选择，不要使用其他类型）：
- PER: 人名、具体人物
- ORG: 组织机构、公司、学校
- LOC: 地点、位置、区域
- TECH: 技术、工具、框架、平台、编程语言
- METHOD: 方法、技术、流程、步骤
- CONCEPT: 概念、原理、理论、思想
- DOMAIN: 领域、学科、专业方向

注意：
1. 不要使用"GENERAL"或其他未定义的类型
2. 如果实体不属于上述任何类型，可以归入 CONCEPT（通用概念）
3. 对于学习相关的实体，优先使用 METHOD（学习方法）或 CONCEPT（学习概念）
4. 对于技术相关的实体，优先使用 TECH（技术）或 METHOD（方法）

关系类型（请根据上下文选择最具体的关系）：
- part_of: 部分与整体关系（如"深度学习是机器学习的一部分"）
- is_a: 类型/分类关系（如"Python 是一种编程语言"）
- uses: 使用关系（如"使用 Python 开发"）
- depends_on: 依赖关系（如"机器学习依赖数据"）
- belongs_to: 归属关系（如"这属于人工智能领域"）
- located_in: 位置关系（如"公司位于北京"）
- work_for: 工作关系（如"他在谷歌工作"）
- cooperate_with: 合作关系（如"公司与大学合作"）
- associated_with: 关联关系（如"技术与应用相关联"）
- related_to: 一般相关关系（当无法确定具体类型时使用）
- causes: 因果关系（如"A 导致 B"）
- enables: 使能关系（如"技术使能应用"）
- 应用于：应用关系（如"技术应用于领域"）
- 包含：包含关系（如"领域包含主题"）
- 学习：学习关系（如"学习某项技能"）

重要要求：
1. 只提取最关键、最核心的实体和关系，不要提取所有可能的词
2. 优先提取明确的语义关系（如 part_of、is_a、uses 等），避免大量使用 related_to
3. 关系数量应控制在实体数量的 1-2 倍以内，避免图谱过于密集
4. 如果两个实体之间没有明确的关系，不要强行提取
5. 实体类型必须从预定义的 7 种类型中选择，不要 invent 新类型

请仔细阅读以下文本，提取所有有意义的实体和关系，直接输出 JSON，不要添加任何解释或 markdown 标记：

文本内容：
{text}
"""

RELATION_INFERENCE_PROMPT = """你是一个知识图谱推理专家。给定一些实体，请推断它们之间可能存在的合理关系。

实体列表：
{entities}

请参考以下背景文本（如果有）：
{context}

请按照以下 JSON 格式输出推断的关系：
{
  "relations": [
    {"source": "源实体", "target": "目标实体", "type": "关系类型", "reason": "推断理由", "confidence": 0.0-1.0},
    ...
  ]
}

直接输出 JSON，不要添加任何解释："""

ENTITY_NORMALIZATION_PROMPT = """你是一个知识图谱数据清洗专家。请对以下实体列表进行归一化处理：

1. 合并同义实体（如 "机器学习" 和 "ML"）
2. 消除歧义（如 "苹果 (公司)" 和 "苹果 (水果)"）
3. 标准化命名格式

实体列表：
{entities}

请按照以下 JSON 格式输出：
{
  "normalized_entities": [
    {"original": "原始文本", "normalized": "标准化后", "type": "实体类型", "note": "处理说明"},
    ...
  ]
}

直接输出 JSON，不要添加任何解释："""

# ============================================
# 使用示例
# ============================================

"""
# 使用 DeepSeek LLM 提取实体和关系
from app.kg.deepseek_config import extract_entities_with_llm

text = "机器学习是人工智能的一个分支..."
result = extract_entities_with_llm(text, model="deepseek-chat")

# 使用 DeepSeek LLM 推断关系
from app.kg.deepseek_config import infer_relations_with_llm

entities = [{"text": "机器学习", "type": "TECH"}, {"text": "人工智能", "type": "TECH"}]
relations = infer_relations_with_llm(entities, text)

# 使用 DeepSeek LLM 归一化实体
from app.kg.deepseek_config import normalize_entities_with_llm

entities = [{"text": "ML", "type": "TECH"}, {"text": "机器学习", "type": "TECH"}]
normalized = normalize_entities_with_llm(entities)
"""

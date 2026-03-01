# 知识图谱提取优化说明

## 概述

针对计算机学习领域，对知识图谱提取算法进行了优化，从传统的"词频"方法转向"语义"方法。主要改进包括：

1. **引入领域词典**：构建计算机学习领域的术语白名单
2. **使用深度学习模型**：采用KeyBERT进行语义关键词提取
3. **名词短语提取**：使用spaCy提取有意义的实体
4. **多方法融合**：集成多种提取方法，提高实体召回率

## 新功能

### 1. 领域词典 (`chattutor/core/domain_lexicon.py`)

包含计算机科学、机器学习、深度学习等领域的核心术语，按类别组织：

- 机器学习基础：监督学习、无监督学习、特征工程等
- 深度学习：神经网络、卷积神经网络、Transformer等
- 自然语言处理：词法分析、句法分析、命名实体识别等
- 计算机视觉：图像分类、目标检测、语义分割等
- 数据科学：数据清洗、数据可视化、统计推断等
- 编程与工具：Python、TensorFlow、PyTorch等

### 2. 高级实体提取器 (`chattutor/core/kg_extractor.py`)

`KGEntityExtractor` 类集成四种提取方法：

1. **NER提取**：使用预训练模型识别命名实体
2. **KeyBERT提取**：基于BERT嵌入的语义关键词提取
3. **spaCy名词短语提取**：提取有意义的复合名词
4. **领域词典匹配**：强制匹配领域核心术语

### 3. 集成到知识图谱构建器

`KnowledgeGraphBuilder` 类现在支持高级提取模式，通过以下参数控制：

- `use_advanced_extractor`: 启用/禁用高级提取器（默认True）
- `use_keybert`: 启用/禁用KeyBERT提取（默认True）
- `use_spacy`: 启用/禁用spaCy提取（默认True）
- `use_lexicon`: 启用/禁用领域词典匹配（默认True）

## 安装依赖

```bash
# 安装新增依赖
pip install keybert spacy

# 下载spaCy中文模型
python -m spacy download zh_core_web_sm

# 或安装所有依赖
pip install -r requirements.txt
```

## 使用方法

### 方式1：使用高级提取器（推荐）

```python
from chattutor.core.kg_builder import KnowledgeGraphBuilder

# 创建使用高级提取器的构建器
builder = KnowledgeGraphBuilder(
    model_name="ckiplab/bert-base-chinese-ner",
    use_advanced_extractor=True,  # 启用高级提取器
    use_keybert=True,             # 启用KeyBERT
    use_spacy=True,               # 启用spaCy
    use_lexicon=True              # 启用领域词典
)

# 构建知识图谱
stats = builder.build_graph(text)
print(f"提取到 {stats['entity_count']} 个实体，{stats['relation_count']} 个关系")
```

### 方式2：仅使用传统NER方法

```python
from chattutor.core.kg_builder import KnowledgeGraphBuilder

# 创建使用传统NER的构建器
builder = KnowledgeGraphBuilder(
    use_advanced_extractor=False  # 禁用高级提取器
)

# 构建知识图谱
stats = builder.build_graph(text)
```

### 方式3：直接使用提取器

```python
from chattutor.core.kg_extractor import KGEntityExtractor

# 创建提取器
extractor = KGEntityExtractor(
    use_keybert=True,
    use_spacy=True,
    use_lexicon=True
)

# 提取所有实体
entities = extractor.extract_all_entities(text)
for entity in entities:
    print(f"{entity['text']} ({entity['type']}, 置信度: {entity['score']:.2f})")
```

## 测试优化效果

运行测试脚本查看优化效果：

```bash
python test_kg_extractor.py
```

测试脚本会对比传统NER方法和高级提取器的效果，显示提取的实体数量和质量差异。

## 性能优化建议

1. **首次运行**：需要下载模型文件，可能需要几分钟时间
2. **内存使用**：KeyBERT和spaCy会占用额外内存，如果内存不足可以禁用部分功能
3. **处理速度**：高级提取器比传统NER慢，但提取质量更高
4. **配置选项**：可以根据需要调整参数：
   - `min_confidence`: 实体置信度阈值（默认0.5）
   - `min_entity_length`: 最小实体长度（默认2个字符）
   - `keybert_model`: KeyBERT模型名称（默认"paraphrase-multilingual-MiniLM-L12-v2"）

## 与现有代码的兼容性

1. **向后兼容**：默认参数保持向后兼容，现有代码无需修改
2. **API兼容**：`KnowledgeGraphBuilder` 的公共API保持不变
3. **输出格式**：实体和关系的输出格式保持不变
4. **可视化兼容**：生成的可视化文件格式保持不变

## 领域词典扩展

如需添加新的领域术语，编辑 `chattutor/core/domain_lexicon.py` 文件中的 `COMPUTER_SCIENCE_TERMS` 字典：

```python
COMPUTER_SCIENCE_TERMS = {
    "新类别名称": [
        "术语1",
        "术语2",
        # ...
    ],
    # ...
}
```

## 故障排除

### 1. 导入错误：缺少依赖
```
ImportError: No module named 'keybert'
```
解决方案：`pip install keybert`

### 2. spaCy模型未找到
```
OSError: [E050] Can't find model 'zh_core_web_sm'
```
解决方案：`python -m spacy download zh_core_web_sm`

### 3. 内存不足
减少同时使用的提取方法：
```python
builder = KnowledgeGraphBuilder(
    use_keybert=True,   # 保持KeyBERT
    use_spacy=False,    # 禁用spaCy节省内存
    use_lexicon=True    # 保持领域词典
)
```

### 4. 提取结果不理想
调整参数：
```python
extractor = KGEntityExtractor(
    min_confidence=0.6,      # 提高置信度阈值
    min_entity_length=3,     # 增加最小长度
    use_mmr=True,            # KeyBERT使用最大边缘相关性
    diversity=0.7            # 提高多样性
)
```

## 优化效果预期

与传统NER方法相比，高级提取器可以：
1. **提高实体召回率**：增加30-50%的相关实体
2. **减少虚词提取**：过滤"研究"、"方法"等无意义实体
3. **增强领域相关性**：优先提取计算机学习领域的核心术语
4. **提高语义准确性**：基于上下文理解提取更有意义的实体
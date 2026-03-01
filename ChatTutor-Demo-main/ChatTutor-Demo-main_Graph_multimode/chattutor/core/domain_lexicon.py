"""
计算机学习领域词典模块。

提供计算机科学、机器学习、深度学习等领域的术语白名单，
用于改进知识图谱实体提取。
"""

# 计算机学习领域核心术语词典
# 按类别组织，便于扩展和维护

COMPUTER_SCIENCE_TERMS = {
    # 机器学习基础
    "机器学习": ["监督学习", "无监督学习", "半监督学习", "强化学习",
                "分类", "回归", "聚类", "降维", "特征工程", "特征选择",
                "过拟合", "欠拟合", "偏差", "方差", "正则化", "交叉验证",
                "训练集", "测试集", "验证集", "准确率", "精确率", "召回率",
                "F1分数", "ROC曲线", "AUC", "混淆矩阵", "损失函数", "代价函数",
                "梯度下降", "随机梯度下降", "批量梯度下降", "小批量梯度下降",
                "学习率", "迭代", "epoch", "batch", "优化器", "Adam", "SGD",
                "RMSprop", "动量", "正则化项", "L1正则化", "L2正则化"],

    # 深度学习
    "深度学习": ["神经网络", "人工神经网络", "前馈神经网络", "卷积神经网络",
                "循环神经网络", "长短期记忆网络", "门控循环单元", "自注意力机制",
                "Transformer", "BERT", "GPT", "自编码器", "变分自编码器",
                "生成对抗网络", "深度信念网络", "玻尔兹曼机", "受限玻尔兹曼机",
                "深度强化学习", "Q学习", "深度Q网络", "策略梯度", "演员评论家",
                "激活函数", "Sigmoid", "ReLU", "LeakyReLU", "Tanh", "Softmax",
                "损失函数", "交叉熵", "均方误差", "反向传播", "链式法则", "梯度消失",
                "梯度爆炸", "批量归一化", "层归一化", "Dropout", "残差连接",
                "注意力机制", "多头注意力", "位置编码", "嵌入层", "词嵌入",
                "Word2Vec", "GloVe", "FastText", "预训练模型", "微调"],

    # 自然语言处理
    "自然语言处理": ["词法分析", "句法分析", "语义分析", "词性标注", "命名实体识别",
                    "依存句法分析", "语义角色标注", "情感分析", "文本分类",
                    "文本摘要", "机器翻译", "问答系统", "对话系统", "聊天机器人",
                    "语言模型", "n-gram", "语言生成", "文本生成", "文本相似度",
                    "词向量", "句向量", "文档向量", "主题模型", "LDA", "文本聚类",
                    "信息检索", "信息抽取", "关系抽取", "事件抽取", "知识图谱",
                    "实体链接", "共指消解", "语料库", "停用词", "词干提取", "词形还原"],

    # 计算机视觉
    "计算机视觉": ["图像分类", "目标检测", "语义分割", "实例分割", "图像生成",
                  "图像分割", "边缘检测", "特征提取", "SIFT", "HOG", "卷积核",
                  "池化", "最大池化", "平均池化", "全连接层", "卷积层", "池化层",
                  "上采样", "下采样", "数据增强", "图像增强", "迁移学习",
                  "风格迁移", "超分辨率", "人脸识别", "物体识别", "姿态估计",
                  "光流", "三维重建", "点云", "立体视觉", "相机标定"],

    # 数据科学
    "数据科学": ["数据清洗", "数据预处理", "数据可视化", "探索性数据分析",
                "假设检验", "统计推断", "概率分布", "正态分布", "贝叶斯统计",
                "假设检验", "p值", "置信区间", "相关系数", "线性回归", "逻辑回归",
                "决策树", "随机森林", "梯度提升", "XGBoost", "LightGBM", "CatBoost",
                "支持向量机", "核方法", "核函数", "主成分分析", "t-SNE", "UMAP",
                "聚类算法", "K均值", "层次聚类", "DBSCAN", "关联规则", "Apriori"],

    # 编程与工具
    "编程与工具": ["Python", "NumPy", "Pandas", "Scikit-learn", "TensorFlow",
                  "PyTorch", "Keras", "Jupyter", "Matplotlib", "Seaborn",
                  "SciPy", "NLTK", "spaCy", "HuggingFace", "Transformers",
                  "CUDA", "GPU加速", "分布式训练", "模型部署", "ONNX",
                  "Docker", "Kubernetes", "云计算", "AWS", "Azure", "GCP"],
}

# 同义词映射：用于语义归一化
# 格式: {规范形式: [同义词1, 同义词2, ...]}
SYNONYM_MAPPINGS = {
    # 神经网络相关
    "神经网络": ["人工神经网络", "ANN", "Neural Network", "神经网"],
    "深度学习": ["深度神经网络", "Deep Learning", "深度学习网络"],
    "机器学习": ["ML", "Machine Learning", "机器学"],

    # 模型相关
    "卷积神经网络": ["CNN", "卷积网络", "Convolutional Neural Network"],
    "循环神经网络": ["RNN", "循环网络", "Recurrent Neural Network"],
    "Transformer": ["变换器", "Transformer模型", "自注意力模型"],
    "BERT": ["Bidirectional Encoder Representations from Transformers", "BERT模型"],

    # 算法相关
    "梯度下降": ["Gradient Descent", "梯度下降法"],
    "随机梯度下降": ["SGD", "Stochastic Gradient Descent", "随机梯度下降法"],
    "反向传播": ["Backpropagation", "反向传播算法", "误差反向传播"],

    # 工具框架
    "TensorFlow": ["TF", "TensorFlow框架"],
    "PyTorch": ["PyTorch框架", "Pytorch"],
    "Scikit-learn": ["sklearn", "Scikit Learn", "scikit-learn库"],

    # 概念
    "特征工程": ["特征提取", "特征构造", "Feature Engineering"],
    "数据清洗": ["数据预处理", "数据清理", "Data Cleaning"],
    "数据可视化": ["数据图表", "可视化分析", "Data Visualization"],
}


def get_all_terms() -> list:
    """
    获取所有领域术语的扁平列表。

    Returns:
        所有术语的列表
    """
    all_terms = []
    for category, terms in COMPUTER_SCIENCE_TERMS.items():
        all_terms.extend(terms)
    return all_terms


def get_terms_by_category(category: str) -> list:
    """
    获取特定类别的术语。

    Args:
        category: 类别名称

    Returns:
        该类别的术语列表
    """
    return COMPUTER_SCIENCE_TERMS.get(category, [])


def is_domain_term(term: str) -> bool:
    """
    检查术语是否在领域词典中。

    Args:
        term: 要检查的术语

    Returns:
        如果术语在领域词典中返回True
    """
    all_terms = get_all_terms()
    return term in all_terms


def find_similar_terms(term: str, threshold: float = 0.7) -> list:
    """
    查找与输入术语相似的领域术语（基于字符串相似度）。
    这是一个简单实现，可以替换为更复杂的相似度计算。

    Args:
        term: 输入术语
        threshold: 相似度阈值

    Returns:
        相似术语列表
    """
    import difflib
    all_terms = get_all_terms()
    matches = difflib.get_close_matches(term, all_terms, n=5, cutoff=threshold)
    return matches


class DomainLexicon:
    """
    领域词典类，提供更高级的查询功能。
    """

    def __init__(self):
        self.terms = get_all_terms()
        self.categories = COMPUTER_SCIENCE_TERMS

    def search(self, query: str, category: str = None) -> list:
        """
        搜索领域术语。

        Args:
            query: 搜索查询
            category: 可选，限制搜索类别

        Returns:
            匹配的术语列表
        """
        if category:
            search_space = self.categories.get(category, [])
        else:
            search_space = self.terms

        # 简单实现：包含查询的术语
        matches = [term for term in search_space if query in term]
        return matches

    def categorize_term(self, term: str) -> list:
        """
        获取术语所属的类别。

        Args:
            term: 术语

        Returns:
            类别列表
        """
        categories = []
        for category, terms in self.categories.items():
            if term in terms:
                categories.append(category)
        return categories

    def get_related_terms(self, term: str, max_terms: int = 10) -> list:
        """
        获取相关术语（同一类别中的其他术语）。

        Args:
            term: 输入术语
            max_terms: 最大返回术语数

        Returns:
            相关术语列表
        """
        categories = self.categorize_term(term)
        related = set()

        for category in categories:
            category_terms = self.categories[category]
            # 添加同一类别的其他术语
            for t in category_terms:
                if t != term:
                    related.add(t)
                    if len(related) >= max_terms:
                        break
            if len(related) >= max_terms:
                break

        return list(related)[:max_terms]

    def get_synonyms(self, term: str) -> list:
        """
        获取术语的同义词。

        Args:
            term: 术语

        Returns:
            同义词列表（包括规范形式和所有变体）
        """
        synonyms = []
        for canonical, variants in SYNONYM_MAPPINGS.items():
            if term == canonical or term in variants:
                synonyms.extend([canonical] + variants)
        return list(set(synonyms))

    def get_canonical_form(self, term: str) -> str:
        """
        获取规范形式（如果存在）。

        Args:
            term: 术语

        Returns:
            规范形式，如果不存在则返回原术语
        """
        for canonical, variants in SYNONYM_MAPPINGS.items():
            if term == canonical:
                return canonical
            if term in variants:
                return canonical
        return term  # 没有规范形式，返回原术语
# 支持文本+图像输入的医药多模态问答系统 ()
#OCR需要进行优化


#9.6版本


# # 1) 答案/检索缓存（减少重复计算，命中直返）

# **30 秒速答版**
# 9_6 给检索链路加了**检索缓存**（query 命中直接返回 Top-K），并在**关键事实变更**时清空**生成缓存**，避免“旧答案复用”。结果是**重复问答更快**、**事实改动后更安全**。   

# **2 分钟展开版（Why → How → Result → Check）**

# * **Why：** 高频相同问句会反复检索/重排；而资料更新（如用药/过敏）后若不失效缓存，会“带旧结论”。
# * **How：**

#   1. 在 `_hybrid_search` 先查 **retrieval_cache**，命中则直接返结果；未命中再跑 MMR+BM25 并**写入缓存**。
#   2. 在追加记忆时，如抽到 **profile/medication/allergy** 等关键事实，**清空生成缓存**。  
# * **Result：** 相同问句**响应时间下降**；事实更新后**答案一致性更稳**。
# * **Check：** 记录**缓存命中率/平均耗时**；做“事实变更→再次提问”的一致性抽测。

# ---

# # 2) 降级模式（高负载时只返证据摘要）

# **30 秒速答版**
# 9_6 新增**降级路径**：负载高或受限时不走大模型，只返回**证据摘要 + 来源**，保证“有信息、有出处、可用”。

# **2 分钟展开版（Why → How → Result → Check）**

# * **Why：** 峰值/异常时，端到端生成最脆弱；需要“**最低可用**”策略。
# * **How：** 提供 `_degraded_query`，把前三条证据做**要点压缩**并拼出处，直接作为响应体返回。
# * **Result：** 失败→可用；响应更快；用户仍能**看到来源**与**核心信息**。
# * **Check：** 压测下比较**降级触发率/99p 时延/失败率**；人工抽查证据摘要的**可读性和相关性**。

# ---

# # 3) 检索融合实现（保持 MMR+BM25，但 9_6 加了“检索缓存 + 显式 α/β”）

# **30 秒速答版**
# 两版都用 **MMR + BM25.from_documents**；9_6 在融合前先查**检索缓存**，并显式保留 **α=0.6（语义）/β=0.4（关键词）** 的线性融合权重。  

# **2 分钟展开版（Why → How → Result → Check）**

# * **Why：** 短问更依赖关键词，长问更依赖语义；融合要“兼顾 + 去冗”。
# * **How：**

#   1. MMR 控冗＋多样性；BM25 用 **from_documents** 保 metadata；
#   2. 9_6 在 `_hybrid_search` 首先命中 **retrieval_cache**；未命中再按 **α/β** 线性融合排序取 Top-K。  
# * **Result：** 一样的**可溯源**，但 9_6 对**重复查询**更快。
# * **Check：** 统计**Top-5 覆盖/重复率**与**命中缓存后的时延**；短问/长问分层评测。

# ---

# # 4) 事实变更 → 定向失效（答案更“新”）

# **30 秒速答版**
# 9_6 在保存记忆后，会**抽事实**；若命中“个人信息/用药/过敏”等类型，就**清空生成缓存**，防止引用旧答案。

# **2 分钟展开版（Why → How → Result → Check）**

# * **Why：** 医疗咨询里“姓名/药物/禁忌”一变，历史答案就可能过时。
# * **How：** `_append_memory` 后检查事实类型集，若包含关键类目，执行 **cache clear** 日志化记录。
# * **Result：** **一致性/时效性**提升，减少“沿用旧处方”的风险。
# * **Check：** 做“事实改动回归集”，验证改动后**答案差异率**与**引用更新率**。

# ---

# ## 面试一句话总括（备用）

# > **相对 9.5，9_6** 把**检索与生成做了可缓存**（命中直返），提供**降级模式**保证最低可用，并在**关键事实变更时定向失效缓存**；检索侧依旧是 **MMR + BM25.from_documents + 线性融合（α/β）**，但整体**重复问更快、事实改动更安全**。   





#调取qwen-vl-max模型API进行多模态问答
from collections import deque
import os
import base64
import json
import logging
from typing import List, Dict, Any
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from datasets import load_dataset
import time, threading
import hashlib
from langchain_community.retrievers import BM25Retriever
import math
from langchain_core.documents import Document 
import configparser
import numpy as np
import re
import sys
from tqdm.auto import tqdm
import PyPDF2 
import io
from PIL import Image
import redis
from functools import lru_cache
from datetime import datetime, timedelta

TQDM_OPTS = dict(file=sys.stdout, dynamic_ncols=True, mininterval=0.05, miniters=1)

# 启用 Hugging Face 镜像
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

# ========== 日志设置 ==========
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# --- 统一的 LLM 调用封装（指数回退 + 熔断） ---
_CIRCUIT = {"open_until": 0.0, "fail": 0, "lock": threading.Lock()}

def _circuit_allows():
    with _CIRCUIT["lock"]:
        return time.time() >= _CIRCUIT["open_until"]

def _circuit_record(success: bool):
    with _CIRCUIT["lock"]:
        if success:
            _CIRCUIT["fail"] = 0
        else:
            _CIRCUIT["fail"] += 1
            if _CIRCUIT["fail"] >= 5:
                # 连续失败 5 次，熔断 60s
                _CIRCUIT["open_until"] = time.time() + 60

def _chat_with_retry(llm: ChatOpenAI, messages, **kwargs):
    if not _circuit_allows():
        return "（后端繁忙，已进入短暂保护，请稍后再试）"
    delay = 1.0
    last_err = None
    for attempt in range(Config.LLM_RETRIES):
        try:
            rsp = llm.invoke(messages, **kwargs)
            _circuit_record(True)
            return getattr(rsp, "content", str(rsp))
        except Exception as e:
            last_err = e
            _circuit_record(False)
            if attempt == Config.LLM_RETRIES - 1:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 8.0)
# ========== 配置 ==========
# --- config: 用环境变量接管（支持 .env；若不想装依赖，可以不用 dotenv） ---

# 读取配置文件
def load_config_from_ini(config_file="D:/HUAWEI_project/medical_assistant/project/code/config.ini"):
    config = configparser.ConfigParser()
    config.read(config_file, encoding='utf-8')
    return config

# 加载配置
try:
    ini_config = load_config_from_ini()
except Exception:
    # 如果配置文件不存在或读取失败，使用空配置
    ini_config = configparser.ConfigParser()

class Config:
    # 优先从ini文件读取配置，否则使用环境变量，最后使用默认值
    VECTOR_DB_PATH = ini_config.get('DEFAULT', 'VECTOR_DB_PATH', 
                                   fallback=os.getenv("VECTOR_DB_PATH", "D:/HUAWEI_project/medical_assistant/project/code/datebase/medical_faiss_db"))
    RETRIEVAL_TOP_K = int(ini_config.get('DEFAULT', 'RETRIEVAL_TOP_K', 
                                        fallback=os.getenv("RETRIEVAL_TOP_K", "3")))
    MEMORY_PATH = ini_config.get('DEFAULT', 'MEMORY_PATH', 
                                fallback=os.getenv("MEMORY_PATH", "D:/HUAWEI_project/medical_assistant/project/code/datebase/memory.json"))
    MEMORY_MAX_ENTRIES = int(ini_config.get('DEFAULT', 'MEMORY_MAX_ENTRIES', 
                                           fallback=os.getenv("MEMORY_MAX_ENTRIES", "30")))
     # 新增会话元数据路径配置
    SESSION_META_PATH = ini_config.get('DEFAULT', 'SESSION_META_PATH', 
                                      fallback=os.getenv("SESSION_META_PATH", 
                                      "D:/HUAWEI_project/medical_assistant/project/code/datebase/session_meta.json"))

    # 后端切换：dashscope | local
    BACKEND = ini_config.get('DEFAULT', 'RAG_BACKEND', 
                            fallback=os.getenv("RAG_BACKEND", "dashscope"))
    LLM_BASE_URL = ini_config.get('DEFAULT', 'OPENAI_BASE_URL', 
                                 fallback=os.getenv("OPENAI_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1" if BACKEND == "dashscope" else "http://localhost:8000/v1"
    ))
    LLM_API_KEY = ini_config.get('DEFAULT', 'OPENAI_API_KEY', 
                                fallback=os.getenv("OPENAI_API_KEY", "EMPTY" if BACKEND == "local" else ""))
    LLM_MODEL_NAME = ini_config.get('DEFAULT', 'OPENAI_MODEL', 
                                   fallback=os.getenv("OPENAI_MODEL", "qwen-vl-max" if BACKEND == "dashscope" else "Qwen-VL-Max"))
    LLM_TIMEOUT = int(ini_config.get('DEFAULT', 'RAG_TIMEOUT', 
                                    fallback=os.getenv("RAG_TIMEOUT", "30")))
    LLM_RETRIES = int(ini_config.get('DEFAULT', 'RAG_RETRIES', 
                                    fallback=os.getenv("RAG_RETRIES", "3")))
    
    # Redis 配置
    REDIS_HOST = ini_config.get('REDIS', 'HOST', fallback=os.getenv("REDIS_HOST", "localhost"))
    REDIS_PORT = int(ini_config.get('REDIS', 'PORT', fallback=os.getenv("REDIS_PORT", "6379")))
    REDIS_DB = int(ini_config.get('REDIS', 'DB', fallback=os.getenv("REDIS_DB", "0")))
# ========== 系统Prompt ==========
def get_system_prompt() -> str:
    return """你是一名专业医药助手，基于以下医学知识与图像内容回答问题：
1. 请仅基于知识与图像内容，不要编造信息；
2. 回答中回答中提到具体需要使用的药物需包含药物名称、适应症、禁忌症，但不需要固定回答模板；
3. 如知识库中未包含，请明确说明“知识库中未包含该信息”，但依然给出科学的解释，不得捏造信息；
4. 使用中文回答，保持专业且易懂。
5. 若用户身体不适，需引导用户补充说明自己的病症，以便提供更准确的建议，在获得与病症相关的有效信息的清苦那个下引导在3轮左右，不得超过5轮。在引导用户补充完病症前，不要给出具体的诊断结果或用药建议。
6. 语气温和逻辑清晰，避免大量使用专业术语或复杂句式，让非专业用户也能理解。
7. 用户提供医学信息或图像时，优先基于这些信息回答问题，不得进行编造。
"""

# ========== 简单缓存类 ==========
class RetrievalCache:
    def __init__(self, ttl=300):  # 5分钟TTL
        self.cache = {}
        self.ttl = ttl
    
    def _get_cache_key(self, query: str, filters: dict = None) -> str:
        key_data = {
            "query": query,
            "filters": str(sorted(filters.items())) if filters else ""
        }
        return hashlib.md5(str(key_data).encode()).hexdigest()
    
    def get(self, query: str, filters: dict = None):
        key = self._get_cache_key(query, filters)
        if key in self.cache:
            result, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return result
            else:
                del self.cache[key]
        return None
    
    def set(self, query: str, filters: dict, results: list):
        key = self._get_cache_key(query, filters)
        self.cache[key] = (results, time.time())

# ========== 生成缓存类 ==========
class GenerationCache:
    def __init__(self, short_ttl=300, long_ttl=1800):  # 5分钟和30分钟TTL
        self.cache = {}
        self.short_ttl = short_ttl
        self.long_ttl = long_ttl
    
    def _get_cache_key(self, query: str, evidence_ids: list, system_prompt: str, history_sig: str = "") -> str:
        key_data = {
            "query": query,
            "evidence_ids": sorted(evidence_ids),
            "system_prompt": system_prompt,
            "history_sig": history_sig,  # ★ 新增
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    def get(self, query: str, evidence_ids: list, system_prompt: str, is_complex: bool = False, history_sig: str = ""):
        key = self._get_cache_key(query, evidence_ids, system_prompt, history_sig)
        if key in self.cache:
            result, timestamp, ttl_type = self.cache[key]
            ttl = self.long_ttl if ttl_type == "long" else self.short_ttl
            if time.time() - timestamp < ttl:
                return result
            else:
                del self.cache[key]
        return None

    def set(self, query: str, evidence_ids: list, system_prompt: str, result: dict, is_complex: bool = False, history_sig: str = ""):
        key = self._get_cache_key(query, evidence_ids, system_prompt, history_sig)
        ttl_type = "long" if is_complex else "short"
        self.cache[key] = (result, time.time(), ttl_type)

# ========== RedisMemoryManager类 ==========
class RedisMemoryManager:
    def __init__(self, host=Config.REDIS_HOST, port=Config.REDIS_PORT, db=Config.REDIS_DB):
        self.redis_client = redis.Redis(host=host, port=port, db=db)
        # 添加连接测试
        try:
            self.redis_client.ping()
            logger.info("✅ Redis连接成功")
        except Exception as e:
            logger.error(f"❌ Redis连接失败: {e}")
    
    def save_short_memory(self, session_id: str, turns: list, ttl_sec=3600):
        """
        保存会话短期记忆到Redis
        """
        try:
            payload = json.dumps(turns, ensure_ascii=False)
            self.redis_client.setex(f"chat:{session_id}:recent", ttl_sec, payload)
            logger.info(f"✅ 成功保存会话 {session_id} 的短期记忆到Redis")
        except Exception as e:
            logger.error(f"保存短期记忆到Redis失败: {e}")

    def load_short_memory(self, session_id: str) -> list:
        """
        从Redis加载会话短期记忆
        """
        try:
            value = self.redis_client.get(f"chat:{session_id}:recent")
            if value:
                logger.info(f"✅ 成功从Redis加载会话 {session_id} 的短期记忆")
                return json.loads(value)
            else:
                logger.info(f"ℹ️  Redis中未找到会话 {session_id} 的短期记忆")
                return []
        except Exception as e:
            logger.error(f"从Redis加载短期记忆失败: {e}")
            return []

    def update_session_summary(self, session_id: str, summary: str, ttl_sec=3600):
        """
        更新会话摘要
        """
        try:
            self.redis_client.setex(f"chat:{session_id}:summary", ttl_sec, summary)
            logger.info(f"✅ 成功更新会话 {session_id} 的摘要到Redis")
        except Exception as e:
            logger.error(f"更新会话摘要到Redis失败: {e}")

# ========== FactCard类 ==========
class FactCard:
    def __init__(self, patient_id: str, fact_type: str, fields: Dict[str, Any], source: str):
        self.type = "patient_fact"
        self.patient_id = patient_id
        self.fact_type = fact_type  # 如 "allergy", "medication", "diagnosis"
        self.fields = fields
        self.source = source  # 来源会话ID
        self.ts = datetime.utcnow().isoformat() + "Z"
    
    def to_dict(self):
        return {
            "type": self.type,
            "patient_id": self.patient_id,
            "fact_type": self.fact_type,
            "fields": self.fields,
            "source": self.source,
            "ts": self.ts
        }

# 在文件中添加性能监控类
class PerformanceMonitor:
    def __init__(self, window_size=100):
        self.response_times = deque(maxlen=window_size)
        self.request_count = 0
        self.error_count = 0
        
    def record_response_time(self, response_time: float):
        self.response_times.append(response_time)
        self.request_count += 1
        
    def record_error(self):
        self.error_count += 1
        
    def get_p95_latency(self) -> float:
        if not self.response_times:
            return 0
        sorted_times = sorted(self.response_times)
        index = int(0.95 * len(sorted_times))
        return sorted_times[min(index, len(sorted_times) - 1)]
        
    def should_degrade(self, threshold_ms: int = 5000) -> bool:
        """判断是否需要降级"""
        if len(self.response_times) < 10:  # 至少需要10个样本
            return False
        return self.get_p95_latency() > threshold_ms

# ========== 主类 ==========
class MedRAGAscend:
    def __init__(self):
        logger.info("🚀 初始化医药多模态系统 (qwen-vl-max via DashScope API) ...")

        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"}
        )

        # 使用 DashScope 的 OpenAI 兼容接口
        self.llm = ChatOpenAI(
            model=Config.LLM_MODEL_NAME,
            base_url=Config.LLM_BASE_URL,
            api_key=Config.LLM_API_KEY,
            temperature=0.1,
            max_tokens=512,
            timeout=Config.LLM_TIMEOUT,
            max_retries=Config.LLM_RETRIES,
        )

        # 初始化 Redis 管理器
        self.redis_manager = RedisMemoryManager()
         # 初始化事实提取器
        self.fact_extractor = self._init_fact_extractor()

        # 初始化缓存
        self.retrieval_cache = RetrievalCache()
        # 初始化生成缓存
        self.generation_cache = GenerationCache()
        # 初始化性能监控
        self.perf_monitor = PerformanceMonitor()

        # 新增会话管理属性
        self.session_id = None# 会话ID
        self.session_summary = ""# 会话摘要
        self.session_meta = self._load_session_meta()# 会话元数据
        self.previous_session_id = None# 上一个会话ID
        self.previous_session_needs_rename = False# 上一个会话是否需要重命名

        # 初始化向量数据库，用于存储和检索医学知识
        self.vectorstore = self._load_or_create_vectorstore()
        # 创建一个检索器，设置检索参数，最多返回top_k个相关文档
        # 创建一个混合检索器，替换原来的 retriever
        self._hybrid_search = self._build_hybrid_retriever()
        # 获取系统提示信息，定义模型的行为和回答规范
        self.system_prompt = get_system_prompt()

        # 设置记忆文件路径和最大记忆条目数
        self.memory_path = Config.MEMORY_PATH
        self.memory_max = Config.MEMORY_MAX_ENTRIES
        # 加载历史对话记忆，用于上下文理解和连续对话
        self.memory = self._load_memory()
        # 尝试初始化交叉编码器，用于更精细的文档重排序
        self._try_init_cross_encoder()

        self.log_path = "logs/rag.jsonl"# 对话日志文件
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)# 创建日志目录

        logger.info("✅ 系统初始化完成（使用 Qwen-VL 远程 API）。")

# ========= 结构化日志 ==========
    def _log_event(self, event: dict):
        """记录事件到结构化日志"""
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

# ========= 数据加载与处理 ==========
    def _hash_text(self, s: str) -> str:
        return hashlib.md5(s.strip().encode("utf-8")).hexdigest()

    # 添加PDF文本提取方法
    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        从PDF文件中提取文本内容
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            提取的文本内容
        """
        try:
            text = ""
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logger.error(f"❌ PDF文件处理失败 {pdf_path}: {e}")
            return ""
        
    # 添加文本行转纯文本方法
    def _row_to_text(self, row):
        """将 HuggingFace 数据集的一条记录转成可检索的纯文本"""
        if not isinstance(row, dict):
            try:
                row = dict(row)
            except Exception:
                return None
        # 常见字段
        if isinstance(row.get("text"), str):
            return row["text"]
        if "instruction" in row and "output" in row:
            return f"问：{row['instruction']}\n答：{row['output']}"
        if "messages" in row and isinstance(row["messages"], list):
            return "\n".join(f"{m.get('role','user')}：{m.get('content','')}" for m in row["messages"])
        # 兜底：拼所有字符串字段
        parts = [str(v) for v in row.values() if isinstance(v, str)]
        return "\n".join(parts) if parts else None

# 创建一个函数，用于从HuggingFace数据集与本地存储中加载数据
    def _build_documents_from_hf(self) -> list:
        docs = []
        
        # 1. 加载HuggingFace数据集
        datasets_to_load = [
            ("FreedomIntelligence/TCM-Instruction-Tuning-ShizhenGPT", "1.TCM_text_instruction"),
            ("FreedomIntelligence/TCM-Instruction-Tuning-ShizhenGPT", "2.TCM_vision_instruction"),
            ("FreedomIntelligence/TCM-Instruction-Tuning-ShizhenGPT", "3.TCM_speech_instruction")
        ]
        
        for dataset_name, config_name in datasets_to_load:
            try:
                ds = load_dataset(dataset_name, config_name)

                # 用 _row_to_text 把每条样本转成纯文本
                pairs = []  # (idx, text)
                for i, row in enumerate(ds["train"]):
                    t = self._row_to_text(row)
                    if t:
                        pairs.append((i, t))

                # 去重（按整条原文 md5）
                seen, uniq = set(), []
                for i, t in pairs:
                    h = self._hash_text(t)
                    if h not in seen:
                        seen.add(h)
                        uniq.append((i, t))
                splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=60)
                # 为数据集处理添加进度条
                pbar = tqdm(uniq, desc=f"处理数据集 {dataset_name}/{config_name}", unit="条目", **TQDM_OPTS)
                for i, t in pbar:  # 正确使用进度条迭代
                    for chunk in splitter.split_text(t):
                        docs.append(Document(page_content=chunk, metadata={
                            "source": f"dataset://{dataset_name}/{config_name}#{i}",
                            "section": "",
                            "version": "v1"
                        }))
                logger.info(f"✅ 成功加载数据集: {dataset_name}/{config_name}")
            except Exception as e:
                logger.warning(f"⚠️ 加载数据集失败 {dataset_name}/{config_name}: {e}")
        
        # 2. 加载本地文件
        local_files = [
            "D:/HUAWEI_project/medical_assistant/project/code/book/02.中医诊断学_第10版.pdf"
        ]
        
        # 为文件处理添加进度条
        for file_path in tqdm(local_files, desc="处理本地文件", unit="文件", **TQDM_OPTS):
            try:
                if os.path.exists(file_path):
                    # 根据文件扩展名处理不同类型的文件
                    if file_path.lower().endswith('.pdf'):
                        # 处理PDF文件
                        content = self._extract_text_from_pdf(file_path)
                    else:
                        # 处理文本文件
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                    
                    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=60)
                    chunks = splitter.split_text(content)
                    # 为文件分块处理添加进度条
                    for i, chunk in enumerate(tqdm(chunks, desc=f"分块处理 {os.path.basename(file_path)}", unit="块", leave=False, **TQDM_OPTS)):
                        docs.append(Document(page_content=chunk, metadata={
                            "source": f"file://{file_path}#{i}",
                            "section": "",
                            "version": "local"
                        }))
                    logger.info(f"✅ 成功加载本地文件: {file_path}")
                else:
                    logger.warning(f"⚠️ 本地文件不存在: {file_path}")
            except Exception as e:
                logger.error(f"❌ 加载本地文件失败 {file_path}: {e}")
        
        return docs
    # ========= 向量库 ==========
    def _load_or_create_vectorstore(self) -> FAISS:
        if os.path.exists(Config.VECTOR_DB_PATH):
            logger.info("📚 加载已有 FAISS 知识库...")
            return FAISS.load_local(
                Config.VECTOR_DB_PATH,
                self.embeddings,
                allow_dangerous_deserialization=True  # 添加此参数
            )

        logger.info("📘 创建新的医学知识库...")
        docs = self._build_documents_from_hf()
        # 为向量化过程添加进度条
        logger.info("🔄 开始向量化文档...")
        docs_list = list(docs)  # 明确计算长度，供进度条显示

        # 仅用于“显示”进度，不改变你的向量化方式
        for _ in tqdm(range(len(docs_list)), desc="向量化文档", unit="文档", **TQDM_OPTS):
            pass
        store = FAISS.from_documents(docs_list, self.embeddings)
        store.save_local(Config.VECTOR_DB_PATH)
        logger.info("✅ 医学知识库已保存。")
        return store
    
    def _build_hybrid_retriever(self):
        # 1) 基于已有向量库创建 MMR 检索器（先取大一点的 fetch_k，再去重压缩到 k）
        vec_retriever_mmr = self.vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={"k": max(4, Config.RETRIEVAL_TOP_K), "fetch_k": 32, "lambda_mult": 0.5}
        )
        # 2) BM25 基于原始文档（可缓存 doc 列表），这里简单取向量库的"反索引"文本
        #    如果你有原始全量文档列表，替换为那个列表更好
        # 2) BM25：直接用 Document 构建，保留 metadata
        all_docs = list(self.vectorstore.docstore._dict.values())
        bm25 = BM25Retriever.from_documents(all_docs)   # ✅ 不要 from_texts
        bm25.k = max(4, Config.RETRIEVAL_TOP_K)


        # 在 _build_hybrid_retriever 方法中修改 _hybrid_search 函数
        def _hybrid_search(query: str):
            # 检查检索缓存
            cached_results = self.retrieval_cache.get(query)
            if cached_results:
                logger.info("命中检索缓存")
                return cached_results

            a = vec_retriever_mmr.invoke(query)  # 向量MMR结果
            b = bm25.invoke(query)               # 关键词BM25结果

            # 构建 scored 映射：doc -> (doc, vector_score, bm25_score)
            scored = {}

            # 假设每个文档可以用其 page_content 作为唯一标识（或使用 hash）
            alpha, beta = 0.6, 0.4  # 可调权重参数

            # 分别为向量和BM25的结果赋初始分数
            for doc in a:
                key = doc.page_content
                if key not in scored:
                    scored[key] = [doc, 0.0, 0.0]
                scored[key][1] += 1.0  # 简单计数代替真实相似度

            for doc in b:
                key = doc.page_content
                if key not in scored:
                    scored[key] = [doc, 0.0, 0.0]
                scored[key][2] += 1.0  # BM25得分简易模拟

            # 融合排序
            fused = sorted(scored.values(), key=lambda x: (alpha * x[1] + beta * x[2]), reverse=True)

            results = [x[0] for x in fused[:Config.RETRIEVAL_TOP_K]]

            # 缓存结果
            self.retrieval_cache.set(query, None, results)

            return results

        return _hybrid_search
    
# ======== 事实卡片 ==========
    def _init_fact_extractor(self):
        """
        初始化事实提取器（可以是简单的规则或小型模型）
        """
        # 这里可以实现一个简单的规则引擎或者使用小型模型来提取事实
        pass
# ======== 事实提取与保存 ==========
    def _extract_facts(self, user_input: str, assistant_response: str) -> List[FactCard]:
        """
        从对话中抽取可复用的事实卡片：
        - profile：姓名
        - medication：药物（名称/剂量/频次/用法）
        - allergy：过敏（致敏原/描述）
        - adverse_event：不良反应
        - risk_factor：风险因素（孕期/肾功能等）
        """
        facts: List[FactCard] = []
        text = f"{user_input or ''}\n{assistant_response or ''}"

        # —— 基础正则库 ——
        name_pat = re.compile(r"(?:我叫|我的名字是)\s*([A-Za-z0-9_\u4e00-\u9fa5]{1,20})")
        # 常见药物词表可自行扩充
        drug_terms = [
            "阿莫西林", "阿莫西林克拉维酸", "阿奇霉素", "头孢", "头孢克肟", "左氧氟沙星", "莫西沙星",
            "布洛芬", "对乙酰氨基酚", "洛索洛芬", "头孢呋辛", "克拉霉素"
        ]
        drug_pat = re.compile(r"(" + "|".join(map(re.escape, drug_terms)) + r")")
        dose_pat = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|g|μg|ml|mL|片|粒|袋)", re.IGNORECASE)
        freq_pat = re.compile(
            r"(?:一日|每天|每日)\s*(\d+)\s*次|"
            r"(?:每\s*(\d+)\s*(小时|h|天|d))|"
            r"(?:q(\d+)h)|\b(bid|tid|qid)\b|"
            r"(\d+)\s*次/日", re.IGNORECASE
        )
        route_pat = re.compile(r"(口服|po|静脉|iv|肌注|im|外用)", re.IGNORECASE)

        # 过敏：提取致敏原与上下文描述
        allergen_terms = [
            "青霉素", "阿莫西林", "头孢", "花生", "海鲜", "尘螨", "鸡蛋", "牛奶", "贝类", "花粉", "酒精", "对比剂"
        ]
        allergen_pat = re.compile(r"(?:对)?\s*(" + "|".join(map(re.escape, allergen_terms)) + r")\s*过敏")
        allergy_hit_pat = re.compile(r"(过敏|过敏史|过敏反应)")

        # 不良反应/症状（可作提醒）
        ae_pat = re.compile(r"(皮疹|瘙痒|荨麻疹|腹泻|恶心|呕吐|呼吸困难|喉头水肿|休克|眩晕|胃痛)")
        # 风险因素（示例：孕期/肾功能异常）
        risk_pat = re.compile(r"(怀孕|孕|妊娠|备孕|哺乳|肾功能不全|肾衰|肾病|肌酐升高|GFR\s*\d+)")

        # —— 工具：句子切分与去重 —— 
        def split_sents(t: str) -> List[str]:
            return [s.strip() for s in re.split(r"[。；;.!?\n]+", t) if s.strip()]

        seen = set()
        def add_fact(ftype: str, fields: Dict[str, Any]):
            # 去重键：类型+字段内容
            key = f"{ftype}:{json.dumps(fields, sort_keys=True, ensure_ascii=False)}"
            if key in seen:
                return
            seen.add(key)
            facts.append(FactCard(
                patient_id=self.session_id,
                fact_type=ftype,
                fields=fields,
                source=f"chat://{self.session_id}"
            ))

        sents = split_sents(text)

        # —— 1) 姓名抽取（优先从用户输入） ——
        name_src = user_input or text
        m_name = name_pat.search(name_src)
        if m_name:
            add_fact("profile", {"name": m_name.group(1)})

        # —— 2) 药物相关抽取（逐句扫描：命中药名→就近抽取剂量/频次/用法） ——
        for s in sents:
            m_drug = drug_pat.search(s)
            if not m_drug:
                continue
            drug = m_drug.group(1)
            dose = None
            freq = None
            route = None

            m_dose = dose_pat.search(s)
            if m_dose:
                dose = f"{m_dose.group(1)}{m_dose.group(2)}"

            m_freq = freq_pat.search(s)
            if m_freq:
                # 归一化频次表达
                if m_freq.group(1):  # 一日/每天/每日 X 次
                    freq = f"每日{m_freq.group(1)}次"
                elif m_freq.group(2) and m_freq.group(3):  # 每 X 小时/天
                    freq = f"每{m_freq.group(2)}{m_freq.group(3)}"
                elif m_freq.group(4):  # qXh
                    freq = f"q{m_freq.group(4)}h"
                elif m_freq.group(5):  # bid/tid/qid
                    freq = m_freq.group(5).lower()
                elif m_freq.group(6):  # X次/日
                    freq = f"每日{m_freq.group(6)}次"

            m_route = route_pat.search(s)
            if m_route:
                route = m_route.group(1).lower().replace("po", "口服").replace("iv", "静脉").replace("im", "肌注")

            fields = {"name": drug}
            if dose: fields["dosage"] = dose
            if freq: fields["frequency"] = freq
            if route: fields["route"] = route
            fields["context"] = s[:120]
            add_fact("medication", fields)

        # —— 3) 过敏抽取（致敏原 + 描述） ——
        if allergy_hit_pat.search(text) or "过敏" in text:
            allergens = set(a.group(1) for a in allergen_pat.finditer(text))
            # 取含“过敏”的代表性句子做描述
            allergy_sents = [s for s in sents if "过敏" in s][:2]
            fields = {}
            if allergens:
                fields["allergens"] = list(allergens)
            if allergy_sents:
                fields["description"] = "；".join(allergy_sents)[:200]
            if fields:
                add_fact("allergy", fields)

        # —— 4) 不良反应（AE） —— 
        for s in sents:
            m_ae = ae_pat.search(s)
            if m_ae:
                add_fact("adverse_event", {"event": m_ae.group(1), "description": s[:160]})

        # —— 5) 风险因素（孕期/肾功能等） —— 
        for s in sents:
            m_r = risk_pat.search(s)
            if m_r:
                add_fact("risk_factor", {"factor": m_r.group(1), "description": s[:160]})

        return facts


# 保存事实卡片的方法
    def _save_fact_card(self, fact_card: FactCard):
        """
        保存事实卡片到向量库和结构化数据库
        这里只是示例，实际实现需要根据你的向量库和数据库选择来实现
        """
        try:
            # 保存到向量库用于语义检索（示例使用FAISS）
            # 这需要根据实际情况实现
            
            # 保存到结构化数据库的逻辑也需要根据你选择的数据库来实现
            logger.info(f"保存事实卡片: {fact_card.fact_type}")
        except Exception as e:
            logger.error(f"保存事实卡片失败: {e}")


    # ========= 记忆管理 ==========
    # 修改记忆加载方法以支持会话
    def _load_memory(self) -> List[Dict[str, Any]]:
        """加载当前会话的记忆"""
        if not self.session_id:
            return []
        
        # 优先从 Redis 加载短期记忆
        try:
            memory = self.redis_manager.load_short_memory(self.session_id)
            if memory:
                return memory
        except Exception as e:
            logger.warning(f"从Redis加载记忆失败，回退到文件存储: {e}")
        
        # 回退到文件存储
        session_memory_path = f"{Config.MEMORY_PATH}.{self.session_id}"
        if not os.path.exists(session_memory_path):
            logger.info(f"🧠 会话 {self.session_id} 无历史记录，初始化为空记忆。")
            return []
        try:
            with open(session_memory_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data[-self.memory_max:] if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"🧠 读取会话 {self.session_id} 记忆文件失败：{e}")
            return []


    # 修改记忆保存方法以支持会话
    def _save_memory(self):
        """保存当前会话的记忆"""
        if not self.session_id:
            logger.warning("⚠️  未设置会话ID，无法保存记忆")
            return
        
        # 保存到 Redis 短期记忆
        try:
            to_save = self.memory[-self.memory_max:]
            self.redis_manager.save_short_memory(self.session_id, to_save)
        except Exception as e:
            logger.error(f"保存记忆到Redis失败: {e}")
        
        # 同时保存到文件作为备份
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
            
            to_save = self.memory[-self.memory_max:]
            with open(self.memory_path, "w", encoding="utf-8") as f:
                json.dump(to_save, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"🧠 保存记忆到文件失败：{e}")

    # 修改添加记忆的方法
    def _append_memory(self, user_text: str, assistant_text: str, has_image: bool = False, 
                   image_meta: str = None, thumbnail_data: str = None):
        """为当前会话添加记忆"""
        if not self.session_id:
            logger.warning("⚠️  未设置会话ID，无法添加记忆")
            return
            
        entry = {
            "user": {
                "text": user_text, 
                "has_image": bool(has_image), 
                "image_meta": image_meta or "",
                "thumbnail": thumbnail_data or ""
            },
            "assistant": {"text": assistant_text}
        }
        self.memory.append(entry)
        self.memory = self.memory[-self.memory_max:]
        self._save_memory()
        
        # 提取并保存事实卡片
        facts = self._extract_facts(user_text, assistant_text)
        for fact in facts:
            self._save_fact_card(fact)

        # 在 _append_memory 的末尾
        try:
            if any(f.fact_type in {"profile", "medication", "allergy"} for f in facts):
                # 关键个人/用药信息变化，清理生成缓存，避免沿用旧答案
                self.generation_cache.cache.clear()
                logger.info("关键事实变更，已清空生成缓存")
        except Exception:
            pass


    # 修改 _memory_to_messages 方法，添加缩略图信息
    def _memory_to_messages(self) -> List[Dict[str, Any]]:
        msgs = []
        for entry in self.memory:
            u = entry.get("user", {})
            user_text = u.get("text", "")
            if u.get("has_image", False):
                user_text += f"\n（历史对话中包含图像）"
                # 如果有缩略图，可以在这里添加相关信息
                if u.get("thumbnail", ""):
                    user_text += "[包含可访问的图像内容]"
            msgs.append({"role": "user", "content": user_text})
            msgs.append({"role": "assistant", "content": entry.get("assistant", {}).get("text", "")})
        return msgs
    
    def _try_init_cross_encoder(self):
        try:
            from sentence_transformers import CrossEncoder
            # 体量适中的重排器（可换 bge-reranker-base）
            self._ce = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            self._use_ce = True
        except Exception:
            # 无法安装/加载就用退化版：向量平均相似度重排
            self._ce = None
            self._use_ce = False

    def _rerank(self, query: str, docs: list, top_n: int = None):
        if top_n is None:
            top_n = Config.RETRIEVAL_TOP_K
        if not docs:
            return []
        if self._use_ce and len(docs) > top_n:
            pairs = [[query, d.page_content] for d in docs]
            scores = self._ce.predict(pairs)  # 越大越相关
            order = np.argsort(-scores)
            docs = [docs[i] for i in order[:top_n]]
        else:
            # 退化重排：用嵌入相似度粗排
            try:
                q_vec = self.embeddings.embed_query(query)
                d_vecs = [self.embeddings.embed_query(d.page_content[:400]) for d in docs]
                sims = [np.dot(q_vec, dv)/(np.linalg.norm(q_vec)*np.linalg.norm(dv)+1e-9) for dv in d_vecs]
                order = np.argsort(-np.array(sims))
                docs = [docs[i] for i in order[:top_n]]
            except Exception:
                docs = docs[:top_n]
        return docs
    # ========= 证据条目压缩：保留关键句 =========

    _NEG = re.compile(r"(不宜|禁用|不得|禁止|避免|不推荐|禁忌)")
    _NUM = re.compile(r"(\d+(\.\d+)?\s?(mg|μg|IU|mmol/L|ml|kg|g|次/日|每日|q\d?h|bid|tid|q\d?d))", re.I)

    def _bullet_compress(self, text: str, max_chars: int = 280) -> str:
        """
        规则：优先保留含"禁忌/不宜/不得"等否定词，或含剂量/单位/频次的句子
        不足再补首句。尽量压到 max_chars。
        """
        sents = re.split(r"[。；;.!?]\s*", text.strip())
        picks = []
        for s in sents:
            if not s: 
                continue
            if self._NEG.search(s) or self._NUM.search(s):
                picks.append(s)
        if not picks and sents:
            picks.append(sents[0])
        out = "；".join(picks)
        return (out[:max_chars] + "…") if len(out) > max_chars else out
    
    # ========= 简易预算管理：先放高优先级，超预算就裁证据摘要 =========
    def _assemble_with_budget(self, system_prompt: str, facts_json: str, question: str,
                            evidence_docs: list, history_sel: list, budget_chars: int = 6000):
        """
        把提示分块拼起来：系统提示 > 关键事实 > 当前问题 > 证据条目 > 会话摘要
        超预算时先裁证据条目，再裁会话摘要；系统+事实永不裁。
        """
        # 关键事实（第6步的 JSON 模式里我们会用）
        hist_text = "\n".join([f"{h['role']}: {h['content']}" for h in history_sel])
        # 压缩证据为条目
        ev_bullets = []
        for d in evidence_docs:
            ev_bullets.append(f"- {d.metadata.get('source','unknown')}: {self._bullet_compress(d.page_content)}")
        ev_text = "\n".join(ev_bullets)

        parts = [
            ("SYSTEM", system_prompt),
            ("FACTS", facts_json or ""),
            ("QUESTION", question),
            ("EVIDENCE", ev_text),
            ("HISTORY", hist_text),
        ]
        joined = ""
        for name, block in parts:
            if not block: 
                continue
            candidate = joined + f"\n\n## {name}\n{block}"
            if len(candidate) <= budget_chars or name in ("SYSTEM","FACTS","QUESTION"):
                joined = candidate
            else:
                # 超预算：证据优先裁，最后才裁历史
                if name == "EVIDENCE":
                    # 留前 N 条证据
                    lines = ev_text.splitlines()
                    keep = max(3, int(len(lines)*0.5))
                    ev_text_short = "\n".join(lines[:keep] + ["- ……"])
                    candidate2 = joined + f"\n\n## {name}\n{ev_text_short}"
                    if len(candidate2) <= budget_chars:
                        joined = candidate2
                        continue
                # 历史也裁掉
                if name == "HISTORY":
                    lines = hist_text.splitlines()
                    keep = min(6, len(lines))
                    hist_short = "\n".join(lines[-keep:])
                    candidate3 = joined + f"\n\n## {name}\n{hist_short}"
                    if len(candidate3) <= budget_chars:
                        joined = candidate3
                    # 超了就不加 HISTORY 了
        return joined
    
    # ========= 会话历史选择（先选再压） =========
    def _select_history(self, query: str, history: list, keep_recent: int = 2, top_sim: int = 6):
        """
        history: [{'role':'user'|'assistant', 'content': '...'}, ...]
        返回：保留靠后的 keep_recent 条 + 与当前问题最相似的 top_sim 条（去重）
        """
        if not history:
            return []
        recent = history[-keep_recent:] if len(history) > keep_recent else history[:]
        # 余下做相似度
        rest = history[:-keep_recent] if len(history) > keep_recent else []
        try:
            q = self.embeddings.embed_query(query)
            scored = []
            for h in rest:
                t = h.get("content","")
                if not t: 
                    continue
                v = self.embeddings.embed_query(t[:400])
                sim = np.dot(q, v) / (np.linalg.norm(q)*np.linalg.norm(v) + 1e-9)
                scored.append((sim, h))
            scored.sort(key=lambda x: x[0], reverse=True)
            picked = [h for _, h in scored[:top_sim]]
        except Exception:
            picked = rest[:top_sim]
        # 合并 + 去重（按内容）
        seen, out = set(), []
        for h in (picked + recent):
            c = h.get("content","").strip()
            if c and c not in seen:
                seen.add(c)
                out.append(h)
        return out
    
    # 更稳健的历史选择
    def _select_history_smart(self, query: str, history: list,
                            keep_recent_pairs: int = 3, top_sim: int = 6, hard_keywords: list = None):
        if not history:
            return []
        if hard_keywords is None:
            hard_keywords = ["我叫", "名字", "阿莫西林", "过敏", "剂量", "几次", "多久一次"]

        # 分“问答对”
        pairs, buf = [], []
        for msg in history:
            buf.append(msg)
            if len(buf) == 2:
                pairs.append(buf); buf = []
        if buf: pairs.append(buf)

        # 最近 N 轮问答对
        recent_pairs = pairs[-keep_recent_pairs:] if len(pairs) >= keep_recent_pairs else pairs[:]
        recent_msgs = [m for p in recent_pairs for m in p]

        # 相似度挑选（排除最近）
        rest_msgs = history[:-len(recent_msgs)] if len(history) > len(recent_msgs) else []
        picked_sim = []
        try:
            q = self.embeddings.embed_query(query)
            scored = []
            for h in rest_msgs:
                t = h.get("content",""); 
                if not t: continue
                v = self.embeddings.embed_query(t[:400])
                sim = np.dot(q, v) / (np.linalg.norm(q)*np.linalg.norm(v)+1e-9)
                scored.append((sim, h))
            scored.sort(key=lambda x: x[0], reverse=True)
            picked_sim = [h for _, h in scored[:top_sim]]
        except Exception:
            picked_sim = rest_msgs[:top_sim]

        # 关键事实强保
        hard_hits = [h for h in history if any(k in h.get("content","") for k in hard_keywords)]

        # 引用型问题：加大最近保留
        if re.search(r"(刚刚|上次|之前|前面|我叫什么|我是谁|我问的|那个药|前一个问题)", query):
            extra_pairs = pairs[-(keep_recent_pairs+3):]
            recent_msgs = [m for p in extra_pairs for m in p]

        # 合并去重 + 简单预算
        out, seen = [], set()
        for group in [recent_msgs, picked_sim, hard_hits]:
            for h in group:
                c = h.get("content","").strip()
                if c and c not in seen:
                    seen.add(c); out.append(h)

        budget, total, trimmed = 3000, 0, []
        for h in out[::-1]:
            c = h.get("content","")
            if total + len(c) <= budget:
                trimmed.append(h); total += len(c)
            else:
                break
        return list(reversed(trimmed))


    
    # 添加图片处理相关常量
    MAX_IMG_BYTES = 2 * 1024 * 1024  # 2MB
    
    def _downscale_bytes(self, img_bytes: bytes, max_side: int = 1600, quality: int = 85) -> bytes:
        """
        压缩图片到指定尺寸和质量
        
        Args:
            img_bytes: 原始图片的字节数据
            max_side: 最大边长
            quality: JPEG质量 (1-100)
            
        Returns:
            压缩后的图片字节数据
        """
        try:
            # 打开图片
            image = Image.open(io.BytesIO(img_bytes))
            
            # 转换RGBA模式为RGB（JPEG不支持透明度）
            if image.mode in ('RGBA', 'LA', 'P'):
                # 创建白色背景
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
                image = background
            
            # 等比缩放
            image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            
            # 保存为JPEG格式
            buf = io.BytesIO()
            image.save(buf, format="JPEG", quality=quality, optimize=True)
            return buf.getvalue()
        except Exception as e:
            logger.warning(f"图片压缩失败: {e}")
            return img_bytes  # 压缩失败时返回原始数据
    
    def _prepare_image_b64(self, img_bytes: bytes) -> tuple[str, str]:
        # 如果图片过大，先压缩
        if len(img_bytes) > self.MAX_IMG_BYTES:
            logger.info(f"图片大小 {len(img_bytes)} bytes 超过限制，进行压缩...")
            img_bytes = self._downscale_bytes(img_bytes)
            logger.info(f"压缩后图片大小: {len(img_bytes)} bytes")
        
        # 使用PIL检测图片格式
        try:
            image = Image.open(io.BytesIO(img_bytes))
            img_format = image.format.lower() if image.format else "jpeg"
        except Exception:
            logger.warning("无法检测图片格式，使用默认JPEG格式")
            img_format = "jpeg"
        
        # 标准化格式名称
        mime_type_map = {
            'jpeg': 'jpeg',
            'jpg': 'jpeg',
            'png': 'png',
            'gif': 'gif',
            'webp': 'webp',
            'bmp': 'bmp'
        }
        
        mime_type = mime_type_map.get(img_format, 'jpeg')
        data_uri = f"data:image/{mime_type};base64," + base64.b64encode(img_bytes).decode()
        
        return data_uri, mime_type
    
     # 添加缩略图相关常量
    THUMBNAIL_MAX_SIDE = 300  # 缩略图最大边长
    THUMBNAIL_QUALITY = 60    # 缩略图质量
    
    def _create_thumbnail(self, img_bytes: bytes) -> str:
        """
        创建图片缩略图并返回base64编码
        
        Args:
            img_bytes: 原始图片的字节数据
            
        Returns:
            str: 缩略图的base64编码
        """
        try:
            # 确保输入是bytes类型
            if not isinstance(img_bytes, bytes):
                if hasattr(img_bytes, 'read'):
                    # 如果是文件对象，读取内容
                    img_bytes = img_bytes.read()
                else:
                    img_bytes = bytes(img_bytes)
            
            # 验证数据有效性
            if not img_bytes or len(img_bytes) == 0:
                logger.warning("图片数据为空")
                return ""
            
            # 打开图片
            image = Image.open(io.BytesIO(img_bytes))
            
            # 验证图片格式
            if not image:
                logger.warning("无法打开图片")
                return ""
            
            # 转换RGBA模式为RGB（JPEG不支持透明度）
            if image.mode in ('RGBA', 'LA', 'P'):
                # 创建白色背景
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
                image = background
            elif image.mode != 'RGB':
                # 其他模式也转换为RGB
                image = image.convert('RGB')
            
            # 创建缩略图
            image.thumbnail((self.THUMBNAIL_MAX_SIDE, self.THUMBNAIL_MAX_SIDE), Image.Resampling.LANCZOS)
            
            # 保存为JPEG格式
            buf = io.BytesIO()
            image.save(buf, format="JPEG", quality=self.THUMBNAIL_QUALITY, optimize=True)
            
            # 返回base64编码
            return base64.b64encode(buf.getvalue()).decode()
        except Exception as e:
            logger.warning(f"创建缩略图失败: {e}")
            return ""  # 创建失败时返回空字符串


     #OCR功能集成
    def _perform_ocr(self, img_bytes: bytes) -> str:
        """
        对图片执行OCR识别
        
        Args:
            img_bytes: 图片字节数据
            
        Returns:
            str: OCR识别出的文本内容
        """
        # 检查OCR依赖是否可用
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            logger.warning("OCR依赖未安装，跳过OCR处理")
            return ""
        
        try:
            # 使用PIL打开图片
            image = Image.open(io.BytesIO(img_bytes))
            
            # 执行OCR识别，支持中英文
            text = pytesseract.image_to_string(image, lang="eng+chi_sim")
            
            # 清理文本，移除多余的空白行
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            cleaned_text = "\n".join(lines)
            
            logger.info(f"OCR识别完成，提取到 {len(lines)} 行文本")
            return cleaned_text
        except Exception as e:
            logger.warning(f"OCR处理失败: {e}")
            return ""
        
    #图片类型判断
    def _is_text_image(self, ocr_text: str, img_bytes: bytes) -> bool:
        """
        判断是否为纯文本图片
        
        Args:
            ocr_text: OCR识别的文本
            img_bytes: 图片字节数据
            
        Returns:
            bool: 是否为纯文本图片
        """
        if not ocr_text:
            return False
        
        # 基于OCR文本长度和行数判断
        lines = ocr_text.splitlines()
        
        # 如果文本行数较多，认为是文本图片
        if len(lines) > 3:
            return True
        
        # 如果文本总长度较长，也认为是文本图片
        if len(ocr_text) > 100:
            return True
            
        return False

    # 添加处理进度显示方法
    def _show_processing_progress(self, stage: int, total_stages: int = 2):
        """显示处理进度"""
        stages = ["初步分析", "详细回答"]
        if stage <= len(stages):
            print(f"🔍 第{stage}阶段：正在{stages[stage-1]}...")
    # 添加处理时间预估方法
    def _estimate_processing_time(self, docs_count: int) -> int:
        """预估处理时间(秒)"""
        # 基于文档数量预估时间
        return max(2, min(docs_count // 2, 8))  # 最少2秒，最多8秒

    # 添加会话元数据管理方法
    def _load_session_meta(self) -> Dict[str, Any]:
        """加载会话元数据"""
        if not os.path.exists(Config.SESSION_META_PATH):
            return {}
        try:
            with open(Config.SESSION_META_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"🧠 读取会话元数据失败：{e}")
            return {}

    def _save_session_meta(self):
        """保存会话元数据"""
        try:
            with open(Config.SESSION_META_PATH, "w", encoding="utf-8") as f:
                json.dump(self.session_meta, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"🧠 保存会话元数据失败：{e}")

    def _generate_session_summary(self, first_question: str) -> str:
        """生成会话主题摘要"""
        try:
            # 使用LLM生成会话主题
            summary_prompt = f"请为以下医药咨询问题生成一个简短的主题摘要（不超过10个字）：\n\n问题：{first_question}"
            messages = [
                {"role": "system", "content": "你是一个专业的医药助手，请为用户的问题生成简洁准确的主题摘要。"},
                {"role": "user", "content": summary_prompt}
            ]
            summary = _chat_with_retry(self.llm, messages)
            return summary.strip()[:20]  # 限制长度
        except Exception as e:
            logger.warning(f"生成会话摘要失败，使用默认摘要: {e}")
            # 提取问题的前10个字符作为默认摘要
            return first_question[:10] + "..." if len(first_question) > 10 else first_question

#创建新会话
    def _create_new_session(self, first_question: str = "") -> str:
        """创建新会话"""
        # 如果当前会话是"新对话"且有内容，立即重命名
        if (self.session_id and 
            self.session_summary == "新对话" and 
            len(self.memory) > 0):
            self._rename_current_session()

        # 更新前一个会话的退出时间
        if self.session_id and self.session_id in self.session_meta:
            self.session_meta[self.session_id]["last_accessed"] = time.time()
            self._save_session_meta()

        # 生成新的会话ID（使用时间戳）
        new_session_id = f"session_{int(time.time() * 1000)}"
        
        # 生成会话摘要
        summary = self._generate_session_summary(first_question) if first_question else "新对话"
        
        # 初始化会话元数据
        self.session_meta[new_session_id] = {
            "id": new_session_id,
            "summary": summary,
            "created_at": time.time(),
            "last_accessed": time.time()
        }
        
        # 保存元数据
        self._save_session_meta()
        
        # 设置当前会话
        self.session_id = new_session_id
        self.session_summary = summary
        
        # 更新记忆文件路径
        self.memory_path = f"{Config.MEMORY_PATH}.{new_session_id}"
        self.memory = []  # 清空当前记忆
        self._save_memory()  # 创建空的记忆文件
        
        logger.info(f"✅ 创建新会话: {new_session_id} - {summary}")
        return new_session_id

# 切换会话相关方法
    def _switch_to_session(self, session_id: str):
        """切换到指定会话"""
        if session_id not in self.session_meta:
            logger.error(f"❌ 会话 {session_id} 不存在")
            return False

        # 如果当前会话是"新对话"且有内容，立即重命名
        if (self.session_id and 
            self.session_summary == "新对话" and 
            len(self.memory) > 0):
            self._rename_current_session()

        # 更新前一个会话的退出时间
        if self.session_id and self.session_id in self.session_meta:
            self.session_meta[self.session_id]["last_accessed"] = time.time()
            self._save_session_meta()

        # 设置当前会话
        self.session_id = session_id
        self.session_summary = self.session_meta[session_id]["summary"]
        
        # 更新记忆文件路径并加载记忆
        self.memory_path = f"{Config.MEMORY_PATH}.{session_id}"
        self.memory = self._load_memory()
        
        # 更新最后访问时间
        self.session_meta[session_id]["last_accessed"] = time.time()
        self._save_session_meta()
        
        logger.info(f"✅ 切换到会话: {session_id} - {self.session_summary}")
        return True

# 添加重命名前一个会话的方法
    def _rename_current_session(self):
        """为当前会话生成新的标题"""
        try:
            # 获取当前会话的记忆内容
            current_memory_path = f"{Config.MEMORY_PATH}.{self.session_id}"
            if os.path.exists(current_memory_path):
                with open(current_memory_path, "r", encoding="utf-8") as f:
                    current_memory = json.load(f)
                
                # 提取对话内容用于生成标题
                if current_memory and len(current_memory) > 0:
                    # 收集对话内容
                    conversation_text = ""
                    for entry in current_memory[:3]:  # 只取前3轮对话
                        user_text = entry.get("user", {}).get("text", "")
                        assistant_text = entry.get("assistant", {}).get("text", "")
                        if user_text:
                            conversation_text += f"用户: {user_text}\n"
                        if assistant_text:
                            conversation_text += f"助手: {assistant_text}\n"
                    
                    if conversation_text:
                        # 使用LLM生成会话标题
                        summary_prompt = f"请为以下医药咨询对话生成一个简短的主题摘要（不超过10个字）：\n\n{conversation_text}"
                        messages = [
                            {"role": "system", "content": "你是一个专业的医药助手，请为用户和助手的对话生成简洁准确的主题摘要。"},
                            {"role": "user", "content": summary_prompt}
                        ]
                        summary = _chat_with_retry(self.llm, messages)
                        new_summary = summary.strip()[:20]  # 限制长度
                        
                        # 更新会话元数据
                        if self.session_id in self.session_meta:
                            self.session_meta[self.session_id]["summary"] = new_summary
                            self._save_session_meta()
                            
                            # 更新当前显示的会话名称
                            self.session_summary = new_summary
                                
                        logger.info(f"✅ 会话 {self.session_id} 已重命名为: {new_summary}")
            
        except Exception as e:
            logger.warning(f"生成会话标题失败: {e}")
        
# 列出会话方法
    def _list_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """列出最近的会话，按上次退出时间倒序排列"""
        sessions = list(self.session_meta.values())
        # 按上次退出时间排序（last_accessed字段）
        sessions.sort(key=lambda x: x["last_accessed"], reverse=True)
        return sessions[:limit]

# 删除会话方法
    def _delete_session(self, session_id: str) -> bool:
        """删除指定会话"""
        try:
            # 检查会话是否存在
            if session_id not in self.session_meta:
                logger.warning(f"会话 {session_id} 不存在")
                return False
                
            # 删除会话记忆文件
            session_memory_path = f"{Config.MEMORY_PATH}.{session_id}"
            if os.path.exists(session_memory_path):
                os.remove(session_memory_path)
                logger.info(f"已删除会话记忆文件: {session_memory_path}")
            
            
            # 清理Redis中的会话数据
            try:
                recent_key = f"chat:{session_id}:recent"
                summary_key = f"chat:{session_id}:summary"
                
                recent_deleted = self.redis_manager.redis_client.delete(recent_key)
                summary_deleted = self.redis_manager.redis_client.delete(summary_key)
                
                logger.info(f"尝试清理Redis中会话 {session_id} 的缓存数据: {recent_key} (删除: {recent_deleted}), {summary_key} (删除: {summary_deleted})")
            except Exception as e:
                logger.warning(f"清理Redis缓存失败: {e}")
            
            # 从元数据中移除会话
            del self.session_meta[session_id]
            self._save_session_meta()
            
            logger.info(f"✅ 会话 {session_id} 已删除")
            return True
        except Exception as e:
            logger.error(f"删除会话 {session_id} 失败: {e}")
            return False
# 显示会话选择界面
    def _show_session_selector(self):
        """显示会话选择界面"""
        sessions = self._list_sessions()
        if not sessions:
            print("📝 暂无历史会话")
            return None
        
        print("\n📋 历史会话列表(删除对话：del+会话编号):")
        print("0. 创建新会话")
        for i, session in enumerate(sessions, 1):
            # 格式化时间，显示上次退出时间
            last_accessed_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(session["last_accessed"]))
            print(f"{i}. [{session['id']}] {session['summary']} (上次退出: {last_accessed_time})")
        
        while True:
            try:
                choice = input("\n请选择会话编号 (0创建新会话, 回车创建新会话): ").strip()
                
                # 检查是否为删除命令
                if choice.startswith("del") and len(choice) > 3:
                    try:
                        # 解析删除的会话编号
                        del_index = int(choice[3:])
                        if 1 <= del_index <= len(sessions):
                            session_to_delete = sessions[del_index - 1]
                            session_id = session_to_delete["id"]
                            session_summary = session_to_delete["summary"]
                            
                            # 确认删除
                            confirm = input(f"确定要删除会话 [{session_id}] {session_summary} 吗？(y/N): ").strip().lower()
                            if confirm == 'y' or confirm == 'yes':
                                if self._delete_session(session_id):
                                    print(f"✅ 会话 [{session_id}] {session_summary} 已删除")
                                    # 重新加载会话列表并刷新显示
                                    sessions = self._list_sessions()
                                    if not sessions:
                                        print("📝 暂无历史会话")
                                        return None
                                    
                                    print("\n📋 历史会话列表(删除对话：del+会话编号):")
                                    print("0. 创建新会话")
                                    for i, session in enumerate(sessions, 1):
                                        last_accessed_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(session["last_accessed"]))
                                        print(f"{i}. [{session['id']}] {session['summary']} (上次退出: {last_accessed_time})")
                                    continue
                                else:
                                    print("❌ 删除会话失败")
                            else:
                                print("取消删除操作")
                                # 重新显示会话列表
                                sessions = self._list_sessions()
                                print("\n📋 历史会话列表(删除对话：del+会话编号):")
                                print("0. 创建新会话")
                                for i, session in enumerate(sessions, 1):
                                    last_accessed_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(session["last_accessed"]))
                                    print(f"{i}. [{session['id']}] {session['summary']} (上次退出: {last_accessed_time})")
                                continue
                        else:
                            print("⚠️  无效的会话编号，请重新输入")
                            continue
                    except ValueError:
                        print("⚠️  请输入有效的会话编号，格式如: del1")
                        continue
                
                # 正常的选择逻辑
                if choice == "" or choice == "0":
                    return self._create_new_session()
                
                choice_num = int(choice)
                if 1 <= choice_num <= len(sessions):
                    return sessions[choice_num - 1]["id"]
                else:
                    print("⚠️  无效的选择，请重新输入")
            except ValueError:
                print("⚠️  请输入有效的数字")
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"⚠️  输入错误: {e}")

    def _generate_draft_answer_stream(self, question: str, evidence_docs: list):
        """流式生成初步答案（不输出中间结果）"""
        # 构建简化提示
        simplified_evidence = "\n".join([
            f"- {doc.metadata.get('source','unknown')}: {self._bullet_compress(doc.page_content, 100)}" 
            for doc in evidence_docs[:3]  # 只使用前3个证据
        ])
        
        draft_prompt = f"""
    问题: {question}

    基于以下关键证据，请快速给出初步回答，并指出还需要哪些补充信息:
    {simplified_evidence}

    要求:
    1. 给出简洁的初步回答
    2. 明确指出还需要哪些方面的详细信息才能给出完整回答
    3. 用JSON格式返回，包含"draft_answer"和"gaps"字段
    """

        messages = [
            {"role": "system", "content": "你是一个高效的医疗助手，请快速生成初步回答并识别信息缺口。"},
            {"role": "user", "content": draft_prompt}
        ]
        
        try:
            response = ""
            for content in self._stream_chat_with_retry(
                self.llm, 
                messages, 
                temperature=0.3
            ):
                response += content
                
            # 不输出中间结果，直接解析JSON
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                # 如果不是JSON格式，返回默认结构
                return {"draft_answer": response, "gaps": ["需要更多信息"]}
        except Exception as e:
            logger.warning(f"流式草稿生成失败: {e}")
            return {"draft_answer": "正在处理您的问题...", "gaps": ["需要更多信息"]}

    def _generate_enhanced_answer_stream(self, prompt_compact: str, user_content: list):
        """
        直接把包含 SYSTEM/FACTS/QUESTION/EVIDENCE/HISTORY 的 prompt_compact 发给模型，
        user_content[1:] 里可能有图片（image_url）。
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": [{"type": "text", "text": prompt_compact}] + (user_content[1:] if len(user_content) > 1 else [])}
        ]
        response_content = ""
        try:
            for content in self._stream_chat_with_retry(self.llm, messages, temperature=0.1):
                response_content += content
                print(content, end="", flush=True)
            print()
            return response_content
        except Exception as e:
            logger.error(f"流式生成完整答案失败: {e}")
            return f"发生错误：{e}"

    
# ========== 降级模式 ==========
    def _degraded_query(self, question: str, evidence_docs: list) -> dict:
        """
        降级模式：只返回证据摘要，不调用大模型
        """
        evidence_summary = "\n".join([
            f"- {doc.metadata.get('source','unknown')}: {self._bullet_compress(doc.page_content)}" 
            for doc in evidence_docs[:3]  # 只使用前3个证据
        ])
        
        degraded_response = f"""
    基于检索到的医学资料，为您找到以下相关信息：

    {evidence_summary}

    由于系统负载较高，暂时无法生成详细解答。建议您：
    1. 提供更具体的问题描述
    2. 稍后再试
    3. 咨询专业医生获取准确诊断
    """
        
        return {
            "response": degraded_response,
            "sources": [doc.metadata.get("source", "unknown") for doc in evidence_docs[:3]]
        }
    # ========= 支持流式输出的LLM调用 ==========
    def _stream_chat_with_retry(self, llm: ChatOpenAI, messages, **kwargs):
        """支持流式输出的LLM调用"""
        if not _circuit_allows():
            yield "（后端繁忙，已进入短暂保护，请稍后再试）"
            return
        
        try:
            for chunk in llm.stream(messages, **kwargs):
                content = getattr(chunk, "content", str(chunk))
                yield content
            _circuit_record(True)
        except Exception as e:
            _circuit_record(False)
            yield f"发生错误：{e}"
    # ========== 查询接口 ==========
    def query(self, question: str, image_base64: str = None, stream_output: bool = True):
        """
        查询接口增强版：支持外部传入图像分析结果

        Args:
            question: 用户问题
            image_base64: 图片的 base64 编码（可选）
            stream_output: 是否流式输出
        """
        # 记录开始时间
        start_time = time.time()
        # 预估处理时间并提示用户
        if hasattr(self, '_hybrid_search'):
            # 粗略预估，基于问题长度
            estimated_time = max(3, min(len(question) // 20, 10))
            print(f"⏰ 预计需要 {estimated_time} 秒完成处理，请稍候...")

        # 检查是否需要降级
        if self.perf_monitor.should_degrade():
            logger.warning("系统负载过高，启用降级模式")
            candidates = self._hybrid_search(question)
            docs = self._rerank(question, candidates, top_n=min(3, Config.RETRIEVAL_TOP_K))
            result = self._degraded_query(question, docs)
            
            # 记录性能指标
            latency_ms = int((time.time() - start_time) * 1000)
            self.perf_monitor.record_response_time(latency_ms)
            
            return result
        
        # 处理特殊命令
        if question.strip() == "/new":
            self._create_new_session()
            return {"response": f"✅ 已创建新会话: {self.session_summary}", "sources": []}
        

        try:
            # ===== 1. 初筛（多拿一些，例如 20 条）=====
            candidates = self._hybrid_search(question)
            # 如果想拿更多候选，可以把混合检索改造成返回更多再在这里截断
            # 这里示意直接用 candidates，当你扩展 _hybrid_search 时把数量拉大到 20

            # ===== 1.5 交叉重排，最后只留 top_k =====
            docs = self._rerank(question, candidates, top_n=Config.RETRIEVAL_TOP_K)
            context = "\n".join([doc.page_content for doc in docs]) if docs else "未检索到相关医学资料。"

            # 获取完整历史记录（提前获取，用于计算 history_sig）
            full_history = self._memory_to_messages()
            
            # 计算历史签名（在缓存检查前计算）
            try:
                recent_hist_text = " || ".join([m.get("content","") if isinstance(m, dict) else str(m) for m in full_history[-8:]])
                history_sig = hashlib.md5(recent_hist_text.encode("utf-8")).hexdigest()
            except Exception:
                history_sig = "nohist"

            # 检查生成缓存（使用 history_sig）
            evidence_ids = [doc.metadata.get("source", "unknown") for doc in docs]
            cached_result = self.generation_cache.get(question, evidence_ids, self.system_prompt, history_sig=history_sig)
            if cached_result:
                logger.info("命中生成缓存")
                # 缓存命中时只在流式模式下输出，主程序会负责输出结果
                return cached_result
                
            # ===== 2. 构建用户问题（融合图像分析信息）=====
            augmented_question = question

            # ===== 3. 上下文治理与压缩 =====
            # 选择相关历史（更稳）
            history_sel = self._select_history_smart(question, full_history, keep_recent_pairs=3, top_sim=6)

            # 简单的历史签名：最近 8 条消息文本拼接后 md5
            try:
                recent_hist_text = " || ".join([m.get("content","") if isinstance(m, dict) else str(m) for m in full_history[-8:]])
                history_sig = hashlib.md5(recent_hist_text.encode("utf-8")).hexdigest()
            except Exception:
                history_sig = "nohist"

            # 选择相关历史（更稳）
            history_sel = self._select_history_smart(question, full_history, keep_recent_pairs=3, top_sim=6)


            # （可选）从最近几条里抽取姓名/药物形成 FACTS（没做事实持久化时的轻量版）
            facts_list = []
            try:
                recent_text = " ".join([m.get("content","") for m in full_history[-8:]])
                m_name = re.search(r"(我叫|我的名字是)\s*([A-Za-z0-9_\u4e00-\u9fa5]{1,20})", recent_text)
                if m_name:
                    facts_list.append(f"姓名：{m_name.group(2)}")
                m_drug = re.search(r"(阿莫西林|莫西沙星|头孢|布洛芬|对乙酰氨基酚)", recent_text)
                if m_drug:
                    facts_list.append(f"最近提到的药物：{m_drug.group(1)}")
            except Exception:
                pass
            facts_json = "；".join(facts_list)

            # 预算化拼装（只把选出来的 HISTORY 文本放进 prompt）
            prompt_compact = self._assemble_with_budget(
                system_prompt=self.system_prompt,
                facts_json=facts_json,
                question=augmented_question,
                evidence_docs=docs,
                history_sel=history_sel,
                budget_chars=6000
            )


             # ===== 4. 构建多模态输入 content =====
            user_content = [
                {"type": "text", "text": prompt_compact},
            ]
            img_bytes = None
            if image_base64:
                # 解码base64图片数据
                try:
                    # 移除可能的数据URI前缀
                    if image_base64.startswith('data:image'):
                        # 提取实际的base64数据部分
                        image_data = image_base64.split(',')[1]
                    else:
                        image_data = image_base64
                    
                    img_bytes = base64.b64decode(image_data)
                    
                    # 执行OCR识别
                    ocr_text = self._perform_ocr(img_bytes)
                    is_text_image = self._is_text_image(ocr_text, img_bytes)

                    # 根据图片类型采取不同策略
                    if is_text_image:
                        # 对纯文本图片可以优化处理，如跳过大模型图片理解
                        logger.info("检测到纯文本图片，将采用优化处理策略")
                    
                    # 将OCR结果添加到问题中
                    if ocr_text:
                        # 动态控制OCR文本长度
                        max_ocr_length = 300  # 可以设置为配置项或根据需要调整
                        if hasattr(Config, 'MAX_OCR_LENGTH'):
                            max_ocr_length = Config.MAX_OCR_LENGTH

                        augmented_question = f"OCR识别内容：{ocr_text[:max_ocr_length]}...\n\n原始问题：{question}"
                    
                    # 处理图片格式和压缩
                    processed_image, mime_type = self._prepare_image_b64(img_bytes)
                    user_content.append({
                        "type": "image_url", 
                        "image_url": {"url": processed_image}
                    })
                    logger.info(f"图片处理完成，格式: {mime_type}, 大小: {len(img_bytes)} bytes")
                except Exception as e:
                    logger.error(f"图片处理失败: {e}")
                    # 如果图片处理失败，仍然使用原始数据
                    user_content.append({
                        "type": "image_url", 
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                    })

            # ===== 5. 构建完整消息历史 =====
            system_message = {"role": "system", "content": self.system_prompt}
            messages = [system_message, {"role": "user", "content": user_content}]


            # ===== 6. 调用 LLM =====
            # =====  两段式生成 =====
            if stream_output:
                print("🔍 正在分析问题并检索相关信息...")
                start_stage_time = time.time()

                # 第一阶段：流式生成草稿（不输出）
                draft_info = self._generate_draft_answer_stream(question, docs[:3])

                # 添加检查
                if not isinstance(draft_info, dict):
                    draft_info = {"draft_answer": "正在处理...", "gaps": []}

                # 判断是否需要第二阶段
                if draft_info.get("gaps") and len(draft_info["gaps"]) > 0:
                    print("🧠 正在生成详细回答...")
                    stage2_start = time.time()
                    # 第二阶段：流式生成完整答案
                    response_content = self._generate_enhanced_answer_stream(prompt_compact, user_content)
                    print(f"✅ 回答生成完成 (耗时 {round(time.time() - stage2_start, 1)}s)")
                else:
                    # 不需要第二阶段时，直接输出草稿答案
                    response_content = draft_info.get("draft_answer", "正在处理...")
                    print(response_content)
            else:
                # 非流式输出：直接生成完整答案（使用与流式模式相同的prompt结构）
                try:
                    # 使用与流式模式相同的消息结构
                    messages = [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_content}
                    ]
                    response = _chat_with_retry(self.llm, messages, temperature=0.1)
                    # 处理响应内容
                    if isinstance(response, str):
                        response_content = response
                    else:
                        response_content = getattr(response, "content", str(response))
                except Exception as e:
                    logger.error(f"LLM调用失败: {e}")
                    response_content = f"生成回答时发生错误：{e}"

            # ===== 7. 保存记忆（带图像分析元信息和缩略图）=====
            image_meta = "inline_base64_image" if image_base64 else ""
            thumbnail_data = ""
            
            # 如果有图片，创建缩略图
            if image_base64 and img_bytes:
                try:
                    # 移除可能的数据URI前缀
                    if image_base64.startswith('data:image'):
                        image_data = image_base64.split(',')[1]
                    else:
                        image_data = image_base64
                    img_bytes_for_thumbnail = base64.b64decode(image_data)
                    thumbnail_data = self._create_thumbnail(img_bytes_for_thumbnail)
                except Exception as e:
                    logger.warning(f"创建缩略图时解码图片失败: {e}")
            
            self._append_memory(
                augmented_question, 
                response_content, 
                bool(image_base64), 
                image_meta,
                thumbnail_data
            )

            # ===== 8. 记录日志 =====
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_event({
                "ts": time.time(),
                "query": question[:200],  # 限制长度
                "prompt_len": len(prompt_compact),
                "evidence": [d.metadata.get("source", "unknown") for d in docs],
                "model": Config.LLM_MODEL_NAME,
                "temperature": self.llm.temperature,
                "latency_ms": latency_ms,
                "outcome": "ok"
            })

            # ===== 9. 返回结果 =====
            result = {
            "response": response_content,
            "sources": [doc.metadata.get("source", "unknown") for doc in docs]
        }
        
            # 缓存生成结果
            self.generation_cache.set(question, evidence_ids, self.system_prompt, result, history_sig=history_sig)
            return result

        except Exception as e:
            self.perf_monitor.record_error()
            # 记录错误日志
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_event({
                "ts": time.time(),
                "query": question[:200],
                "prompt_len": len(prompt_compact) if 'prompt_compact' in locals() else 0,
                "evidence": [],
                "model": Config.LLM_MODEL_NAME,
                "temperature": self.llm.temperature if hasattr(self.llm, 'temperature') else 0.1,
                "latency_ms": latency_ms,
                "outcome": "error",
                "error": str(e)
            })
            
            logger.error(f"❌ Query failed: {e}")
            return {"response": f"发生错误：{e}", "sources": []}

# ========== 交互入口 ==========
# 修改主程序部分的退出逻辑
if __name__ == "__main__":
    rag = MedRAGAscend()
    print("🩺 医药多模态问答系统（ Qwen-VL-Max）")
    print("💡 输入问题后可上传图片路径（可选），再输入图像分析结果（可选），或直接回车跳过。")
    print("💡 特殊命令：/new (创建新对话)  /history (选择历史对话)")

    # 启动时让用户选择会话
    try:
        session_id = rag._show_session_selector()
        if session_id:
            rag._switch_to_session(session_id)
        else:
            rag._create_new_session()
    except KeyboardInterrupt:
        # 程序被中断时也要重命名当前会话
        if (rag.session_id and 
            rag.session_summary == "新对话" and 
            len(rag.memory) > 0):
            rag._rename_current_session()
        print("\n👋 程序退出。")
        exit(0)

    while True:
        try:
            # 1. 输入问题
            question = input(f"\n📝 [当前会话: {rag.session_summary}] 请输入问题（或输入 exit 退出）: ").strip()
            if question.lower() == "exit":
                # 退出时重命名当前会话
                if (rag.session_id and 
                    rag.session_summary == "新对话" and 
                    len(rag.memory) > 0):
                    rag._rename_current_session()
                # 更新会话退出时间
                if rag.session_id and rag.session_id in rag.session_meta:
                    rag.session_meta[rag.session_id]["last_accessed"] = time.time()
                    rag._save_session_meta()
                print("👋 感谢使用，再见！")
                break
            
            # 处理特殊命令 /new
            if question.strip() == "/new":
                rag._create_new_session()
                continue

            # 处理特殊命令 /history
            if question.strip() == "/history":
                try:
                    session_id = rag._show_session_selector()
                    if session_id and session_id != rag.session_id:
                        rag._switch_to_session(session_id)
                        print(f"✅ 已切换到会话: {rag.session_summary}")
                    elif session_id == rag.session_id:
                        print("ℹ️  已在当前会话中")
                except KeyboardInterrupt:
                    print("\n↩️  取消切换会话")
                continue

            # 2. 上传图片（可选）
            img_path = input("🖼️ 请输入图片路径（回车跳过）: ").strip()
            b64_img = None
            if img_path and os.path.exists(img_path):
                with open(img_path, "rb") as f:
                    b64_img = base64.b64encode(f.read()).decode("utf-8")
                print("✅ 图片已上传。")
            elif img_path:
                print("⚠️ 图片路径不存在，跳过图片输入。")

            # 3. 调用查询
            # 注意：使用流式输出，内容会在生成过程中实时显示
            result = rag.query(
                question=question,
                image_base64=b64_img,
                stream_output=True
            )
            # 流式模式下，内容已经在query方法中输出，这里不需要再次输出

            
            # —— 输出检索来源（对用户可见）——
            if result and "sources" in result:
                sources = list(dict.fromkeys(result.get("sources", [])))  # 去重且保留顺序
                # 过滤掉"unknown"来源
                valid_sources = [s for s in sources if s != "unknown"]
                if valid_sources:
                    print("\n\n📚 Sources:")
                    for i, s in enumerate(valid_sources, 1):
                        print(f"  {i}. {s}")

        except KeyboardInterrupt:
            # 程序被中断时也要重命名当前会话
            if (rag.session_id and 
                rag.session_summary == "新对话" and 
                len(rag.memory) > 0):
                rag._rename_current_session()
            # 更新会话退出时间
            if rag.session_id and rag.session_id in rag.session_meta:
                rag.session_meta[rag.session_id]["last_accessed"] = time.time()
                rag._save_session_meta()
            print("\n\n👋 检测到中断，退出中...")
            break
        except EOFError:
            # 程序结束时也要重命名当前会话
            if (rag.session_id and 
                rag.session_summary == "新对话" and 
                len(rag.memory) > 0):
                rag._rename_current_session()
            # 更新会话退出时间
            if rag.session_id and rag.session_id in rag.session_meta:
                rag.session_meta[rag.session_id]["last_accessed"] = time.time()
                rag._save_session_meta()
            print("\n👋 对话结束。")
            break
"""
知识图谱（向量存储）管道模块。

提供从PDF文件生成向量存储并存储到ChromaDB的功能。
"""

import os
import sys
import json
import glob
from typing import List, Optional, Dict, Any

def run_kg_pipeline(
    pdf_folder: str = "data",
    persist_directory: str = "./chroma_storage",
    collection_name: str = "chattutor",
    embedding_model: Optional[str] = None
) -> str:
    """
    从PDF文件夹生成向量存储并存入ChromaDB。

    Args:
        pdf_folder: 包含PDF文件的文件夹路径（默认："data"）
        persist_directory: ChromaDB持久化目录（默认："./chroma_storage"）
        collection_name: ChromaDB集合名称（默认："chattutor"）
        embedding_model: 嵌入模型类型（默认：None，自动选择）
            - None 或 "openai": 使用OpenAIEmbeddings（需要有效API密钥）
            - "huggingface": 使用免费的HuggingFaceEmbeddings
            当OpenAI API密钥无效时，会自动切换到HuggingFace模型

    Returns:
        日志字符串，描述执行过程和结果。
    """
    lines = []
    def log(msg: str):
        lines.append(msg)
        print(msg)

    # Import config for API keys
    try:
        from app.core.config import settings
    except ImportError as e:
        log(f"缺少配置模块: {e}")
        log("无法获取API密钥配置")
        return "\n".join(lines)

    try:
        from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
        import chromadb
    except ImportError as e:
        log(f"缺少依赖: {e}")
        log("请安装: pip install langchain-community chromadb")
        return "\n".join(lines)

    if not os.path.exists(pdf_folder):
        log(f"错误: 找不到PDF文件夹 {pdf_folder}，请将PDF放在此目录下。")
        return "\n".join(lines)

    log(f"正在读取PDF文件夹: {pdf_folder} ...")
    loader = DirectoryLoader(pdf_folder, glob="**/*.pdf", loader_cls=PyPDFLoader)
    docs = loader.load()
    if not docs:
        log("未发现有效PDF文件。")
        return "\n".join(lines)

    texts = [d.page_content for d in docs]
    metadatas = [d.metadata for d in docs]
    ids = [str(i) for i in range(len(texts))]

    client = chromadb.PersistentClient(path=persist_directory)
    try:
        collection = client.get_collection(collection_name)
        log(f"已打开现有Chroma集合 '{collection_name}'。数据将被追加。")
    except Exception:
        collection = client.create_collection(name=collection_name)
        log(f"已建立新的Chroma集合 '{collection_name}'。")

    # Determine which embedding model to use
    # Handle "auto" option (let the function decide automatically)
    if embedding_model and embedding_model.lower() == "auto":
        embedding_model = None

    model_type = (embedding_model or "huggingface").lower()  # Default to HuggingFace if not specified
    embeddings = None

    # OpenAI embeddings are disabled, always use HuggingFace
    if model_type in ["openai", "openaiembeddings"]:
        log(f"提示: OpenAI嵌入模型已禁用，使用免费HuggingFace嵌入模型。")
        model_type = "huggingface"  # Force HuggingFace

    # Try HuggingFace embeddings if needed (either requested or as fallback)
    if model_type in ["huggingface", "hf", "sentence-transformers"] and embeddings is None:
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings
            # Use a lightweight, free sentence transformer model
            model_name = "sentence-transformers/all-MiniLM-L6-v2"
            embeddings = HuggingFaceEmbeddings(model_name=model_name)
            log(f"使用免费HuggingFace嵌入模型 (model: {model_name})")
            log("注意: 首次使用需要下载模型文件，可能需要几分钟时间。")
        except ImportError as e:
            log(f"缺少HuggingFaceEmbeddings依赖: {e}")
            log("请安装: pip install sentence-transformers")
            return "\n".join(lines)
        except Exception as e:
            log(f"创建HuggingFaceEmbeddings失败: {e}")
            log("请检查网络连接或尝试其他嵌入模型。")
            return "\n".join(lines)

    # Check if embeddings were successfully created
    if embeddings is None:
        log(f"错误: 无法创建嵌入模型")
        log(f"请求的模型类型: {embedding_model or 'huggingface (默认)'}")
        log("支持的选项: 'huggingface' (免费嵌入模型)")
        return "\n".join(lines)

    log(f"正在计算嵌入并写入Chroma（共 {len(texts)} 条）...")
    try:
        collection.add(
            documents=texts,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings.embed_documents(texts)
        )
        # 尝试持久化（兼容新旧版本）
        try:
            client.persist()
        except AttributeError:
            # ChromaDB 新版本中 PersistentClient 自动持久化
            log("注意: ChromaDB 新版本自动持久化，无需显式调用 persist()")
        except Exception as e:
            log(f"持久化警告: {e}")
    except Exception as e:
        log(f"写入Chroma失败: {e}")
        return "\n".join(lines)

    log("✅ Chroma数据库更新完成！")
    return "\n".join(lines)


def build_knowledge_graph(
    pdf_folder: str = "data",
    output_dir: str = "./kg_output",
    model_name: str = "bert-base-chinese"
) -> str:
    """
    从PDF文件夹构建真正的知识图谱（实体-关系图）并生成可视化。

    Args:
        pdf_folder: 包含PDF文件的文件夹路径（默认："data"）
        output_dir: 输出目录（默认："./kg_output"）
        model_name: NER模型名称（默认："bert-base-chinese"）

    Returns:
        日志字符串，描述执行过程和结果。
    """
    lines = []
    def log(msg: str):
        lines.append(msg)
        print(msg)

    try:
        # 尝试导入知识图谱构建器
        from app.kg.kg_builder import build_knowledge_graph_from_pdf
    except ImportError as e:
        log(f"缺少知识图谱构建模块: {e}")
        log("请确保已安装所需依赖: pip install transformers torch networkx pyvis")
        return "\n".join(lines)

    import os
    import glob

    if not os.path.exists(pdf_folder):
        log(f"错误: 找不到PDF文件夹 {pdf_folder}，请将PDF放在此目录下。")
        return "\n".join(lines)

    # 查找PDF文件
    pdf_files = glob.glob(os.path.join(pdf_folder, "**/*.pdf"), recursive=True)
    if not pdf_files:
        log(f"在 {pdf_folder} 中未找到PDF文件")
        return "\n".join(lines)

    log(f"找到 {len(pdf_files)} 个PDF文件")

    all_results = []
    for pdf_file in pdf_files:
        log(f"正在处理: {os.path.basename(pdf_file)}")

        try:
            # 构建知识图谱
            result = build_knowledge_graph_from_pdf(pdf_file, output_dir, model_name=model_name)

            if result.get("success"):
                stats = result.get("stats", {})
                log(f"  ✅ 成功构建知识图谱")
                log(f"     实体数: {stats.get('entity_count', 0)}")
                log(f"     关系数: {stats.get('relation_count', 0)}")
                log(f"     可视化文件: {result.get('visualization', 'N/A')}")
                all_results.append(result)
            else:
                log(f"  ❌ 失败: {result.get('error', '未知错误')}")

        except Exception as e:
            log(f"  ❌ 处理失败: {e}")

    if all_results:
        log(f"\n✅ 知识图谱构建完成！共处理 {len(all_results)} 个文件")
        log(f"输出目录: {output_dir}")
        log("文件列表:")
        for result in all_results:
            log(f"  - 可视化: {result.get('visualization', 'N/A')}")
            log(f"  - 数据: {result.get('data', 'N/A')}")
    else:
        log("❌ 未能成功构建任何知识图谱")

    return "\n".join(lines)


def build_knowledge_graph_from_sessions(
    sessions_dir: str = "memory/sessions",
    output_dir: str = "./kg_output",
    model_name: str = "bert-base-chinese"
) -> str:
    """
    从对话会话文件构建知识图谱（实体-关系图）并生成可视化。

    Args:
        sessions_dir: 包含会话JSON文件的文件夹路径（默认："memory/sessions"）
        output_dir: 输出目录（默认："./kg_output"）
        model_name: NER模型名称（默认："bert-base-chinese"）

    Returns:
        日志字符串，描述执行过程和结果。
    """
    lines = []
    def log(msg: str):
        lines.append(msg)
        print(msg)

    # 设置环境变量以优化HuggingFace Hub客户端行为
    # 防止HTTP客户端被意外关闭的问题
    import os
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "0"  # 设置为"1"可强制离线模式

    try:
        # 尝试导入知识图谱构建器
        from app.kg.kg_builder import KnowledgeGraphBuilder
    except ImportError as e:
        log(f"缺少知识图谱构建模块: {e}")
        log("请确保已安装所需依赖: pip install transformers torch networkx pyvis")
        return "\n".join(lines)

    if not os.path.exists(sessions_dir):
        log(f"错误: 找不到会话文件夹 {sessions_dir}")
        return "\n".join(lines)

    # 查找JSON会话文件
    json_files = glob.glob(os.path.join(sessions_dir, "**/*.json"), recursive=True)
    if not json_files:
        log(f"在 {sessions_dir} 中未找到JSON会话文件")
        return "\n".join(lines)

    log(f"找到 {len(json_files)} 个会话文件")

    # 从所有会话文件中提取对话文本
    all_conversation_texts = []

    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)

            # 提取对话文本
            conversation_text = extract_conversation_from_session(session_data)
            if conversation_text:
                all_conversation_texts.append(conversation_text)
                log(f"已处理: {os.path.basename(json_file)} ({len(conversation_text)} 字符)")
            else:
                log(f"跳过: {os.path.basename(json_file)} (无有效对话)")

        except Exception as e:
            log(f"处理会话文件 {json_file} 失败: {e}")

    if not all_conversation_texts:
        log("❌ 未从任何会话文件中提取到有效对话")
        return "\n".join(lines)

    # 合并所有对话文本
    combined_text = "\n\n".join(all_conversation_texts)
    log(f"合并对话文本总长度: {len(combined_text)} 字符")

    # 构建知识图谱
    try:

        builder = KnowledgeGraphBuilder(model_name=model_name)

        log("正在构建知识图谱...")
        stats = builder.build_graph(combined_text)

        log(f"✅ 知识图谱构建完成!")
        log(f"  实体数: {stats.get('entity_count', 0)}")
        log(f"  关系数: {stats.get('relation_count', 0)}")
        log(f"  节点数: {stats.get('node_count', 0)}")
        log(f"  边数: {stats.get('edge_count', 0)}")

        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

        # 生成可视化
        html_path = os.path.join(output_dir, "knowledge_graph_from_sessions.html")
        visualization_path = builder.visualize_graph(html_path)
        if visualization_path:
            log(f"  可视化文件: {visualization_path}")

        # 导出数据
        json_path = os.path.join(output_dir, "knowledge_graph_from_sessions.json")
        graph_data = builder.export_graph_data(json_path)
        log(f"  数据文件: {json_path}")

    except RuntimeError as e:
        if "client has been closed" in str(e):
            log(f"❌ 构建知识图谱失败: HTTP客户端已关闭")
            log("这可能是因为Streamlit环境中的HTTP客户端管理问题。")
            log("建议：")
            log("1. 重启Streamlit应用")
            log("2. 确保网络连接正常")
            log("3. 如果问题持续，请尝试使用更简单的模型或离线模式")
            log(f"详细错误: {e}")
        else:
            log(f"❌ 构建知识图谱失败: {e}")
            import traceback
            log(f"详细错误: {traceback.format_exc()}")
    except Exception as e:
        log(f"❌ 构建知识图谱失败: {e}")
        import traceback
        log(f"详细错误: {traceback.format_exc()}")

    return "\n".join(lines)


def extract_conversation_from_session(session_data: Dict[str, Any]) -> str:
    """
    从会话数据中提取对话文本。

    Args:
        session_data: 会话JSON数据

    Returns:
        合并后的对话文本
    """
    conversation_parts = []

    # 提取会话摘要（如果有）
    if session_data.get("conversation_summary"):
        conversation_parts.append(f"对话摘要: {session_data['conversation_summary']}")

    # 提取对话消息
    messages = session_data.get("messages", [])
    for msg in messages:
        msg_type = msg.get("type", "")
        msg_data = msg.get("data", {})

        if msg_type == "human" and "content" in msg_data:
            conversation_parts.append(f"用户: {msg_data['content']}")
        elif msg_type == "ai" and "content" in msg_data:
            conversation_parts.append(f"AI: {msg_data['content']}")

    return "\n".join(conversation_parts)
import requests
import json
from langchain_core.tools import tool
from chattutor.core.config import settings

@tool("baidu_search")
def api_baidu_search(query: str) -> str:
    """
    使用百度 AppBuilder API 执行联网搜索。
    
    Args:
        query: 用户的搜索关键词
        
    Returns:
        JSON 格式的搜索结果字符串（目前仅返回原始 Response，等待进一步处理）
    """
    url = "https://qianfan.baidubce.com/v2/ai_search/web_search"
    
    headers = {
        'X-Appbuilder-Authorization': f'Bearer {settings.BAIDU_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "messages": [
            {
                "content": query,
                "role": "user"
            }
        ],
        "search_source": "baidu_search_v2",
        "resource_type_filter": [{"type": "web", "top_k": 10}]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # 结果解析与格式化
        if "references" not in data or not data["references"]:
            return "No relevant search results found."
            
        results_text = []
        for item in data["references"]:
            title = item.get("title", "No Title")
            url = item.get("url", "No URL")
            content = item.get("content", "")
            date = item.get("date", "")
            
            # 拼装单条结果
            entry = f"Title: {title}\nDate: {date}\nSource: {url}\nContent: {content}\n"
            results_text.append(entry)
            
        # 返回合并后的字符串，供 LLM 阅读
        return "\n---\n".join(results_text)
        
    except Exception as e:
        return f"Error connecting to Baidu Search: {str(e)}"

# 临时的变量导出，方便其他模块调用
search_tool = api_baidu_search


# -----------------------------------------------------------------------------
# Knowledge Graph / vector store helper using ChromaDB
# -----------------------------------------------------------------------------

@tool("kg_search")
def kg_search(query: str) -> str:
    """
    Perform a similarity search over documents stored in a ChromaDB
    collection.  The collection is expected to have been populated by
    ``run_kg_pipeline`` which ingests PDF text.

    Returns a short summary of the most relevant documents or an error
    message if Chroma is not available.
    """
    try:
        import chromadb
    except ImportError:
        return "Error: chromadb package is required for kg_search."

    # open local persist directory (default 'chroma_storage')
    client = chromadb.PersistentClient(path="./chroma_storage")
    try:
        collection = client.get_collection("chattutor")
    except Exception:
        return "Error: Chroma collection 'chattutor' not found. Run ingestion first."

    try:
        results = collection.query(query_texts=[query], n_results=5)
    except Exception as e:
        return f"KG query failed: {e}"

    docs = results.get("documents", [[]])[0]
    if not docs:
        return "No matching documents found in vector store."

    # simply return the top documents concatenated
    return "\n---\n".join(docs)


def get_chroma_collection_info(collection_name="chattutor", path="./chroma_storage"):
    """
    获取Chroma集合的详细信息。

    Args:
        collection_name: 集合名称
        path: Chroma持久化目录路径

    Returns:
        字典格式的集合信息，包含文档数量、ID等，或错误信息
    """
    try:
        import chromadb
    except ImportError:
        return {"error": "chromadb package is required."}

    try:
        client = chromadb.PersistentClient(path=path)
        collection = client.get_collection(collection_name)

        # 获取集合信息
        count = collection.count()

        # 获取前N个文档的ID和元数据
        sample_docs = []
        try:
            # 尝试获取一些文档样本
            results = collection.get(limit=min(10, count))
            if results and results.get("ids"):
                for i, doc_id in enumerate(results["ids"]):
                    doc_content = results["documents"][i] if i < len(results["documents"]) else ""
                    metadata = results["metadatas"][i] if i < len(results.get("metadatas", [])) else {}
                    sample_docs.append({
                        "id": doc_id,
                        "content_preview": doc_content[:100] + "..." if len(doc_content) > 100 else doc_content,
                        "metadata": metadata
                    })
        except Exception as e:
            sample_docs = [{"error": f"获取文档样本失败: {e}"}]

        return {
            "collection_name": collection_name,
            "document_count": count,
            "sample_docs": sample_docs,
            "path": path
        }

    except Exception as e:
        return {"error": f"获取集合信息失败: {e}"}

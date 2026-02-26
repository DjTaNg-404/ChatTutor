import requests
import json
from langchain_core.tools import tool
from app.core.config import settings

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

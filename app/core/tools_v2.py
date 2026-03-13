from langchain_core.tools import tool

from app.core.cache import retrieval_cache
from app.core.tools import api_baidu_search as base_search_tool


@tool("baidu_search")
def api_baidu_search_cached(query: str) -> str:
    """
    Cached wrapper for Baidu search.
    """
    key = retrieval_cache.make_key(query)
    hit = retrieval_cache.get(key)
    if hit is not None:
        return hit

    # base_search_tool is already a LangChain Tool
    result = base_search_tool.invoke({"query": query})
    retrieval_cache.set(key, result)
    return result


search_tool_v2 = api_baidu_search_cached

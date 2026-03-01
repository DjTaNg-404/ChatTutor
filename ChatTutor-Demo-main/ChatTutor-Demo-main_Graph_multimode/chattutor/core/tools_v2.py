from langchain_core.tools import tool

from chattutor.core.cache import retrieval_cache
from chattutor.core.tools import api_baidu_search as base_search_tool


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


# wrap kg_search with caching as well (if available)
try:
    from chattutor.core.tools import kg_search as _kg_search_base

    @tool("kg_search")
    def kg_search_cached(query: str) -> str:
        """Cached knowledge graph lookup.

        This wraps :func:`chattutor.core.tools.kg_search` and stores results in
        the retrieval cache to speed up repeated queries.  The key is
        prefixed with "kg" to avoid colliding with other tools.
        """
        key = retrieval_cache.make_key(query, prefix="kg")
        hit = retrieval_cache.get(key)
        if hit is not None:
            return hit
        result = _kg_search_base.invoke({"query": query})
        retrieval_cache.set(key, result)
        return result

    kg_tool_v2 = kg_search_cached
except ImportError:
    kg_tool_v2 = None

"""将数据库连接类错误转为可读的 HTTP 503。"""

from __future__ import annotations

from fastapi import HTTPException, status

_DB_HINT = (
    "数据库未连接。请在本机先启动 PostgreSQL（默认端口 5432），"
    "并在项目根目录执行: alembic upgrade head。"
    "一键启动依赖（需 Docker）: bash scripts/start_local_deps.sh"
)


def _is_connection_failure(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    markers = (
        "connect call failed",
        "connection refused",
        "could not connect",
        "errno 61",
        "errno 111",
        "name or service not known",
        "timeout",
        "server closed the connection unexpectedly",
    )
    return any(m in text for m in markers) or isinstance(
        exc, (ConnectionError, OSError, TimeoutError)
    )


async def await_db(coro):
    """执行异步 DB 调用；若为连接失败则返回 503。"""
    try:
        return await coro
    except Exception as e:
        if _is_connection_failure(e):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=_DB_HINT,
            ) from e
        raise

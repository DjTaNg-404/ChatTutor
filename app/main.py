from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.history import router as history_router
from app.api.notes import router as notes_router
from app.api.task_plan import router as task_plan_router
from app.api.tasks import router as tasks_router
from app.api.auth import router as auth_router
from app.core.config import settings
from app.core.logging_config import setup_logging, LoggingMiddleware
from app.core.rate_limiter import setup_rate_limiting
from app.core.langfuse_callback import tracer


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    setup_logging(level="INFO", json_format=True)

    # Initialize database — always ensure all tables exist, not just users
    # (create_all is idempotent: it only creates tables that are missing)
    try:
        from app.db.engine import init_db
        await init_db()
    except Exception as e:
        print(f"Warning: Database initialization failed: {e}")
        print(
            "      → 登录/注册需要 PostgreSQL。Docker 一键: bash scripts/start_local_deps.sh"
        )

    # Initialize Redis
    try:
        from app.core.redis_client import init_redis
        await init_redis()
    except Exception as e:
        print(f"Warning: Redis initialization failed: {e}")

    try:
        from app.core.kafka_bus import start_kafka
        await start_kafka()
    except Exception as e:
        print(f"Warning: Kafka startup skipped: {e}")

    print("✅ ChatTutor API started")

    yield

    # Shutdown
    tracer.shutdown()

    try:
        from app.core.kafka_bus import stop_kafka
        await stop_kafka()
    except Exception:
        pass

    try:
        from app.core.redis_client import close_redis
        await close_redis()
    except Exception:
        pass

    try:
        from app.db.engine import close_db
        await close_db()
    except Exception:
        pass

    print("👋 ChatTutor API shutdown complete")


app = FastAPI(
    title="ChatTutor API",
    description="Backend API for ChatTutor - AI Learning Assistant",
    version="1.0.0",
    lifespan=lifespan,
)

# ===== Middleware =====

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limiting Middleware
setup_rate_limiting(app)

# Logging Middleware (optional - for detailed request logging)
# app.add_middleware(LoggingMiddleware)

# ===== Routes =====

app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(chat_router, prefix="/api/v1", tags=["Chat"])
app.include_router(history_router, prefix="/api/v1/history", tags=["History"])
app.include_router(notes_router, prefix="/api/v1/notes", tags=["Notes"])
app.include_router(task_plan_router, prefix="/api/v1/agent", tags=["Task Plan"])
app.include_router(tasks_router, prefix="/api/v1", tags=["Tasks"])

if settings.KG_ENABLED:
    from app.api.kg import router as kg_router
    app.include_router(kg_router, prefix="/api/v1/kg", tags=["Knowledge Graph"])


@app.get("/")
async def root():
    return {"message": "Welcome to ChatTutor API"}


@app.get("/health")
async def health_check():
    """
    Health check for网关 / K8s。含 Redis 探测；Kafka 为可选不阻塞 healthy。
    """
    from redis.asyncio import Redis

    from app.core.redis_client import get_redis_pool

    body: dict = {
        "status": "healthy",
        "service": "ChatTutor API",
        "version": "1.0.0",
        "checks": {},
    }
    r: Redis | None = None
    try:
        r = Redis(connection_pool=get_redis_pool())
        await r.ping()
        body["checks"]["redis"] = "ok"
    except Exception as e:
        body["checks"]["redis"] = f"error: {e!s}"
        body["status"] = "degraded"
    finally:
        if r is not None:
            try:
                await r.aclose()
            except Exception:
                pass

    if settings.KAFKA_ENABLED:
        body["checks"]["kafka"] = "enabled"

    return body

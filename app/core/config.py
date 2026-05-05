import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # API Keys
    # os.getenv 兼容 ModelScope 等平台的直接环境变量注入
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "sk-02973663a9d74207be7bfda17ed09f00")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "sk-02973663a9d74207be7bfda17ed09f00")
    BAIDU_API_KEY: str = os.getenv("BAIDU_API_KEY", "")

    # Model Configuration
    # 默认使用 deepseek-chat
    MODEL_NAME: str = "deepseek-chat"
    EVALUATOR_MODEL_NAME: str = "deepseek-chat"

    # KG Configuration (disabled by default)
    KG_ENABLED: bool = False

    # Constants
    MODE_ACTIVE: str = "active"
    MODE_SOCRATIC: str = "socratic"

    # Thresholds
    MAX_ITERATIONS: int = 5  # 防止苏格拉底模式下死循环追问的最大次数

    # ===== Production: Database =====
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://chattutor:chattutor123@localhost:5432/chattutor"
    )

    # ===== Production: Redis =====
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # ===== Kafka / Redpanda（可选，用于异步事件）=====
    KAFKA_ENABLED: bool = os.getenv("KAFKA_ENABLED", "false").lower() in ("1", "true", "yes", "on")
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    KAFKA_TOPIC_EVENTS: str = os.getenv("KAFKA_TOPIC_EVENTS", "chattutor.events")

    # ===== Gunicorn（仅启动脚本读取，应用内可不使用）=====
    GUNICORN_WORKERS: int = int(os.getenv("GUNICORN_WORKERS", "4"))

    # ===== Production: Authentication =====
    # Note: JWT_SECRET_KEY must be set in production via environment variable
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 小时

    # ===== Production: Observability (Langfuse) =====
    LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
    LANGFUSE_ENABLED: bool = False  # 默认关闭，需手动开启

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

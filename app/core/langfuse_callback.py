"""
Langfuse integration for LLM tracing.

Provides:
- Langfuse client for manual tracing
- Token usage tracking
"""

from typing import Optional
from langfuse import Langfuse

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class LangfuseTracer:
    """
    Langfuse tracer for LLM call tracking.
    """

    def __init__(self):
        self.enabled = bool(
            settings.LANGFUSE_PUBLIC_KEY
            and settings.LANGFUSE_SECRET_KEY
            and settings.LANGFUSE_ENABLED
        )
        self._client: Optional[Langfuse] = None

        if self.enabled:
            self._initialize()

    def _initialize(self) -> None:
        """Initialize Langfuse client."""
        try:
            self._client = Langfuse(
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                secret_key=settings.LANGFUSE_SECRET_KEY,
                host=settings.LANGFUSE_HOST,
            )
            logger.info("Langfuse tracing enabled", host=settings.LANGFUSE_HOST)
        except Exception as e:
            logger.error("Failed to initialize Langfuse", error=str(e))
            self.enabled = False
            self._client = None

    @property
    def client(self) -> Optional[Langfuse]:
        """Get the Langfuse client."""
        return self._client

    def shutdown(self) -> None:
        """Shutdown Langfuse client and flush remaining events."""
        if self._client:
            try:
                self._client.flush()
            except Exception as e:
                logger.warning("Failed to shutdown Langfuse", error=str(e))


# Global tracer instance
tracer = LangfuseTracer()


def get_langfuse_client() -> Optional[Langfuse]:
    """Get the Langfuse client."""
    return tracer.client


def flush_langfuse() -> None:
    """Flush pending Langfuse events."""
    if tracer._client:
        try:
            tracer._client.flush()
        except Exception:
            pass

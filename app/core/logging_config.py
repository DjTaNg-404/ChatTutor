"""
Logging configuration for ChatTutor production deployment.

Provides:
- Structured JSON logging
- Request/response logging middleware
- Log correlation IDs (request_id, user_id, session_id)
"""

import logging
import sys
from datetime import datetime
from typing import Any, Dict
import structlog
from structlog.types import Processor


def setup_logging(level: str = "INFO", json_format: bool = True) -> None:
    """
    Setup structured logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        json_format: Whether to use JSON format for logs
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Shared processors for both console and JSON logging
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
    ]

    if json_format:
        # JSON format for production
        structlog.configure(
            processors=shared_processors
            + [
                structlog.processors.dict_tracebacks,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        # Console format for development (with colors via rich if available)
        structlog.configure(
            processors=shared_processors
            + [
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )

    # Configure standard library logging to use structlog
    logging_config = logging.getLogger()
    logging_config.setLevel(log_level)

    # Remove existing handlers
    logging_config.handlers = []

    # Add stream handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logging_config.addHandler(handler)


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """
    Get a structured logger instance.

    Usage:
        logger = get_logger(__name__)
        logger.info("Something happened", extra_data={"key": "value"})
    """
    return structlog.get_logger(name)


class LoggingMiddleware:
    """
    FastAPI middleware for logging requests and responses.

    Adds:
    - Request ID tracking
    - Request/response timing
    - User ID from JWT token
    """

    def __init__(self, app):
        self.app = app
        self.logger = get_logger("api")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        import time
        import uuid
        from contextvars import ContextVar

        # Generate request ID
        request_id = str(uuid.uuid4())[:8]

        # Set request ID in context
        request_id_ctx: ContextVar[str] = ContextVar("request_id", default=request_id)
        structlog.contextvars.set_contextvars(request_id=request_id)

        start_time = time.time()

        # Log request
        method = scope["method"]
        path = scope["path"]

        await self.logger.ainfo(
            "Request started",
            method=method,
            path=path,
            request_id=request_id,
        )

        # Process request
        response_started = False

        async def send_wrapper(message):
            nonlocal response_started

            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                process_time = time.time() - start_time

                await self.logger.ainfo(
                    "Request completed",
                    method=method,
                    path=path,
                    request_id=request_id,
                    status_code=status_code,
                    process_ms=round(process_time * 1000, 2),
                )

            await send(message)

        try:
            return await self.app(scope, receive, send_wrapper)
        except Exception as e:
            await self.logger.aerror(
                "Request failed",
                method=method,
                path=path,
                request_id=request_id,
                error=str(e),
            )
            raise
        finally:
            # Clear context
            structlog.contextvars.clear_contextvars()

"""
Kafka / Redpanda 异步事件总线（可选）。

用于对话完成、中断等事件的下游消费（审计、推荐、离线分析），与主请求解耦。
未安装 aiokafka 或 KAFKA_ENABLED=false 时不启动生产者。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_producer: Any = None
_start_lock = asyncio.Lock()


async def _ensure_producer():
    global _producer
    if not settings.KAFKA_ENABLED:
        return None
    if _producer is not None:
        return _producer
    async with _start_lock:
        if _producer is not None:
            return _producer
        try:
            from aiokafka import AIOKafkaProducer
        except ImportError:
            logger.warning("aiokafka 未安装，已跳过 Kafka 生产者启动")
            return None
        try:
            p = AIOKafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
            )
            await p.start()
            _producer = p
            logger.info("Kafka producer started: %s", settings.KAFKA_BOOTSTRAP_SERVERS)
        except Exception as e:
            logger.exception("Kafka producer 启动失败: %s", e)
            _producer = None
    return _producer


async def start_kafka():
    """应用启动时调用（失败不阻止 API 启动）。"""
    try:
        await _ensure_producer()
    except Exception as e:
        logger.warning("Kafka 启动跳过: %s", e)


async def stop_kafka():
    global _producer
    if _producer is None:
        return
    try:
        await _producer.stop()
    except Exception as e:
        logger.warning("Kafka producer stop: %s", e)
    finally:
        _producer = None


async def publish_event(topic: str, payload: Dict[str, Any]) -> None:
    """
    发送一条事件（失败仅打日志，不影响主链路）。

    payload 勿放用户消息全文，仅放 id 与统计字段。
    """
    if not settings.KAFKA_ENABLED:
        return
    p = await _ensure_producer()
    if p is None:
        return
    try:
        await p.send_and_wait(topic, payload)
    except Exception:
        logger.exception("Kafka send failed topic=%s", topic)


async def emit_chat_event(event_type: str, payload: Dict[str, Any]) -> None:
    """在 async 路由里 fire-and-forget，不阻塞响应体返回。"""

    async def _run():
        await publish_event(
            settings.KAFKA_TOPIC_EVENTS,
            {"type": event_type, **payload},
        )

    asyncio.create_task(_run())

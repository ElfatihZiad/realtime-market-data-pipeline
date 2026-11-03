"""Kafka producer wrapper.

Messages are keyed by instrument_id. That is not cosmetic: the key is what
pins every tick for one instrument to one partition, which is the only reason
per-instrument ordering survives. The previous version of this project sent
unkeyed messages and therefore had no ordering guarantee at all.
"""

from __future__ import annotations

from typing import Any

import structlog
from confluent_kafka import Producer

log = structlog.get_logger(__name__)


class TickProducer:
    def __init__(self, bootstrap: str, topic: str, dlq_topic: str) -> None:
        self._topic = topic
        self._dlq_topic = dlq_topic
        self._producer = Producer(
            {
                "bootstrap.servers": bootstrap,
                "client.id": "ingest-crypto",
                # Durability over throughput: this is market data, and a demo
                # that silently drops trades is worse than a slower one.
                "acks": "all",
                "enable.idempotence": True,
                "compression.type": "lz4",
                "linger.ms": 20,
                "batch.size": 64 * 1024,
            }
        )

    def _on_delivery(self, err: Any, msg: Any) -> None:
        if err is not None:
            log.error("delivery_failed", error=str(err), topic=msg.topic() if msg else None)

    def send_tick(self, key: str, payload: bytes) -> None:
        self._producer.produce(
            topic=self._topic,
            key=key.encode(),
            value=payload,
            on_delivery=self._on_delivery,
        )
        self._producer.poll(0)

    def send_dlq(self, reason: str, raw: bytes) -> None:
        """Malformed input is kept, not swallowed.

        The old code had `except: pass` around its parsing.
        """
        self._producer.produce(
            topic=self._dlq_topic,
            key=reason.encode(),
            value=raw,
            on_delivery=self._on_delivery,
        )
        self._producer.poll(0)

    def flush(self, timeout: float = 10.0) -> int:
        return int(self._producer.flush(timeout))

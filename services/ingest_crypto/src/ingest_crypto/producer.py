"""Kafka producer: Avro values, registered against Confluent Schema Registry.

Messages are keyed by instrument_id. That is not cosmetic: the key is what pins
every tick for one instrument to one partition, which is the only reason
per-instrument ordering survives. The previous version of this project sent
unkeyed messages and therefore had no ordering guarantee at all.

The value serialiser registers `contracts/market/v1/tick.avsc` under the
subject `<topic>-value` on first use. From then on the registry rejects any
incompatible change to the contract, which is the point of having one.
"""

from __future__ import annotations

from typing import Any

import structlog
from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import MessageField, SerializationContext
from mdp_core import Tick, load_schema

log = structlog.get_logger(__name__)


class TickProducer:
    def __init__(
        self, bootstrap: str, topic: str, dlq_topic: str, schema_registry_url: str
    ) -> None:
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
        self._serialize = AvroSerializer(
            SchemaRegistryClient({"url": schema_registry_url}),
            load_schema("tick"),
            lambda tick, _ctx: tick,
        )
        self._ctx = SerializationContext(topic, MessageField.VALUE)

    def _on_delivery(self, err: Any, msg: Any) -> None:
        if err is not None:
            log.error("delivery_failed", error=str(err), topic=msg.topic() if msg else None)

    def send_tick(self, tick: Tick) -> None:
        self._producer.produce(
            topic=self._topic,
            key=tick.instrument_id.encode(),
            value=self._serialize(tick.to_dict(), self._ctx),
            on_delivery=self._on_delivery,
        )
        self._producer.poll(0)

    def send_dlq(self, reason: str, raw: bytes) -> None:
        """Malformed input is kept, not swallowed.

        Written as the raw bytes we received, deliberately un-Avro'd: the whole
        point of the DLQ is to hold things that did not fit the schema.
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

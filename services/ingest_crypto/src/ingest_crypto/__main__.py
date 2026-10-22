"""Entry point: Coinbase WS -> validate -> Kafka.

Run with:  just ingest
"""

from __future__ import annotations

import asyncio
import json
import signal
import time
from typing import Any

import structlog
import websockets
from mdp_core import configure_logging, get_settings
from prometheus_client import Counter, Histogram, start_http_server
from websockets.asyncio.client import connect

from ingest_crypto.coinbase import MalformedMessage, is_trade, subscribe_frame, to_tick
from ingest_crypto.producer import TickProducer

log = structlog.get_logger("ingest_crypto")

TICKS = Counter("mdp_ticks_ingested_total", "Ticks accepted and produced", ["instrument_id"])
REJECTED = Counter("mdp_ticks_rejected_total", "Messages routed to the DLQ", ["reason"])
RECONNECTS = Counter("mdp_feed_reconnects_total", "WebSocket reconnections")
FEED_LATENCY = Histogram(
    "mdp_feed_latency_seconds",
    "venue event_time -> our ingest_time",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

_shutdown = asyncio.Event()


def _handle_signal() -> None:
    log.info("shutdown_requested")
    _shutdown.set()


async def _pump(ws: Any, producer: TickProducer) -> None:
    async for message in ws:
        if _shutdown.is_set():
            return

        raw_bytes = message if isinstance(message, bytes) else message.encode()
        try:
            payload = json.loads(raw_bytes)
        except json.JSONDecodeError as exc:
            REJECTED.labels(reason="invalid_json").inc()
            producer.send_dlq("invalid_json", raw_bytes)
            log.warning("invalid_json", error=str(exc))
            continue

        msg_type = payload.get("type")
        if msg_type == "subscriptions":
            log.info("subscribed", channels=payload.get("channels"))
            continue
        if msg_type == "error":
            log.error("feed_error", message=payload.get("message"))
            continue
        if not is_trade(payload):
            continue

        try:
            tick = to_tick(payload, ingest_time_us=int(time.time() * 1_000_000))
        except MalformedMessage as exc:
            REJECTED.labels(reason="malformed").inc()
            producer.send_dlq("malformed", raw_bytes)
            log.warning("malformed_tick", error=str(exc))
            continue

        producer.send_tick(tick.instrument_id, tick.SerializeToString())
        TICKS.labels(instrument_id=tick.instrument_id).inc()
        FEED_LATENCY.observe((tick.ingest_time_us - tick.event_time_us) / 1_000_000)


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    start_http_server(settings.metrics_port)

    producer = TickProducer(
        bootstrap=settings.kafka_bootstrap,
        topic=settings.ticks_topic,
        dlq_topic=settings.ticks_dlq_topic,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    log.info(
        "starting",
        url=settings.coinbase_ws_url,
        symbols=settings.symbols,
        kafka=settings.kafka_bootstrap,
        metrics_port=settings.metrics_port,
    )

    backoff = 1.0
    while not _shutdown.is_set():
        try:
            async with connect(settings.coinbase_ws_url, ping_interval=20) as ws:
                await ws.send(subscribe_frame(settings.symbols))
                backoff = 1.0  # reconnected cleanly; reset the ramp
                await _pump(ws, producer)
        except asyncio.CancelledError:
            raise
        except (OSError, websockets.exceptions.WebSocketException) as exc:
            if _shutdown.is_set():
                break
            RECONNECTS.inc()
            log.warning("feed_disconnected", error=str(exc), retry_in=round(backoff, 1))
            try:
                await asyncio.wait_for(_shutdown.wait(), timeout=backoff)
            except TimeoutError:
                pass
            # Exponential backoff, capped. The old producer had no retry at all:
            # a single failed request returned a zero-priced fake tick instead.
            backoff = min(backoff * 2, 30.0)

    pending = producer.flush()
    log.info("stopped", undelivered=pending)


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

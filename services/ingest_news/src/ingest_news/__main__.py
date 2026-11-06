"""Poll crypto news RSS, score sentiment, produce to Kafka.

Run with:  just news
"""

from __future__ import annotations

import signal
import time
from collections import OrderedDict

import httpx
import structlog
from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import MessageField, SerializationContext
from mdp_core import configure_logging, configure_tracing, get_settings, load_schema
from prometheus_client import Counter, Gauge, start_http_server

from ingest_news.feeds import FEEDS, Article, parse_feed
from ingest_news.sentiment import build_scorer

log = structlog.get_logger("ingest_news")

ARTICLES = Counter("mdp_news_articles_total", "Articles produced", ["instrument_id", "source"])
FEED_ERRORS = Counter("mdp_news_feed_errors_total", "Feed fetch failures", ["source"])
SENTIMENT = Gauge("mdp_news_sentiment", "Latest sentiment score", ["instrument_id"])

# Bounded de-duplication. The feeds return the same articles on every poll;
# an unbounded set would grow for as long as the process runs.
SEEN_MAX = 5_000

_stop = False


def _handle_signal(*_: object) -> None:
    global _stop
    log.info("shutdown_requested")
    _stop = True


def fetch(client: httpx.Client, source: str, url: str) -> list[Article]:
    try:
        resp = client.get(url)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        FEED_ERRORS.labels(source=source).inc()
        log.warning("feed_fetch_failed", source=source, error=str(exc))
        return []
    return parse_feed(source, resp.content)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_tracing("ingest-news")
    start_http_server(settings.news_metrics_port)

    scorer = build_scorer(settings.sentiment_scorer)
    serialize = AvroSerializer(
        SchemaRegistryClient({"url": settings.schema_registry_url}),
        load_schema("news"),
        lambda item, _ctx: item,
    )
    ctx = SerializationContext(settings.news_topic, MessageField.VALUE)
    producer = Producer(
        {
            "bootstrap.servers": settings.kafka_bootstrap,
            "client.id": "ingest-news",
            "acks": "all",
            "enable.idempotence": True,
            "compression.type": "lz4",
        }
    )

    seen: OrderedDict[str, None] = OrderedDict()
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    log.info(
        "starting",
        scorer=scorer.name,
        feeds=sorted(FEEDS),
        interval_s=settings.news_poll_seconds,
        metrics_port=settings.news_metrics_port,
    )

    headers = {"User-Agent": "market-data-pipeline/0.5 (RSS reader)"}
    with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
        while not _stop:
            produced = 0
            for source, url in FEEDS.items():
                for article in fetch(client, source, url):
                    if article.article_id in seen:
                        continue
                    seen[article.article_id] = None
                    while len(seen) > SEEN_MAX:
                        seen.popitem(last=False)

                    score = scorer.score(article.title, article.instrument_id)
                    payload = {
                        "article_id": article.article_id,
                        "instrument_id": article.instrument_id,
                        "source": article.source,
                        "title": article.title,
                        "url": article.url,
                        "published_at_us": article.published_at_us,
                        "ingest_time_us": int(time.time() * 1_000_000),
                        "sentiment": score,
                        "scorer": scorer.name,
                    }
                    producer.produce(
                        topic=settings.news_topic,
                        key=article.instrument_id.encode(),
                        value=serialize(payload, ctx),
                    )
                    producer.poll(0)
                    ARTICLES.labels(
                        instrument_id=article.instrument_id, source=article.source
                    ).inc()
                    SENTIMENT.labels(instrument_id=article.instrument_id).set(score)
                    produced += 1

            producer.flush(10)
            if produced:
                log.info("produced", articles=produced, tracked=len(seen))

            # Interruptible sleep: a 5-minute poll interval should not mean a
            # 5-minute wait for SIGTERM.
            for _ in range(settings.news_poll_seconds):
                if _stop:
                    break
                time.sleep(1)

    producer.flush(10)
    log.info("stopped")


if __name__ == "__main__":
    main()

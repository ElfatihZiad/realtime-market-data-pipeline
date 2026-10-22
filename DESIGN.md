# Design

## What this project is for

A real-time market data platform, rebuilt to be worth reading in 2027. In 2022,
"uses Kafka" was the interesting part; it is now assumed. What this rebuild aims
to demonstrate instead:

1. **Streaming correctness** — event time vs. processing time, watermarks, late
   data, exactly-once sinks.
2. **Contract discipline** — schemas as versioned artifacts, not `str(dict)`.
3. **Operability** — "what is your p99 end-to-end latency and current consumer
   lag?" answered by pointing at a dashboard.
4. **Cost judgement** — knowing what this costs to run, and having made choices.

Every component below earns its place against one of those. Anything that serves
none of them was cut (see *Deliberately not doing* at the end).

## Target architecture

```
                 ┌─ Coinbase / Binance WS ─┐
SOURCES          ├─ Finnhub / Alpaca WS ────┤   live
                 ├─ SEC EDGAR companyfacts ─┤
                 ├─ FRED API ───────────────┤   batch, daily
                 └─ GDELT / NewsAPI ────────┘
                              │
                     ingest services — async, Pydantic-validated
                              │  Protobuf, keyed by instrument_id
                              ▼
                 Kafka 4.3 KRaft  ·  ticks.raw  ticks.dlq  news.raw
                              │
                     Flink 2.3 SQL — bronze → silver → gold
                     watermarks, event-time windows, late-data side output
                    ┌─────────┴───────────┐
                    ▼                     ▼
            ClickHouse (hot)      Iceberg v2 on S3/MinIO
                    │              dbt marts (medallion)
                    └──────────┬──────────┘
                               ▼
                    FastAPI  →  Next.js dashboard (hosted)

   Airflow 3 ──── batch only: fundamentals, macro, dbt, Iceberg maintenance
   Prometheus + Grafana + OTel ──── lag, latency, throughput, SLOs
```

The streaming path is deliberately **not** orchestrated — see
[ADR 0004](docs/adr/0004-airflow-for-batch-only.md).

## Stack

| Layer | Choice | Note |
|---|---|---|
| Language | Python 3.14, `uv` workspace | 3.13 floor |
| Feed | Coinbase public WS (primary), equities secondary | [ADR 0005](docs/adr/0005-crypto-as-primary-feed.md) |
| Broker | Apache Kafka 4.3, KRaft | ZooKeeper was removed in Kafka 4.0 |
| Wire format | Avro + Confluent Schema Registry | [ADR 0008](docs/adr/0008-avro-and-schema-registry-over-protobuf.md) |
| Stream processing | Flink 2.2.1, SQL files | [ADR 0003](docs/adr/0003-flink-sql-over-pyflink.md), [0010](docs/adr/0010-flink-version-follows-connectors.md) |
| Hot store | ClickHouse 26.9 | [ADR 0001](docs/adr/0001-drop-cassandra-for-clickhouse.md) |
| Lake | Iceberg v2 on MinIO → S3 | [ADR 0002](docs/adr/0002-iceberg-v2-not-v3.md) |
| Transform | dbt, medallion models | verify ClickHouse adapter support on Fusion |
| Orchestration | Airflow 3 | batch only |
| Serving | FastAPI + WebSocket push | replaces Bokeh's 600 ms client poll |
| Frontend | Next.js + lightweight-charts | Phase 5 |
| Ops | Prometheus, Grafana, OpenTelemetry | Phase 4 |
| Quality | Pydantic at the edge, DLQ, dbt tests | |
| CI | GitHub Actions: ruff, mypy, pytest, testcontainers | |

## Phases

Each phase merges to `main` and is independently demoable. That constraint
matters more than the contents: the realistic failure mode is six half-finished
phases.

**Phase 1 — streaming skeleton. Done.**
Contracts, Kafka KRaft, Coinbase ingest with DLQ and backoff, ClickHouse via the
Kafka engine, FastAPI + a live chart. *Exit: `just up` on a clean clone gives a
live-updating chart.* Met.

**Phase 2 — real stream processing. Done.**
Flink SQL 1m/5m OHLCV bars with VWAP, rolling realised volatility and windowed
z-score spike detection. Explicit watermarks with late events routed to
`ticks.late` via `CURRENT_WATERMARK()`. Avro + Schema Registry replacing bare
Protobuf ([ADR 0008](docs/adr/0008-avro-and-schema-registry-over-protobuf.md)).
*Exit met:* `just check-late` injects a trade behind the watermark and proves it
is recorded without mutating a closed bar; `just check-bars` reconciles Flink's
event-time bars against an independent replay of the stored ticks and they match
exactly.

*Carried to Phase 3:* the **Iceberg sink**. It needs a catalog, object storage
and connector jars, and it belongs with the lake and dbt work rather than
bolted onto the windowing phase. ClickHouse is the only sink today.

**Phase 3 — warehouse and batch.** Iceberg + dbt medallion marts. SEC EDGAR
fundamentals, FRED macro. Airflow 3 for batch, including Iceberg compaction and
snapshot expiry. *Exit: `dbt test` green in CI; a backfill is reproducible.*

**Phase 4 — operability.** Full CI gate, testcontainers integration tests,
Prometheus/Grafana, OTel traces. Metrics that matter: end-to-end latency,
consumer lag, bars emitted vs. expected, late-record count, decode failures.
*Exit: a p99 latency dashboard, and a lag alert that fires when a consumer is paused.*

**Phase 5 — portfolio surface.** Next.js dashboard, hosted and public. README
with the demo link first. Regenerated architecture diagram (the current one in
`images/` still shows ZooKeeper). Delete `legacy/`.
*Exit: a stranger clicks a URL and watches live data without cloning anything.*

**Phase 6 — differentiator.** Streaming news sentiment joined to price moves: a
windowed stream-to-stream join with watermarks on both sides. One differentiator
done well, not three half-finished.

## Deliberately not doing

- **Kubernetes.** Compose locally, Terraform for a small managed footprint. A k8s
  manifest for a single-node demo is costume jewellery.
- **Great Expectations.** Pydantic at the edge plus dbt tests covers it without a
  third quality tool.
- **Spark.** Nothing here needs it; Flink owns the streaming story.
- **Keeping Cassandra** because it is already there.
- **A second differentiator** before the first is finished.

## Cost

Kafka + Flink + ClickHouse running 24/7 in any cloud is real money for a side
project. The split: the **full stack runs locally** (`just up` is the reviewer's
path), and only a **thin always-on slice** is hosted for the public demo — one
ingest process → ClickHouse dev tier → FastAPI → static frontend. Flink runs
locally and on demand.

To be filled in with actual figures once Phase 5 is deployed.

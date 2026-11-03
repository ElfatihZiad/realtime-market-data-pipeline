# Real-time market data pipeline

A streaming pipeline for market data: a live trade feed into Kafka, processed on
event time, served to a dashboard that updates as trades happen.

> **Status — rebuild in progress.** This project was originally built in 2021/22
> on Kafka 2.3 + ZooKeeper, Cassandra and Bokeh. It is being rebuilt in phases;
> **Phase 1 of 6 is complete and runs today**. The original code is preserved
> under [`legacy/`](legacy/) for reference. See [DESIGN.md](DESIGN.md) for the
> full plan and [`docs/adr/`](docs/adr/) for the decisions behind it.

## What works right now (Phase 1)

```
Coinbase WS  ──▶  ingest-crypto  ──▶  Kafka 4.3 (KRaft)  ──▶  ClickHouse 26.9  ──▶  FastAPI  ──▶  live chart
   public         validate +           ticks.raw              Kafka engine +        REST +
   24/7 feed      normalise            (Protobuf)             materialised view     WebSocket push
                      │
                      └──▶ ticks.dlq  (malformed input is kept, not swallowed)
```

- **Real trades only.** Coinbase's public feed is keyless and runs 24/7, so the
  dashboard is live whenever you open it. Nothing here fabricates a price.
- **Contracts are load-bearing.** [`contracts/market/v1/tick.proto`](contracts/market/v1/tick.proto)
  is both the producer's schema and the schema ClickHouse decodes the topic with.
- **The pipeline measures itself.** Every tick carries the venue's `event_time`
  and our `ingest_time`; their difference is end-to-end latency, shown on the
  dashboard (p50 ≈ 5 ms, p99 ≈ 120 ms locally).

## Quickstart

Needs Docker, [`uv`](https://docs.astral.sh/uv/) and [`just`](https://just.systems).

```bash
just install     # sync the uv workspace
just up          # Kafka + ClickHouse, with topics and schema created
just ingest      # start the Coinbase feed   (leave running)
just api         # start the dashboard       (leave running, in another shell)
```

Then open <http://localhost:8000>. Data appears within a few seconds.

```bash
just test        # unit tests
just lint        # ruff + mypy --strict
just down        # tear down, including volumes
```

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | Streaming skeleton: feed → Kafka → ClickHouse → live chart | **done** |
| 2 | Flink SQL: event-time OHLCV bars, VWAP, volatility, watermarks, late data | next |
| 3 | Iceberg + dbt marts; SEC EDGAR fundamentals, FRED macro; Airflow 3 for batch | |
| 4 | CI gate, testcontainers integration tests, Prometheus/Grafana, SLOs | |
| 5 | Next.js dashboard, hosted demo, diagrams; delete `legacy/` | |
| 6 | Streaming news sentiment joined to price moves | |

## Layout

```
contracts/     protobuf schemas — the source of truth for the wire format
services/      ingest_crypto (feed → Kafka), api (ClickHouse → REST/WS)
libs/          mdp_core: config, logging, generated contract code
infra/         ClickHouse schema and format schemas
docs/adr/      why things are the way they are
legacy/        the 2021–22 version, kept for reference until Phase 5
```

## Licence

See [LICENSE](LICENSE).

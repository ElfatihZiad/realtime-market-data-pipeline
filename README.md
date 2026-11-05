# Real-time market data pipeline

A streaming pipeline for market data: a live trade feed into Kafka, processed on
event time, served to a dashboard that updates as trades happen.

> **Status — rebuild in progress.** This project was originally built in 2021/22
> on Kafka 2.3 + ZooKeeper, Cassandra and Bokeh. It is being rebuilt in phases;
> **Phases 1–4 of 6 are complete and run today**. The original code is preserved
> under [`legacy/`](legacy/) for reference. See [DESIGN.md](DESIGN.md) for the
> full plan and [`docs/adr/`](docs/adr/) for the decisions behind it.

## What works right now (Phase 1)

```
Coinbase WS ─▶ ingest ─▶ Kafka 4.3 ─▶ Flink 2.1 SQL ─┬─▶ bars.1m/5m ─▶ ClickHouse ─▶ dbt ─▶ FastAPI ─▶ chart
  public       validate   ticks.raw   event-time     ├─▶ signals.1m      (hot)      marts
  24/7 feed    normalise  (Avro +     windows,       ├─▶ ticks.late
                  │        registry)  watermarks     └─▶ Iceberg on S3 (history, Parquet)
                  └─▶ ticks.dlq
                      (unparseable)                   Airflow 3 ─▶ EDGAR · FRED · dbt · Iceberg upkeep
```

- **Real trades only.** Coinbase's public feed is keyless and runs 24/7, so the
  dashboard is live whenever you open it. Nothing here fabricates a price.
- **Bars are closed by watermarks, not by query time.** A bar is emitted once
  Flink believes the window is complete; trades arriving later are recorded in
  `market.ticks_late` rather than silently folded into a number someone already
  acted on. See [ADR 0009](docs/adr/0009-watermarks-and-late-data.md).
- **Contracts are load-bearing.** [`contracts/market/v1/`](contracts/market/v1/)
  holds the Avro schemas; the registry enforces compatibility on every write.
- **The pipeline measures itself.** Every tick carries the venue's `event_time`
  and our `ingest_time`; their difference is end-to-end latency, shown on the
  dashboard and rolled up daily in `fct_pipeline_health` alongside the
  late-arrival rate and decode failures.
- **Two stores, written from the same stream.** ClickHouse is the hot store;
  Iceberg on object storage is the history. Neither is the other's cache.
- **It can be operated, not just run.** Prometheus scrapes the services, Kafka
  consumer lag and Flink; traces go to Jaeger; and five SLOs live as alerting
  rules rather than as sentences. See [ADR 0016](docs/adr/0016-observability-and-slos.md).

## Quickstart

Needs Docker, [`uv`](https://docs.astral.sh/uv/) and [`just`](https://just.systems).

```bash
just install     # sync the uv workspace
just up          # Kafka + ClickHouse, with topics and schema created
just ingest      # start the Coinbase feed    (leave running)
just stream      # submit the Flink SQL jobs  (bars, signals, Iceberg)
just dbt-build   # build and test the marts
just api         # start the dashboard        (leave running, another shell)
```

Grafana <http://localhost:3000> · Prometheus <http://localhost:9090> ·
Jaeger <http://localhost:16686> · Flink <http://localhost:8081> ·
Airflow <http://localhost:8082> · schemas via `just schemas`.

Then open <http://localhost:8000>. Data appears within a few seconds.

```bash
just test        # unit tests
just verify      # streaming correctness: late-data proof + bar reconciliation
just lint        # ruff + mypy --strict
just down        # tear down, including volumes
```

`just verify` is the interesting one. `check-late` injects a trade behind the
watermark and asserts it is recorded without mutating a closed bar;
`check-bars` recomputes every settled window from stored ticks and asserts it
matches what Flink emitted.

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | Streaming skeleton: feed → Kafka → ClickHouse → live chart | **done** |
| 2 | Flink SQL: event-time OHLCV bars, VWAP, volatility, watermarks, late data | **done** |
| 3 | Iceberg sink + dbt marts; SEC EDGAR fundamentals, FRED macro; Airflow 3 for batch | **done** |
| 4 | Prometheus + Grafana, OpenTelemetry traces, SLO rules | **done** |
| 5 | Next.js dashboard, hosted demo, diagrams; delete `legacy/` | next |
| 6 | Streaming news sentiment joined to price moves | |

## Layout

```
contracts/      Avro schemas — the source of truth for the wire format
services/       ingest_crypto (feed → Kafka), api (serving), batch (EDGAR, FRED)
stream/         Flink SQL jobs, and the correctness checks for them
warehouse/      dbt project: staging views, marts, 33 tests
orchestration/  Airflow 3 DAGs — batch only
libs/           mdp_core: config, logging, contract loading
infra/          ClickHouse schema, Flink and Airflow images
docs/adr/      why things are the way they are
legacy/        the 2021–22 version, kept for reference until Phase 5
```

## Licence

See [LICENSE](LICENSE).

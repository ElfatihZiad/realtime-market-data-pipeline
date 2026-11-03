# 0014 — dbt medallion layering, and `build` rather than `run` + `test`

**Status:** accepted (Phase 3)

## Context

The streaming pipeline writes raw tables. Turning those into things people
query is transformation work, and hand-written SQL scattered across the
dashboard is how the 2021 version did it — five query sites, each with its own
`ALLOW FILTERING`.

## Decision

Three layers, with dbt owning the top two:

- **Bronze** — `market.*`, written by Kafka engine tables and Flink. dbt
  declares these as sources and never writes them.
- **Silver** — `staging/`, views: typed, deduplicated, late arrivals flagged.
  Views because they are cheap and always current.
- **Gold** — `marts/`, tables: `fct_bars_daily`, `fct_instrument_liquidity`,
  `fct_pipeline_health`. Tables because they are read far more than written.

Orchestration runs `dbt build`, not `dbt run` followed by `dbt test`.

## Consequences

- `build` interleaves run and test per model, so a model whose tests fail never
  becomes an input to anything downstream. `run` then `test` would publish the
  bad model first and complain afterwards.
- 33 tests ship with the models, including four singular tests that encode
  domain rules rather than column constraints: bar grain uniqueness, OHLC
  internal consistency, VWAP inside the bar range, and no trades timestamped in
  our future.
- `fct_pipeline_health` makes operability queryable — throughput, latency
  percentiles, late-arrival rate and decode failures per day. Most portfolio
  projects can say what the data is; far fewer can say how late it was.
- CI runs `dbt build` against an empty ClickHouse, which proves every model
  compiles and executes without needing a broker or a live feed. That is why
  the schema is split into `01-tables.sql` and `02-streaming.sql`.

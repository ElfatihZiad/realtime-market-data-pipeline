# 0001 — Drop Cassandra for ClickHouse

**Status:** accepted (Phase 1)

## Context

The 2021 version stored everything in Cassandra 3.11, with a table per symbol
(`AAPL`, `AAPL_historical`, `AAPL_tick`, …) and `ALLOW FILTERING` on every read
in the dashboard — five separate query sites.

`ALLOW FILTERING` is Cassandra telling you the data model does not match the
access pattern. Cassandra is a write-optimised, partition-key-driven store: it
is excellent when you always know the partition you want. But every query this
project actually issues is an analytical range scan — "all trades for this
instrument over this window, bucketed" — which is the one shape Cassandra is
worst at.

## Decision

Serve from ClickHouse. One `market.ticks` table for all instruments,
`ORDER BY (instrument_id, event_time)`, partitioned by month.

## Consequences

- Range scans and aggregations become the cheap path instead of the expensive one.
- The Kafka table engine + materialised view replaces a hand-written consumer
  loop, deleting the `ast.literal_eval` / `str(dict)` round-trip entirely.
- One table instead of 3·N, so adding an instrument is a data change, not a DDL change.
- Cassandra experience is no longer demonstrated by this repo. Accepted: keeping
  a store to justify having once chosen it is sunk-cost reasoning, and the
  `ALLOW FILTERING` scattered through the old code is evidence against it, not for it.

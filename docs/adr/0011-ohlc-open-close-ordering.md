# 0011 — open/close rest on a stated invariant, not an ORDER BY

**Status:** accepted, with a known limitation (Phase 2)

## Context

A bar's `open` is the price of the earliest trade in the window by **event
time**, and `close` the latest. The natural expression is `MIN_BY(price,
event_time)` / `MAX_BY(price, event_time)` — which this Flink build does not
have. Its window aggregation offers `FIRST_VALUE` / `LAST_VALUE`, which order by
**arrival**, not by event time.

The fully correct alternative is Window Top-N: rank each window's rows by
event time, take rank 1 and rank N, and join those back to the aggregates. That
is three window queries plus two joins, and the joins produce updating results
that an append-only Kafka sink rejects.

## Decision

Use `FIRST_VALUE` / `LAST_VALUE`, and state the invariant that makes them
correct here:

1. Coinbase emits trades for one product in sequence order on one socket.
2. The producer keys by `instrument_id`, so a product's trades land in a single
   Kafka partition.
3. Kafka preserves order within a partition, and Flink reads a partition in
   offset order.

Therefore arrival order equals event-time order **per instrument**, which is the
only ordering `FIRST_VALUE`/`LAST_VALUE` need.

## Consequences

- Correct as long as the invariant holds, and the invariant is written down
  rather than assumed.
- If it breaks — a producer retry reordering a write, or a second venue feeding
  the same instrument — the offending trade is late by definition and appears in
  `market.ticks_late`. The failure is visible, not silent.
- `high`, `low`, `volume`, `vwap` and `trades` do not depend on ordering at all,
  and `stream/tests/bar_reconciliation.py` checks every one of them against an
  independent replay.
- Revisit if a second venue is added for the same instrument, which would break
  assumption 2.

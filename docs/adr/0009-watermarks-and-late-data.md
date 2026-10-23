# 0009 — Watermarks, and what happens to trades that miss them

**Status:** accepted (Phase 2)

## Context

Phase 1 produced "bars" by aggregating stored ticks at query time
(`market.bars_1m_live`). That has a property worth naming: a bar was never
final. Re-run the query a minute later and a bar for a window ten minutes old
could still change, because more ticks for that window may have landed. Nothing
downstream could know whether it was looking at a settled number.

## Decision

Bars are closed by a **watermark**, not by wall clock and not by query time.
The source declares:

```sql
WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
```

so Flink waits 5 seconds past a window's end before emitting its bar. Trades
arriving after that are **late**: they are routed to `ticks.late` via
`CURRENT_WATERMARK()` and recorded in `market.ticks_late` with their lateness.

Two things follow, both deliberate:

1. A late trade does **not** retroactively mutate a bar that consumers have
   already seen. The bar is wrong by exactly that trade, and the error is
   recorded rather than hidden.
2. The 5-second delay is a tunable trade-off between bar latency and bar
   completeness. `market.ticks_late` is the evidence for whether it is set
   correctly — if lateness is common, raise it.

`stream/tests/late_data_check.py` proves the behaviour: it injects a trade
behind the watermark and asserts it lands in `ticks_late`, that the closed bar's
trade count is unchanged, and that the sentinel price never reaches a bar.

## Consequences

- Bars are final once emitted, so downstream can act on them.
- Completeness is measurable instead of assumed.
- `market.bars_1m_live` is kept, now as the independent replay that
  `stream/tests/bar_reconciliation.py` checks Flink's output against.

## Note: idle partitions

A watermark is the **minimum** across source subtasks. `ticks.raw` has three
partitions and three instruments, which hash onto only two of them, leaving one
permanently empty — and an empty partition never advances its watermark. The
first version of this job sat in state RUNNING, perfectly healthy, emitting
nothing at all. `table.exec.source.idle-timeout` marks quiet partitions idle so
they stop holding the minimum back. This is the most common reason a correct
Flink job produces no output.

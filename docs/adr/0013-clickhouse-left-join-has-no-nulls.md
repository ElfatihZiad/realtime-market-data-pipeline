# 0013 — `was_late` uses a tuple IN, not a LEFT JOIN

**Status:** accepted (Phase 3)

## Context

`stg_ticks` flags trades that missed their window. The natural expression is a
left join against `market.ticks_late` and a null check on the joined column:

```sql
left join late as l on t.instrument_id = l.instrument_id and t.sequence = l.sequence
...
l.sequence is not null as was_late
```

That is wrong in ClickHouse. Unless `join_use_nulls` is set, an unmatched left
join row is filled with the **column type's default**, not NULL — `''` for
String. So `l.sequence is not null` is true for every row.

The first build of `fct_pipeline_health` therefore reported a late rate of
exactly `1.0` on every single day. The number was so obviously wrong that it
was caught immediately; a subtler column would have shipped.

## Decision

Express membership as a tuple `IN` against the subquery instead:

```sql
(t.instrument_id, t.sequence) in (select instrument_id, sequence from ticks_late)
```

## Consequences

- Correct regardless of the `join_use_nulls` setting, and it reads as what it
  means: membership, not a join.
- The corrected figure is `0.000234` for 2026-10-22 — the five trades
  deliberately injected by `stream/tests/late_data_check.py` — and zero
  elsewhere, which is the expected shape.
- General rule for this repo: do not reason about NULLs from a ClickHouse outer
  join. Use `IN`, `ANTI JOIN` or `SEMI JOIN`, which say what they mean.

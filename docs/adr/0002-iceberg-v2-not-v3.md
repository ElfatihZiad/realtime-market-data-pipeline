# 0002 — Iceberg spec v2, not v3

**Status:** accepted (applies from Phase 3)

## Context

Iceberg v3 reached GA on the major commercial platforms during the first half of
2026 and adds genuinely useful things: deletion vectors, variant columns, row
lineage. Engine support outside those platforms is still uneven — an engine that
can open a v3 table may still reject specific v3 features.

## Decision

Write v2 tables. Revisit when the engines this project actually uses
(ClickHouse, DuckDB, Flink) all support v3 end to end.

## Consequences

- Any engine can read the lake; no feature-matrix archaeology to run a query.
- No deletion vectors, so row-level deletes stay merge-on-read.
- The newest spec is not demonstrated. Choosing the format a reader can actually
  open is the better engineering story.

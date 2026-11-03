# 0003 — Flink SQL, not the PyFlink DataStream API

**Status:** accepted (applies from Phase 2)

## Context

The stream processing layer needs event-time windows, watermarks and late-data
handling. Flink offers the DataStream API (Java/Scala/Python) and Flink SQL.

PyFlink's DataStream API is the obvious reach for a Python codebase, but its
developer experience is poor — thin docs, awkward type hints, UDF serialisation
surprises — and the result is harder for anyone else to read.

## Decision

Express the streaming logic as Flink SQL files under `stream/sql/`, versioned
like any other source. Python only orchestrates submission.

## Consequences

- Windowing logic is readable by anyone who knows SQL, which includes every
  reviewer of this repo.
- Testable with bounded sources and golden files.
- Complex custom operators would need a Java job; none are planned.

## Rejected alternatives

Arroyo and RisingWave are both nicer to operate and SQL-native. Flink wins on
one axis that matters for a portfolio: it is what employers actually run.

# 0010 — Flink 2.2.1, not 2.3

**Status:** accepted (Phase 2)

## Context

Flink 2.3.0 is the current release. The SQL connectors this project needs are
versioned separately and lag it: the newest `flink-sql-connector-kafka` is
`5.0.0-2.2` and the newest `flink-sql-avro-confluent-registry` is `2.2.1`, both
built against Flink 2.2.

## Decision

Run Flink 2.2.1. Revisit when 2.3 builds of both connectors exist.

## Consequences

- Connector and runtime versions are consistent, which is the property that
  actually matters.
- `DESIGN.md` says 2.3 in its original plan; this is the correction, and the
  reason it is written down rather than quietly changed.
- Pinning in `infra/flink/Dockerfile` is explicit, so the next upgrade is a
  two-line diff with a known blast radius.

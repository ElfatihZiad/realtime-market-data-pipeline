# 0015 — Airflow runs `standalone` locally, and that is not production

**Status:** accepted (Phase 3)

## Context

Airflow 3 is four processes: api-server, scheduler, dag-processor and
triggerer, normally backed by Postgres. Running all of that in a local compose
stack that already has Kafka, Flink, ClickHouse, a schema registry, an Iceberg
catalog and an object store is a lot of containers for four small DAGs.

## Decision

One container running `airflow standalone` against SQLite, on port 8082.
The batch packages and dbt are installed **into** the image rather than shelled
out to.

## Consequences

- One container, no Postgres, starts in about ninety seconds.
- Installing the code into the image means a failing task produces a Python
  traceback in the task log, not an opaque non-zero exit code.
- SQLite serialises the scheduler; it is fine for four daily DAGs and would not
  survive real concurrency. This topology is explicitly dev-only, and the ADR
  exists so nobody mistakes it for a deployment pattern.
- `mdp_core` locates the Avro schemas by walking up from its own file, which
  breaks once installed into site-packages — hence `MDP_CONTRACTS_DIR` in the
  image.

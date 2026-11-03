# 0004 — Airflow orchestrates batch only, never the stream

**Status:** accepted

## Context

The old repo had an Airflow DAG whose tasks were shell scripts that started
Kafka consumers (`consumer_realtime.sh`, `consumer_news.sh`). A streaming
consumer is a process that runs forever; an Airflow task is a unit of work that
is expected to finish. Modelling one as the other means the task either blocks a
worker slot indefinitely or gets killed by a timeout.

(The DAG also invoked `./aftertrading.sh`, a file that does not exist in the
repo — so it had never run successfully.)

## Decision

Stream processors are long-running services, started by Compose locally and by
the platform in cloud. Airflow 3 schedules batch work only: daily fundamentals,
macro refresh, dbt builds, Iceberg maintenance, backfills.

## Consequences

- Clean separation: if it has an end, it is a DAG; if it runs forever, it is a service.
- Airflow 3's asset-aware scheduling expresses "the dbt marts depend on
  yesterday's partition landing" properly.
- A migration story from Airflow 1.10 to 3.x, which is worth having.

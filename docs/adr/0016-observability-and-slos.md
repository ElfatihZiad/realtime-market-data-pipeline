# 0016 — Metrics, traces and SLOs that actually evaluate

**Status:** accepted (Phase 4)

## Context

"We have monitoring" usually means a Grafana instance nobody opens. The
questions worth answering when a streaming pipeline misbehaves are narrow:
how far behind are we, and how long is a trade taking to get from the venue to
a query.

## Decision

- **Metrics**: Prometheus scrapes the ingest service, the API, Kafka (consumer
  lag via kafka-exporter) and Flink (its bundled Prometheus reporter, moved
  from `opt/` into `lib/`).
- **Traces**: OTLP to Jaeger, opt-in via a single setting. Unset, the services
  run exactly as before and no collector is required to use the project.
- **SLOs as rules, not prose**: five alerting rules in `infra/prometheus/rules.yml`
  covering latency, freshness, availability, correctness and reconnect storms.
  A rule fires, which means it can be wrong, which means it gets fixed.
- **One dashboard**, provisioned from source so it is reviewable in a diff.

## Consequences

- API metrics are labelled by **route**, not raw path. Labelling by path would
  create a time series per instrument id — the standard way to take down a
  Prometheus.
- One span per trade would be millions of spans an hour and say nothing new,
  so the span covers the produce call, which is the hop that can block.
- The tracing endpoint is read through `Settings`, not `os.environ`. Reading
  the raw environment meant the services silently ran untraced whenever they
  were started outside `just`, which is how this was first missed.

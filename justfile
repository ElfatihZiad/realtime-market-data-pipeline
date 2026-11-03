set dotenv-load := true

default:
    @just --list

# Install all workspace deps
install:
    uv sync --all-packages

# Bring up the full local stack
up:
    docker compose up -d --build --wait
    @echo "ClickHouse       http://localhost:8123/play"
    @echo "Flink UI         http://localhost:8081"
    @echo "Schema Registry  http://localhost:18081/subjects"

down:
    docker compose down -v

# Run the crypto ingest service against the local stack
ingest:
    uv run --package ingest-crypto python -m ingest_crypto

# Run the API + dashboard
api:
    uv run --package api uvicorn api.main:app --reload --port 8000

# (Re)apply the ClickHouse schema. The init scripts in the image only run on an
# empty data volume, so this is how a schema change reaches a running stack.
schema:
    docker compose exec -T clickhouse clickhouse-client --multiquery \
        < infra/clickhouse/init/01-schema.sql
    @echo "schema applied"

# Drop and recreate the Kafka engine tables and their views. Needed when their
# SETTINGS change, which CREATE ... IF NOT EXISTS will not do.
schema-reset:
    #!/usr/bin/env bash
    set -euo pipefail
    for t in ticks_mv ticks_errors_mv bars_mv ticks_late_mv signals_mv \
             ticks_queue bars_queue ticks_late_queue signals_queue; do
        docker compose exec -T clickhouse clickhouse-client \
            --query "DROP TABLE IF EXISTS market.$t" 
    done
    just schema

# Submit a Flink SQL script (detached). e.g. `just flink-sql 10_bars.sql`
flink-sql script:
    docker compose exec -T flink-jobmanager \
        ./bin/sql-client.sh -f /opt/sql/{{script}}

# Submit every streaming job
stream: (flink-sql "10_bars.sql") (flink-sql "20_signals.sql")

# What is running on the cluster
flink-jobs:
    docker compose exec -T flink-jobmanager ./bin/flink list

# Schemas currently registered
schemas:
    @curl -s http://localhost:18081/subjects | python3 -m json.tool

# Prove the late-data path: inject a trade behind the watermark and check it
# is recorded rather than dropped, and that no closed bar changed.
check-late:
    uv run --package ingest-crypto python stream/tests/late_data_check.py

# Reconcile Flink's bars against the same windows recomputed from stored ticks.
check-bars:
    uv run --package ingest-crypto python stream/tests/bar_reconciliation.py

# Both streaming correctness checks
verify: check-late check-bars

lint:
    uv run ruff check .
    uv run ruff format --check .
    uv run mypy libs services

fmt:
    uv run ruff format .
    uv run ruff check --fix .

test:
    uv run pytest -q

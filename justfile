set dotenv-load := true

default:
    @just --list

# Install all workspace deps
install:
    uv sync --all-packages

# Generate Python code from the proto contracts
codegen:
    mkdir -p libs/mdp_core/src/mdp_core/gen
    uv run python -m grpc_tools.protoc \
        -I contracts \
        --python_out=libs/mdp_core/src/mdp_core/gen \
        --pyi_out=libs/mdp_core/src/mdp_core/gen \
        contracts/market/v1/tick.proto
    touch libs/mdp_core/src/mdp_core/gen/__init__.py
    find libs/mdp_core/src/mdp_core/gen -type d -exec touch {}/__init__.py \;
    # Stage the contracts where ClickHouse decodes the Kafka topic from them.
    rm -rf infra/clickhouse/format_schemas
    mkdir -p infra/clickhouse/format_schemas
    cp -R contracts/. infra/clickhouse/format_schemas/

# Bring up the full local stack
up: codegen
    docker compose up -d --wait
    @echo "ClickHouse  http://localhost:8123/play"
    @echo "Kafka UI    http://localhost:8080"

down:
    docker compose down -v

# Run the crypto ingest service against the local stack
ingest:
    uv run --package ingest-crypto python -m ingest_crypto

# Run the API + dashboard
api:
    uv run --package api uvicorn api.main:app --reload --port 8000

lint:
    uv run ruff check .
    uv run ruff format --check .
    uv run mypy libs services

fmt:
    uv run ruff format .
    uv run ruff check --fix .

test:
    uv run pytest -q

"""Integration test: the ClickHouse schema and its SQL, against a real server.

Everything else in this repo's test suite is pure Python. The warehouse layer
is SQL, and SQL is only correct against the engine that runs it — ClickHouse's
`argMin`/`argMax` ordering, its aggregate-alias resolution and its outer-join
NULL semantics have each already produced a real bug here (ADR 0013).

Spins a throwaway ClickHouse with testcontainers, applies the real schema file,
inserts hand-computed ticks, and asserts the bar view produces the OHLCV a
human would.

Skipped unless Docker is available:

    uv run pytest tests/ -m integration
"""

from __future__ import annotations

import datetime as dt
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[1]
TABLES_SQL = REPO_ROOT / "infra" / "clickhouse" / "init" / "01-tables.sql"
CLICKHOUSE_IMAGE = "clickhouse/clickhouse-server:26.9"


def _docker_available() -> bool:
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


pytest.importorskip("testcontainers", reason="testcontainers is not installed")
if not _docker_available():
    pytest.skip("docker is not available", allow_module_level=True)


@pytest.fixture(scope="module")
def client() -> Iterator[object]:
    import time

    import clickhouse_connect
    from testcontainers.core.container import DockerContainer

    container = (
        DockerContainer(CLICKHOUSE_IMAGE)
        .with_exposed_ports(8123)
        # Without these the image disables network access for `default` and
        # every request over the port is a 401.
        .with_env("CLICKHOUSE_DB", "market")
        .with_env("CLICKHOUSE_USER", "default")
        .with_env("CLICKHOUSE_PASSWORD", "test")
    )
    with container:
        # Poll the endpoint rather than wait on a log line: the startup banner
        # differs between ClickHouse builds, and a readiness check that greps
        # logs fails for reasons that have nothing to do with readiness.
        host = container.get_container_host_ip()
        port = int(container.get_exposed_port(8123))
        conn = None
        deadline = time.time() + 180
        while time.time() < deadline:
            try:
                conn = clickhouse_connect.get_client(
                    host=host, port=port, username="default", password="test"
                )
                conn.command("SELECT 1")
                break
            except Exception:  # noqa: BLE001 - any failure here means "not up yet"
                time.sleep(2)
        assert conn is not None, "ClickHouse did not become reachable within 180s"
        # The real schema file, not a copy: a test against a hand-written
        # schema would pass while the shipped one is broken.
        import sys

        sys.path.insert(0, str(REPO_ROOT / "infra" / "clickhouse"))
        from apply_schema import statements

        for stmt in statements(TABLES_SQL.read_text()):
            conn.command(stmt)
        yield conn


def _utc(second: int, micro: int = 0) -> dt.datetime:
    return dt.datetime(2026, 1, 1, 10, 0, second, micro, tzinfo=dt.UTC)


@pytest.fixture(scope="module")
def seeded(client):  # type: ignore[no-untyped-def]
    """Five trades in one minute, with a deliberate ordering trap.

    They are inserted OUT of event-time order, and the highest price is neither
    the first nor the last row inserted — so an `open`/`close` taken by arrival
    order rather than event time gets a different, wrong answer.
    """
    rows = [
        # (event_time, price, size)  — inserted deliberately out of order
        (_utc(30), 102.0, 2.0),
        (_utc(0), 100.0, 1.0),  # earliest  → open must be 100.0
        (_utc(59), 101.0, 4.0),  # latest    → close must be 101.0
        (_utc(10), 105.0, 1.0),  # highest
        (_utc(20), 99.0, 2.0),  # lowest
    ]
    client.insert(
        "market.ticks",
        [
            ("TEST-USD", "test", t, t, price, size, "buy", f"seq-{i}", 1000)
            for i, (t, price, size) in enumerate(rows)
        ],
        column_names=[
            "instrument_id",
            "venue",
            "event_time",
            "ingest_time",
            "price",
            "size",
            "side",
            "sequence",
            "latency_us",
        ],
    )
    return client


def test_ohlc_uses_event_time_not_insertion_order(seeded) -> None:  # type: ignore[no-untyped-def]
    row = seeded.query(
        """
        SELECT open, high, low, close, trades
        FROM market.bars_1m_live
        WHERE instrument_id = 'TEST-USD'
        """
    ).result_rows[0]
    open_, high, low, close, trades = row
    assert open_ == 100.0, "open must be the earliest trade by event time"
    assert close == 101.0, "close must be the latest trade by event time"
    assert high == 105.0
    assert low == 99.0
    assert trades == 5


def test_vwap_is_volume_weighted_and_inside_the_range(seeded) -> None:  # type: ignore[no-untyped-def]
    vwap = seeded.query(
        "SELECT vwap FROM market.bars_1m_live WHERE instrument_id = 'TEST-USD'"
    ).result_rows[0][0]
    # (102*2 + 100*1 + 101*4 + 105*1 + 99*2) / 10 = 101.1
    assert vwap == pytest.approx(101.1)
    assert 99.0 <= vwap <= 105.0, "a volume-weighted mean cannot leave the bar's range"


def test_every_table_the_dbt_models_read_exists(seeded) -> None:  # type: ignore[no-untyped-def]
    """The schema split means CI creates only this file; dbt reads from it."""
    present = {
        r[0]
        for r in seeded.query(
            "SELECT name FROM system.tables WHERE database = 'market'"
        ).result_rows
    }
    for required in ("ticks", "bars", "signals", "ticks_late", "ticks_errors", "news", "sentiment"):
        assert required in present, f"dbt sources reference market.{required}"

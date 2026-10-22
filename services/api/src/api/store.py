"""ClickHouse access.

Every query is parameterised. The old version built CQL with str.format() and
then worked around the resulting quoting problems by replacing ' with '@@' on
write and reversing it on read.
"""

from __future__ import annotations

from typing import Any

import clickhouse_connect
from clickhouse_connect.driver.client import Client
from mdp_core import get_settings


def get_client() -> Client:
    s = get_settings()
    return clickhouse_connect.get_client(
        host=s.clickhouse_host,
        port=s.clickhouse_port,
        username=s.clickhouse_user,
        password=s.clickhouse_password,
        database=s.clickhouse_db,
    )


def instruments(client: Client) -> list[str]:
    rows = client.query(
        "SELECT DISTINCT instrument_id FROM market.ticks ORDER BY instrument_id"
    ).result_rows
    return [r[0] for r in rows]


def bars_1m(client: Client, instrument_id: str, minutes: int) -> list[dict[str, Any]]:
    """Bars as Flink closed them on event time.

    Phase 1 served market.bars_1m_live, which re-aggregated stored ticks on
    every request, so a bar could still change long after its minute ended.
    These are emitted once, when the watermark passed the window.
    """
    result = client.query(
        """
        SELECT window_start, open, high, low, close, volume, vwap, trades
        FROM market.bars
        WHERE instrument_id = {instrument_id:String}
          AND bar_interval = '1m'
          AND window_start >= now() - toIntervalMinute({minutes:UInt32})
        ORDER BY window_start
        """,
        parameters={"instrument_id": instrument_id, "minutes": minutes},
    )
    return [
        {
            "bucket": row[0].isoformat(),
            "open": row[1],
            "high": row[2],
            "low": row[3],
            "close": row[4],
            "volume": row[5],
            "vwap": row[6],
            "trades": row[7],
        }
        for row in result.result_rows
    ]


def signals(client: Client, instrument_id: str, minutes: int) -> list[dict[str, Any]]:
    result = client.query(
        """
        SELECT bar_end, close, log_return, realized_vol, zscore, is_spike
        FROM market.signals
        WHERE instrument_id = {instrument_id:String}
          AND bar_end >= now() - toIntervalMinute({minutes:UInt32})
        ORDER BY bar_end
        """,
        parameters={"instrument_id": instrument_id, "minutes": minutes},
    )
    return [
        {
            "bar_end": r[0].isoformat(),
            "close": r[1],
            "log_return": r[2],
            "realized_vol": r[3],
            "zscore": r[4],
            "is_spike": bool(r[5]),
        }
        for r in result.result_rows
    ]


def recent_ticks(
    client: Client, instrument_id: str, since_iso: str | None, limit: int
) -> list[dict[str, Any]]:
    if since_iso:
        result = client.query(
            """
            SELECT event_time, price, size, side, latency_us
            FROM market.ticks
            WHERE instrument_id = {instrument_id:String}
              AND event_time > parseDateTime64BestEffort({since:String}, 6, 'UTC')
            ORDER BY event_time
            LIMIT {limit:UInt32}
            """,
            parameters={"instrument_id": instrument_id, "since": since_iso, "limit": limit},
        )
    else:
        result = client.query(
            """
            SELECT event_time, price, size, side, latency_us
            FROM market.ticks
            WHERE instrument_id = {instrument_id:String}
            ORDER BY event_time DESC
            LIMIT {limit:UInt32}
            """,
            parameters={"instrument_id": instrument_id, "limit": limit},
        )
    rows = [
        {
            "event_time": row[0].isoformat(),
            "price": row[1],
            "size": row[2],
            "side": row[3],
            "latency_us": row[4],
        }
        for row in result.result_rows
    ]
    return rows if since_iso else list(reversed(rows))


def pipeline_stats(client: Client) -> dict[str, Any]:
    """What the pipeline knows about itself."""
    row = client.query(
        """
        SELECT
            count()                                   AS ticks,
            uniqExact(instrument_id)                  AS instruments,
            quantile(0.5)(latency_us) / 1000          AS p50_latency_ms,
            quantile(0.99)(latency_us) / 1000         AS p99_latency_ms,
            max(event_time)                           AS latest_event,
            countIf(event_time >= now() - toIntervalMinute(1)) AS ticks_last_minute
        FROM market.ticks
        """
    ).result_rows
    if not row or row[0][0] == 0:
        return {"ticks": 0, "instruments": 0, "dlq": 0}
    r = row[0]
    dlq = client.query("SELECT count() FROM market.ticks_errors").result_rows[0][0]
    bars = client.query("SELECT count() FROM market.bars WHERE bar_interval = '1m'").result_rows[0][
        0
    ]
    late = client.query(
        "SELECT count(), coalesce(max(lateness_ms), 0) FROM market.ticks_late"
    ).result_rows[0]
    spikes = client.query("SELECT countIf(is_spike) FROM market.signals").result_rows[0][0]
    return {
        "ticks": r[0],
        "instruments": r[1],
        "p50_latency_ms": round(float(r[2]), 2),
        "p99_latency_ms": round(float(r[3]), 2),
        "latest_event": r[4].isoformat() if r[4] else None,
        "ticks_last_minute": r[5],
        "dlq": dlq,
        "bars": bars,
        "late_trades": late[0],
        "max_lateness_ms": late[1],
        "spikes": spikes,
    }

"""Reconcile Flink's event-time bars against an independent computation.

Flink computes bars in-flight from the Kafka stream, driven by watermarks.
ClickHouse can compute the same bars after the fact by aggregating the stored
ticks (market.bars_1m_live, the Phase 1 approach). Two independent paths over
the same trades: they must agree.

They agree only once late arrivals are accounted for. A trade that missed its
window is in market.ticks and therefore in the read-time aggregate, but was
correctly excluded from the Flink bar. Subtracting market.ticks_late is what
makes the two comparable — and the size of that correction is exactly the cost
of the watermark delay.

Run against a live stack after `just stream` has been producing for a few
minutes:

    just check-bars
"""

from __future__ import annotations

import sys

import clickhouse_connect
from mdp_core import get_settings

# Compare only windows that are closed and settled.
SKIP_RECENT_MINUTES = 2
PRICE_TOLERANCE = 1e-6
VOLUME_TOLERANCE = 1e-6


def main() -> int:
    s = get_settings()
    ch = clickhouse_connect.get_client(
        host=s.clickhouse_host,
        port=s.clickhouse_port,
        username=s.clickhouse_user,
        password=s.clickhouse_password,
    )

    rows = ch.query(
        """
        WITH
            -- what Flink emitted
            flink AS (
                SELECT instrument_id, window_start, open, high, low, close, volume, vwap, trades
                FROM market.bars
                WHERE bar_interval = '1m'
                  AND window_start < now() - toIntervalMinute({skip:UInt8})
                  -- Skip the job's FIRST window. The source starts at
                  -- latest-offset, so Flink joins that window part-way through
                  -- and its bar is incomplete by construction, while the
                  -- replay sees every tick ClickHouse stored. Not a defect,
                  -- but not comparable either.
                  AND window_start > (SELECT min(window_start) FROM market.bars
                                      WHERE bar_interval = '1m')
            ),
            -- the same windows recomputed from stored ticks, minus the trades
            -- Flink was right to exclude
            replay AS (
                SELECT
                    t.instrument_id                            AS instrument_id,
                    toStartOfMinute(t.event_time)              AS window_start,
                    max(t.price)                               AS high,
                    min(t.price)                               AS low,
                    sum(t.size)                                AS volume,
                    sum(t.price * t.size) / nullIf(sum(t.size), 0) AS vwap,
                    count()                                    AS trades
                FROM market.ticks AS t
                LEFT ANTI JOIN market.ticks_late AS l
                  ON t.instrument_id = l.instrument_id AND t.sequence = l.sequence
                GROUP BY instrument_id, window_start
            )
        SELECT
            f.instrument_id,
            f.window_start,
            f.trades, r.trades,
            f.high,   r.high,
            f.low,    r.low,
            f.volume, r.volume,
            f.vwap,   r.vwap
        FROM flink AS f
        INNER JOIN replay AS r
          ON f.instrument_id = r.instrument_id AND f.window_start = r.window_start
        ORDER BY f.window_start, f.instrument_id
        """,
        parameters={"skip": SKIP_RECENT_MINUTES},
    ).result_rows

    if not rows:
        print("FAIL: no settled windows to compare yet — let the stream run a few minutes")
        return 1

    mismatches: list[str] = []
    for (
        instrument,
        window,
        f_trades,
        r_trades,
        f_high,
        r_high,
        f_low,
        r_low,
        f_vol,
        r_vol,
        f_vwap,
        r_vwap,
    ) in rows:
        where = f"{instrument} {window}"
        if f_trades != r_trades:
            mismatches.append(f"{where}: trades flink={f_trades} replay={r_trades}")
        if abs(f_high - r_high) > PRICE_TOLERANCE:
            mismatches.append(f"{where}: high flink={f_high} replay={r_high}")
        if abs(f_low - r_low) > PRICE_TOLERANCE:
            mismatches.append(f"{where}: low flink={f_low} replay={r_low}")
        if abs(f_vol - r_vol) > VOLUME_TOLERANCE:
            mismatches.append(f"{where}: volume flink={f_vol} replay={r_vol}")
        if abs(f_vwap - r_vwap) > PRICE_TOLERANCE * max(1.0, abs(r_vwap)):
            mismatches.append(f"{where}: vwap flink={f_vwap} replay={r_vwap}")

    print(f"compared {len(rows)} settled 1m bars across {len({r[0] for r in rows})} instruments")

    late = ch.query("SELECT count(), max(lateness_ms) FROM market.ticks_late").result_rows[0]
    print(f"late arrivals excluded: {late[0]} (max lateness {late[1]}ms)")

    if mismatches:
        print(f"\nFAIL: {len(mismatches)} mismatch(es)")
        for m in mismatches[:20]:
            print("  " + m)
        return 1

    print("\nRECONCILIATION: PASSED — Flink's event-time bars match the replay exactly")
    return 0


if __name__ == "__main__":
    sys.exit(main())

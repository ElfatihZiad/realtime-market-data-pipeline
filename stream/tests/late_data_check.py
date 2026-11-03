"""Prove that a late trade is accounted for rather than silently dropped.

Injects a trade whose event time is deliberately far behind the watermark, then
checks that it (a) does NOT mutate an already-closed bar and (b) DOES appear in
market.ticks_late with its lateness recorded.

Note that the injected trade is synthetic: it is expected to appear in
market.ticks (ClickHouse stores everything on ticks.raw) and in any WIDER
window that was still open when it arrived. What must not happen is it changing
a 1m bar that had already been closed and published.

This is the Phase 2 exit criterion. Run against a live stack:

    just up && just stream && just ingest   # in another shell
    just check-late
"""

from __future__ import annotations

import sys
import time

import clickhouse_connect
from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import MessageField, SerializationContext
from mdp_core import Tick, get_settings, load_schema

INSTRUMENT = "BTC-USD"
# Unique per run: a fixed sentinel would match a row left by an earlier run and
# the check would pass without this run's trade ever arriving.
SENTINEL = f"late-data-check-{int(time.time() * 1000)}"


def main() -> int:
    settings = get_settings()
    ch = clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
    )

    now_us = int(time.time() * 1_000_000)

    # Aim at a window that ALREADY has a closed bar, otherwise "the bar did not
    # change" proves nothing. Take the most recent one Flink has emitted.
    target = ch.query(
        """
        SELECT toUnixTimestamp64Milli(window_start), trades
        FROM market.bars
        WHERE instrument_id = {i:String} AND bar_interval = '1m'
        ORDER BY window_start DESC
        LIMIT 1
        """,
        parameters={"i": INSTRUMENT},
    ).result_rows
    if not target:
        print("FAIL: no closed bars yet — is `just stream` running and ingest feeding it?")
        return 1

    window_start_ms = int(target[0][0])
    # Land the trade 30s into that window, comfortably inside it.
    event_time_us = (window_start_ms + 30_000) * 1_000
    late_by_s = (now_us - event_time_us) // 1_000_000
    print(f"targeting closed window {window_start_ms} (trades={target[0][1]}), {late_by_s}s behind")

    before = ch.query(
        """
        SELECT count(), sum(trades)
        FROM market.bars
        WHERE instrument_id = {i:String} AND bar_interval = '1m'
          AND window_start = fromUnixTimestamp64Milli({w:Int64}, 'UTC')
        """,
        parameters={"i": INSTRUMENT, "w": window_start_ms},
    ).result_rows[0]
    print(f"target window {window_start_ms} before: bars={before[0]} trades={before[1]}")

    tick = Tick(
        instrument_id=INSTRUMENT,
        venue=SENTINEL,
        event_time_us=event_time_us,
        ingest_time_us=now_us,
        price=1.0,
        size=1.0,
        side="buy",
        sequence=SENTINEL,
    )

    serializer = AvroSerializer(
        SchemaRegistryClient({"url": settings.schema_registry_url}),
        load_schema("tick"),
        lambda t, _ctx: t,
    )
    producer = Producer({"bootstrap.servers": settings.kafka_bootstrap, "acks": "all"})
    producer.produce(
        topic=settings.ticks_topic,
        key=INSTRUMENT.encode(),
        value=serializer(
            tick.to_dict(), SerializationContext(settings.ticks_topic, MessageField.VALUE)
        ),
    )
    producer.flush(10)
    print(f"injected a trade {late_by_s}s behind the watermark, inside a CLOSED window")

    # Give Flink and the ClickHouse consumer time to react.
    deadline = time.time() + 60
    late_row = None
    while time.time() < deadline:
        rows = ch.query(
            """
            SELECT lateness_ms, price, event_time
            FROM market.ticks_late
            WHERE sequence = {s:String}
            """,
            parameters={"s": SENTINEL},
        ).result_rows
        if rows:
            late_row = rows[0]
            break
        time.sleep(2)

    after = ch.query(
        """
        SELECT count(), sum(trades)
        FROM market.bars
        WHERE instrument_id = {i:String} AND bar_interval = '1m'
          AND window_start = fromUnixTimestamp64Milli({w:Int64}, 'UTC')
        """,
        parameters={"i": INSTRUMENT, "w": window_start_ms},
    ).result_rows[0]

    ok = True

    if late_row is None:
        print("FAIL: the late trade never reached market.ticks_late")
        ok = False
    else:
        lateness_ms, price, event_time = late_row
        print(
            f"PASS: recorded in ticks_late — price={price} "
            f"lateness={lateness_ms}ms event_time={event_time}"
        )
        if lateness_ms < (late_by_s - 30) * 1000:
            print(f"FAIL: lateness {lateness_ms}ms is implausibly small")
            ok = False

    if before[0] == 0:
        print("FAIL: target window had no bar, so the mutation check is vacuous")
        ok = False
    elif after[1] != before[1]:
        print(f"FAIL: a closed bar mutated — trades {before[1]} -> {after[1]}")
        ok = False
    else:
        print(f"PASS: the closed bar did not change (bars={after[0]}, trades={after[1]})")

    # The sentinel price is 1.0, so a leak collapses the bar's low.
    #
    # Scoped to the 1m window we targeted, deliberately. "Behind the watermark"
    # is not the same as "too late for every window": a trade can be late
    # enough to miss its CLOSED 1m window while still falling inside a 5m
    # window that is open. Flink routes it to ticks.late (it is behind the
    # watermark) AND counts it in the open 5m bar — both correct. Asserting it
    # never reaches any bar would be asserting something untrue.
    leaked = ch.query(
        """
        SELECT count() FROM market.bars
        WHERE instrument_id = {i:String}
          AND bar_interval = '1m'
          AND window_start = fromUnixTimestamp64Milli({w:Int64}, 'UTC')
          AND low <= 1.0
        """,
        parameters={"i": INSTRUMENT, "w": window_start_ms},
    ).result_rows[0][0]
    if leaked:
        print("FAIL: the sentinel price leaked into the closed 1m bar")
        ok = False
    else:
        print("PASS: the sentinel price did not reach the closed 1m bar")

    print("\nLATE-DATA CHECK:", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

"""Unit tests for the Coinbase -> canonical Tick mapping.

This is the only pure logic in Phase 1, and it is where the subtle bugs live:
timestamp parsing, the maker/aggressor side flip, and rejecting junk instead of
quietly turning it into a zero-priced trade.
"""

from __future__ import annotations

import pytest
from ingest_crypto.coinbase import MalformedMessage, is_trade, subscribe_frame, to_tick

MATCH = {
    "type": "match",
    "trade_id": 762_112_233,
    "product_id": "BTC-USD",
    "price": "82480.91",
    "size": "0.00001273",
    "side": "sell",
    "time": "2026-10-22T06:41:35.273090Z",
}


def test_maps_core_fields() -> None:
    tick = to_tick(MATCH, ingest_time_us=1_000)
    assert tick.instrument_id == "BTC-USD"
    assert tick.venue == "coinbase"
    assert tick.price == pytest.approx(82480.91)
    assert tick.size == pytest.approx(0.00001273)
    assert tick.sequence == "762112233"
    assert tick.ingest_time_us == 1_000


def test_event_time_parsed_as_utc_microseconds() -> None:
    tick = to_tick(MATCH, ingest_time_us=0)
    # 2026-10-22T06:41:35.273090Z
    assert tick.event_time_us == 1_792_651_295_273_090


def test_side_is_flipped_to_the_aggressor() -> None:
    """Coinbase reports the maker's side; we store the taker's."""
    assert to_tick({**MATCH, "side": "sell"}, ingest_time_us=0).side == "buy"
    assert to_tick({**MATCH, "side": "buy"}, ingest_time_us=0).side == "sell"


def test_unknown_side_is_empty_not_guessed() -> None:
    assert to_tick({**MATCH, "side": "???"}, ingest_time_us=0).side == ""


@pytest.mark.parametrize(
    "mutation",
    [
        {"price": "not-a-number"},
        {"price": "0"},
        {"size": "-1"},
        {"time": "yesterday"},
    ],
)
def test_bad_values_are_rejected(mutation: dict[str, str]) -> None:
    with pytest.raises(MalformedMessage):
        to_tick({**MATCH, **mutation}, ingest_time_us=0)


@pytest.mark.parametrize("missing", ["product_id", "price", "size", "time"])
def test_missing_fields_are_rejected(missing: str) -> None:
    payload = {k: v for k, v in MATCH.items() if k != missing}
    with pytest.raises(MalformedMessage):
        to_tick(payload, ingest_time_us=0)


def test_only_trade_messages_are_ingested() -> None:
    assert is_trade(MATCH)
    assert is_trade({"type": "last_match"})
    assert not is_trade({"type": "heartbeat"})
    assert not is_trade({"type": "subscriptions"})


def test_subscribe_frame_requests_matches_for_each_symbol() -> None:
    import json

    frame = json.loads(subscribe_frame(["BTC-USD", "ETH-USD"]))
    assert frame["type"] == "subscribe"
    assert frame["product_ids"] == ["BTC-USD", "ETH-USD"]
    assert frame["channels"] == ["matches"]

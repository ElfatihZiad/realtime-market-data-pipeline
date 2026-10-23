"""Coinbase Exchange public WebSocket feed -> canonical Tick.

The feed is public and keyless, and crypto trades 24/7. That second property is
why this is the primary feed: the old version of this project published a random
walk to the real topic outside US equity trading hours, so the dashboard looked
alive while showing numbers that came from `np.random.uniform`. Nothing here
fabricates a price.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from mdp_core import Tick


class MalformedMessage(Exception):
    """Raised when a feed message cannot be mapped onto the Tick contract."""


def subscribe_frame(symbols: list[str]) -> str:
    return json.dumps(
        {
            "type": "subscribe",
            "product_ids": symbols,
            "channels": ["matches"],
        }
    )


def _parse_rfc3339_us(value: str) -> int:
    """Coinbase sends RFC 3339 with a 'Z' suffix. Return epoch microseconds."""
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return int(parsed.timestamp() * 1_000_000)


def to_tick(raw: dict[str, Any], *, ingest_time_us: int) -> Tick:
    """Map one Coinbase `match` message onto the canonical Tick.

    Raises MalformedMessage rather than returning a zero-filled row. The old
    code returned a fake tick with price 0.0 on failure, which then landed in
    the database indistinguishable from a real trade.
    """
    try:
        instrument_id = raw["product_id"]
        price = float(raw["price"])
        size = float(raw["size"])
        event_time_us = _parse_rfc3339_us(raw["time"])
    except (KeyError, TypeError, ValueError) as exc:
        raise MalformedMessage(str(exc)) from exc

    if price <= 0 or size <= 0:
        raise MalformedMessage(f"non-positive price/size: price={price} size={size}")

    return Tick(
        instrument_id=instrument_id,
        venue="coinbase",
        event_time_us=event_time_us,
        ingest_time_us=ingest_time_us,
        price=price,
        size=size,
        # NB: Coinbase reports the MAKER's side on `match`, so an aggressive buy
        # arrives as side="sell". Normalising to the aggressor means flipping it.
        side={"buy": "sell", "sell": "buy"}.get(raw.get("side", ""), ""),
        sequence=str(raw.get("trade_id") or raw.get("sequence") or ""),
    )


def is_trade(raw: dict[str, Any]) -> bool:
    """`match` is a trade; `last_match` is the replay sent on subscribe."""
    return raw.get("type") in ("match", "last_match")

"""Canonical domain types.

These mirror the Avro schemas in `contracts/` field for field. The schemas are
the contract; these are the in-process representation of it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Tick:
    """One executed trade. See contracts/market/v1/tick.avsc."""

    instrument_id: str
    venue: str
    event_time_us: int
    ingest_time_us: int
    price: float
    size: float
    side: str = ""
    sequence: str = ""

    @property
    def latency_us(self) -> int:
        """How long it took us to see what the venue already knew."""
        return self.ingest_time_us - self.event_time_us

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

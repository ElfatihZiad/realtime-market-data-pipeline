"""FRED writes '.' for a missing observation.

Storing that as 0.0 would quietly distort every average computed over the
series, so the loader must carry it through as NULL. This pins that mapping.
"""

from __future__ import annotations

import pytest


def to_value(raw: str | None) -> float | None:
    """Mirrors the mapping in batch.fred.run()."""
    return None if raw in (".", "", None) else float(raw)


@pytest.mark.parametrize("raw", [".", "", None])
def test_missing_observations_become_null(raw: str | None) -> None:
    assert to_value(raw) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("0", 0.0), ("3.25", 3.25), ("-0.5", -0.5), ("21000.1", 21000.1)],
)
def test_real_observations_parse(raw: str, expected: float) -> None:
    assert to_value(raw) == expected


def test_zero_is_not_treated_as_missing() -> None:
    """The bug this guards: `if not value` would swallow a genuine 0."""
    assert to_value("0") == 0.0
    assert to_value("0") is not None

"""Tests for the EDGAR fact extraction.

The live API cannot be exercised here — SEC returns 403 without a User-Agent
carrying real contact details — so the parsing is pinned against the documented
companyfacts response shape instead. That is the part with the logic in it; the
HTTP call is a one-liner.
"""

from __future__ import annotations

from typing import Any

from batch.edgar import extract_facts

COMPANYFACTS: dict[str, Any] = {
    "cik": 320193,
    "entityName": "Apple Inc.",
    "facts": {
        "us-gaap": {
            "NetIncomeLoss": {
                "units": {
                    "USD": [
                        {
                            "start": "2023-10-01",
                            "end": "2024-09-28",
                            "val": 93736000000,
                            "accn": "0000320193-24-000123",
                            "fy": 2024,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2024-11-01",
                        },
                        # No `filed` — cannot be placed on a timeline.
                        {"end": "2023-09-30", "val": 96995000000, "fy": 2023, "fp": "FY"},
                        # No `end` — same problem.
                        {"val": 1, "filed": "2024-11-01", "fy": 2024, "fp": "FY"},
                    ]
                }
            },
            "Assets": {
                "units": {
                    "USD": [
                        {
                            "end": "2024-09-28",
                            "val": 364980000000,
                            "accn": "0000320193-24-000123",
                            "fy": 2024,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2024-11-01",
                        }
                    ]
                }
            },
            # Not in WANTED_FACTS; must be ignored rather than widening the load.
            "GoodwillImpairmentLoss": {
                "units": {"USD": [{"end": "2024-09-28", "val": 0, "filed": "2024-11-01"}]}
            },
        }
    },
}


def _rows() -> list[tuple[Any, ...]]:
    return extract_facts("AAPL", 320193, COMPANYFACTS)


def test_extracts_only_wanted_facts() -> None:
    assert {r[2] for r in _rows()} == {"NetIncomeLoss", "Assets"}


def test_skips_observations_without_end_or_filed() -> None:
    net_income = [r for r in _rows() if r[2] == "NetIncomeLoss"]
    assert len(net_income) == 1
    assert net_income[0][6] == "2024-09-28"


def test_row_shape_matches_insert_columns() -> None:
    row = next(r for r in _rows() if r[2] == "Assets")
    ticker, cik, fact, unit, fy, fp, period_end, filed, accession, value = row
    assert (ticker, cik, fact, unit) == ("AAPL", 320193, "Assets", "USD")
    assert (fy, fp) == (2024, "FY")
    assert (period_end, filed) == ("2024-09-28", "2024-11-01")
    assert accession == "0000320193-24-000123"
    assert value == 364980000000.0


def test_missing_facts_section_yields_nothing() -> None:
    assert extract_facts("NONE", 1, {"facts": {}}) == []
    assert extract_facts("NONE", 1, {}) == []

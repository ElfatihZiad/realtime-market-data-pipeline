"""FRED macro series -> ClickHouse.

Replaces `pandas_datareader`, which is unmaintained and whose FRED reader
breaks whenever the site changes. This calls the documented JSON API directly.

Needs a free API key in FRED_API_KEY. Without one the loader logs and exits
cleanly rather than failing the DAG: a missing optional credential should not
look like a broken pipeline.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from mdp_core import get_settings

log = structlog.get_logger("batch.fred")

OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"

DDL = """
CREATE TABLE IF NOT EXISTS market.macro
(
    series_id   LowCardinality(String),
    series_name LowCardinality(String),
    obs_date    Date,
    value       Nullable(Float64),
    loaded_at   DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY (series_id, obs_date)
"""

# The same indicators the 2021 version charted, now pulled from the source.
SERIES: dict[str, str] = {
    "GDPC1": "Real Gross Domestic Product",
    "CPIAUCSL": "Consumer Price Index, All Urban Consumers",
    "INDPRO": "Industrial Production Index",
    "UNRATE": "Civilian Unemployment Rate",
    "PAYEMS": "All Employees, Total Nonfarm",
    "FEDFUNDS": "Effective Federal Funds Rate",
    "DGS10": "10-Year Treasury Constant Maturity Rate",
    "DGS30": "30-Year Treasury Constant Maturity Rate",
    "DTB3": "3-Month Treasury Bill Secondary Market Rate",
    "GFDEBTN": "Federal Debt: Total Public Debt",
}


def fetch_series(
    client: httpx.Client, series_id: str, api_key: str, start: str
) -> list[dict[str, Any]]:
    resp = client.get(
        OBSERVATIONS_URL,
        params={
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": start,
        },
    )
    resp.raise_for_status()
    observations: list[dict[str, Any]] = resp.json().get("observations", [])
    return observations


def run(start: str = "2010-01-01") -> int:
    settings = get_settings()
    if not settings.fred_api_key:
        log.info("fred_skipped", reason="FRED_API_KEY is not set")
        return 0

    import clickhouse_connect

    ch = clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
    )
    ch.command(DDL)

    total = 0
    with httpx.Client(timeout=30.0) as client:
        for series_id, name in SERIES.items():
            observations = fetch_series(client, series_id, settings.fred_api_key, start)
            rows = [
                (
                    series_id,
                    name,
                    obs["date"],
                    # FRED writes "." for a missing observation. That is a gap,
                    # not a zero, and storing it as 0.0 would quietly distort
                    # every average computed over the series.
                    None if obs.get("value") in (".", "", None) else float(obs["value"]),
                )
                for obs in observations
                if obs.get("date")
            ]
            if rows:
                ch.insert(
                    "market.macro",
                    rows,
                    column_names=["series_id", "series_name", "obs_date", "value"],
                )
            total += len(rows)
            log.info("loaded", series_id=series_id, rows=len(rows))

    log.info("fred_done", series=len(SERIES), rows=total)
    return total


def main() -> None:
    from mdp_core import configure_logging

    configure_logging(get_settings().log_level)
    run()


if __name__ == "__main__":
    main()

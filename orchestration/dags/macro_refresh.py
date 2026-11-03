"""FRED macro series.

Skips cleanly when FRED_API_KEY is unset rather than failing: a missing
optional credential should not look like a broken pipeline.
"""

from __future__ import annotations

import datetime as dt

from airflow.sdk import dag, task

DEFAULT_ARGS = {"retries": 2, "retry_delay": dt.timedelta(minutes=10)}


@dag(
    dag_id="macro_refresh",
    description="Load FRED macro series into market.macro",
    schedule="30 6 * * *",
    start_date=dt.datetime(2026, 11, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["batch", "macro"],
)
def macro_refresh() -> None:
    @task
    def load_fred() -> int:
        from batch.fred import run

        return run()

    load_fred()


macro_refresh()

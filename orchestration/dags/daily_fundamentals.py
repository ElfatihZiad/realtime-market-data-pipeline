"""SEC EDGAR company facts, once a day after filings settle.

Batch, with a beginning and an end — which is why it is a DAG. The streaming
jobs are not; see docs/adr/0004-airflow-for-batch-only.md.
"""

from __future__ import annotations

import datetime as dt

from airflow.sdk import dag, task

DEFAULT_ARGS = {"retries": 2, "retry_delay": dt.timedelta(minutes=10)}


@dag(
    dag_id="daily_fundamentals",
    description="Load SEC EDGAR company facts into market.fundamentals",
    schedule="0 6 * * *",
    start_date=dt.datetime(2026, 11, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["batch", "fundamentals"],
)
def daily_fundamentals() -> None:
    @task
    def load_edgar() -> int:
        """Returns the row count so the task log says what it actually did."""
        from batch.edgar import run

        return run()

    load_edgar()


daily_fundamentals()

"""Rebuild the dbt marts and run their tests.

`dbt build` interleaves run and test per model, so a model whose tests fail
does not become a dependency of anything downstream. That is the whole reason
to use `build` rather than `run` followed by `test`.
"""

from __future__ import annotations

import datetime as dt

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag

DEFAULT_ARGS = {"retries": 1, "retry_delay": dt.timedelta(minutes=5)}


@dag(
    dag_id="dbt_build",
    description="Build and test the ClickHouse marts",
    schedule="0 7 * * *",
    start_date=dt.datetime(2026, 11, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["batch", "dbt"],
)
def dbt_build() -> None:
    BashOperator(
        task_id="dbt_build",
        bash_command="cd /opt/mdp/warehouse && dbt build --no-use-colors",
    )


dbt_build()

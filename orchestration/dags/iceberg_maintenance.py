"""Iceberg housekeeping.

A streaming sink that commits every checkpoint produces a great many small
files and a long snapshot history. Left alone, read performance degrades and
metadata grows without bound. This is the chore that every "we put it in a
lakehouse" demo omits, and the reason those demos get slow.
"""

from __future__ import annotations

import datetime as dt
import os

from airflow.sdk import dag, task

DEFAULT_ARGS = {"retries": 1, "retry_delay": dt.timedelta(minutes=5)}
RETAIN_SNAPSHOTS_DAYS = 7


@dag(
    dag_id="iceberg_maintenance",
    description="Expire old Iceberg snapshots and report table file counts",
    schedule="0 5 * * *",
    start_date=dt.datetime(2026, 11, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["batch", "iceberg"],
)
def iceberg_maintenance() -> None:
    @task
    def expire_snapshots() -> dict[str, int]:
        from pyiceberg.catalog.rest import RestCatalog

        catalog = RestCatalog(
            "mdp",
            uri=os.environ["ICEBERG_REST_URI"],
            warehouse="s3://warehouse/",
            **{
                "s3.endpoint": os.environ["S3_ENDPOINT"],
                "s3.access-key-id": os.environ["AWS_ACCESS_KEY_ID"],
                "s3.secret-access-key": os.environ["AWS_SECRET_ACCESS_KEY"],
                "s3.path-style-access": "true",
            },
        )

        cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=RETAIN_SNAPSHOTS_DAYS)
        report: dict[str, int] = {}
        for namespace, name in catalog.list_tables("market"):
            table = catalog.load_table((namespace, name))
            before = len(table.metadata.snapshots)
            try:
                table.expire_snapshots().expire_snapshots_older_than(cutoff).commit()
            except AttributeError:
                # pyiceberg's expiry API is young; if this build does not have
                # it, say so plainly rather than reporting a no-op as success.
                raise RuntimeError(
                    "This pyiceberg build has no expire_snapshots() API. "
                    "Pin a newer pyiceberg, or run the equivalent Flink "
                    "procedure, before relying on this task."
                ) from None
            after = len(catalog.load_table((namespace, name)).metadata.snapshots)
            report[f"{namespace}.{name}"] = before - after
        return report

    expire_snapshots()


iceberg_maintenance()

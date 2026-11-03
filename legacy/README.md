# Legacy (2021–2022)

The original version of this project: Kafka 2.3 + ZooKeeper, Cassandra 3.11,
Bokeh server dashboard, Airflow 1.10 DAG.

It is kept here during the rebuild as reference material — the Bokeh plotting
logic, the economy/BEA CSV extracts under `pipeline/visualization/`, and the
company fundamentals JSON are still useful inputs for the new dashboard.

**It does not run on current dependencies** (Bokeh 3 removed `Panel`, pandas 2
removed `DataFrame.append`, Airflow 2+ moved `bash_operator`, Kafka 4 removed
ZooKeeper). Do not treat it as working code.

Scheduled for deletion at the end of Phase 5. See `../DESIGN.md`.

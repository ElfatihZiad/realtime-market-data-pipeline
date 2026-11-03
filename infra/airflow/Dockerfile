# Airflow 3.3.2 on Python 3.13 — the workspace packages require >=3.13.
#
# The batch loaders and dbt are installed INTO this image rather than shelled
# out to, so a task failure is a Python traceback in the task log instead of a
# non-zero exit code with no context.
FROM apache/airflow:3.3.2-python3.13

USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*
USER airflow

# Build context is the repo root.
COPY --chown=airflow:root libs/mdp_core      /opt/mdp/libs/mdp_core
COPY --chown=airflow:root services/batch     /opt/mdp/services/batch
COPY --chown=airflow:root contracts          /opt/mdp/contracts
COPY --chown=airflow:root warehouse          /opt/mdp/warehouse

RUN pip install --no-cache-dir \
        /opt/mdp/libs/mdp_core \
        /opt/mdp/services/batch \
        "dbt-core>=1.12,<2" \
        "dbt-clickhouse>=1.9" \
        "pyiceberg[sql-sqlite]>=0.9"

# mdp_core resolves the Avro schemas by walking up from its own file, which
# does not work once it is installed into site-packages.
ENV MDP_CONTRACTS_DIR=/opt/mdp/contracts
ENV DBT_PROFILES_DIR=/opt/mdp/warehouse

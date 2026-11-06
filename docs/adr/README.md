# Architecture Decision Records

Short records of the decisions that shaped the rebuild, and — more usefully —
the ones that were rejected. Format: context, decision, consequences.

## Index

| ADR | Decision |
|---|---|
| [0001](0001-drop-cassandra-for-clickhouse.md) | Drop Cassandra for ClickHouse |
| [0002](0002-iceberg-v2-not-v3.md) | Iceberg spec v2, not v3 |
| [0003](0003-flink-sql-over-pyflink.md) | Flink SQL, not the PyFlink DataStream API |
| [0004](0004-airflow-for-batch-only.md) | Airflow orchestrates batch only |
| [0005](0005-crypto-as-primary-feed.md) | Crypto is the primary feed |
| [0006](0006-protobuf-wire-format-registry-deferred.md) | Protobuf on the wire *(superseded by 0008)* |
| [0007](0007-price-as-double.md) | Price and size are doubles, with a stated limitation |
| [0008](0008-avro-and-schema-registry-over-protobuf.md) | Avro + Schema Registry, replacing Protobuf |
| [0009](0009-watermarks-and-late-data.md) | Watermarks, and what happens to trades that miss them |
| [0010](0010-flink-version-follows-connectors.md) | The Flink version follows its connectors |
| [0011](0011-ohlc-open-close-ordering.md) | open/close rest on a stated invariant |
| [0012](0012-iceberg-on-s3-compatible-storage.md) | Iceberg on S3-compatible storage |
| [0013](0013-clickhouse-left-join-has-no-nulls.md) | ClickHouse left joins have no NULLs |
| [0014](0014-dbt-medallion-and-build.md) | dbt medallion layering, and `build` not `run`+`test` |
| [0015](0015-airflow-standalone-for-dev.md) | Airflow `standalone` is dev-only |
| [0016](0016-observability-and-slos.md) | Metrics, traces and SLOs that evaluate |
| [0017](0017-sentiment-window-join.md) | Sentiment × price window join, pluggable scorer |

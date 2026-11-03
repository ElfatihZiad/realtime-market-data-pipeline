# 0012 — Iceberg on S3-compatible object storage, via a REST catalog

**Status:** accepted (Phase 3)

## Context

`DESIGN.md` called for Iceberg v2 on MinIO locally and S3 in cloud. MinIO no
longer publishes publicly pullable images — neither `minio/minio`,
`quay.io/minio/minio` nor `bitnami/minio` resolves, and neither registry will
even list tags.

The obvious fallback is a local filesystem warehouse. That was tried and
rejected, for a reason worth recording: with a `file://` warehouse Iceberg
writes through Hadoop's `ChecksumFileSystem`, which cannot create the nested
partition directories and fails every checkpoint with

```
Mkdirs failed to create file:/warehouse/market/ticks/data/dt=.../instrument_id=...
```

Forcing `fs.file.impl=RawLocalFileSystem` fixes the writes and then breaks the
reads — `Not implemented by the RawLocalFileSystem FileSystem implementation`.
An unreadable lake is not a lake.

## Decision

Run `adobe/s3mock` as the object store and have Iceberg write through
**S3FileIO**, with an Iceberg REST catalog in front.

## Consequences

- The data path is the AWS SDK, not Hadoop's filesystem layer — which is what
  production actually looks like. Moving to real S3 is a change of endpoint and
  credentials; no job changes.
- A REST catalog rather than a Hadoop catalog means any engine (Flink, Spark,
  DuckDB, Trino) can discover the tables through one documented API.
- Hadoop is still on the Flink classpath: Iceberg's connector imports
  `org.apache.hadoop.conf.Configuration` during catalog setup even when no
  Hadoop filesystem is used. It is one shaded jar and nothing calls into it.
- s3mock is a test double. It is enough to exercise S3FileIO, bucket
  semantics and path-style addressing; it is not a durability story, and the
  warehouse is a dev volume.
- Iceberg will not create the bucket, exactly as real S3 would not, so a small
  init container does it.

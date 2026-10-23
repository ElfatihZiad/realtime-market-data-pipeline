# 0008 — Avro + Schema Registry, replacing Protobuf

**Status:** accepted (Phase 2). Supersedes [0006](0006-protobuf-wire-format-registry-deferred.md).

## Context

Phase 1 put bare Protobuf on the wire and deferred Schema Registry, because the
registry's framing (a magic byte plus a 4-byte schema id) is something
ClickHouse's `ProtobufSingle` format cannot skip.

Phase 2 introduces Flink, and Flink SQL's `protobuf` format does not read a
`.proto` file. It requires **compiled Java classes** packaged into a JAR and
named via `protobuf.message-class-name`. For a Python repo that means adding a
Maven build, a JVM toolchain in CI, and a second code-generation path — all to
describe eight fields.

Flink SQL's `avro-confluent` format needs none of that: it resolves schemas
from the registry at runtime. ClickHouse reads the same framing natively via
`AvroConfluent` with `format_avro_schema_registry_url`.

## Decision

Avro is the wire format, with Confluent Schema Registry as the authority.
`contracts/market/v1/*.avsc` are the source of truth; the producer registers
`tick.avsc` on first use, and Flink registers the schemas for the topics it
writes.

## Consequences

- One format understood natively by all three runtimes, with no codegen step at
  all — `just codegen`, the `gen/` package and the CI generate step are deleted.
- Schema evolution is enforced: the registry runs BACKWARD compatibility checks
  and rejects a breaking contract change at the producer, not in production.
- Protobuf's compactness is lost. Irrelevant at this volume.
- The decision was driven by what the engines actually support rather than by
  which format is nicer in the abstract. Protobuf would have been fine with a
  JVM build; it was not worth one.

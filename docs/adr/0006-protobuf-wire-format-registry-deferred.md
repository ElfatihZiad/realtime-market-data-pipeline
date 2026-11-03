# 0006 — Protobuf on the wire now, Schema Registry in Phase 2

**Status:** accepted (Phase 1), superseded by Phase 2

## Context

The plan called for Protobuf **plus** Confluent Schema Registry from Phase 1.
There is a concrete incompatibility: the registry's serialisers frame each
message with a magic byte and a 4-byte schema id before the payload. ClickHouse's
`ProtobufSingle` format expects a bare serialised message and cannot skip that
header. In Phase 1, ClickHouse reads the topic directly via the Kafka engine, so
registry framing would break ingestion.

## Decision

Phase 1 produces bare `ProtobufSingle` messages. The `.proto` files in
`contracts/` are the schema, mounted into ClickHouse and used to decode the topic
— so the contract is load-bearing, not decorative.

Schema Registry arrives in Phase 2, when Flink sits between Kafka and ClickHouse
and ClickHouse is fed by Flink rather than by the Kafka engine.

## Consequences

- No schema evolution enforcement in Phase 1. Acceptable: there is one producer
  and one consumer, both in this repo.
- The Phase 2 cutover changes the wire framing, so the topic will be recreated
  rather than migrated. It is a local dev topic with 24h retention.
- Deviation from the original plan, recorded here rather than made silently.

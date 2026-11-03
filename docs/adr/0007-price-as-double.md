# 0007 — Price and size are doubles (for now)

**Status:** accepted, with a known limitation

## Context

`Tick.price` and `Tick.size` are protobuf `double`, stored as ClickHouse
`Float64`. Binary floating point cannot represent a tick size of 0.01 exactly.
The error is tiny per trade but compounds through VWAP and bar aggregation, and
in a system that settled money it would be a defect.

Protobuf has no decimal type. The real options are scaled integers (price in
satoshis / cents, plus an exponent) or a decimal string.

## Decision

Use `double` for now, and say so plainly rather than let a reader assume it was
not considered.

## Consequences

- Exact for the demo's purposes; the error is far below one tick.
- Revisit if this ever computes a P&L number anyone acts on, at which point the
  contract gains `price_scaled int64` + `price_exponent int32`.
- Changing it later is a breaking contract change, which is exactly the kind of
  change Schema Registry (ADR 0006) exists to govern.

# 0017 — Sentiment joined to price with a window join, and a pluggable scorer

**Status:** accepted (Phase 5)

## Context

The differentiator this project set out to build was news sentiment correlated
with price moves. Two design questions had real answers.

**How to join two streams.** A regular join on `window_start` would be an
unbounded stateful join producing *updating* rows, which an append-only Kafka
sink rejects outright. A **window join** is bounded — once the watermark passes
a window, that window's state is released — and its output is append-only by
construction.

**What to do about windows with no news.** Most five-minute windows contain
trades and nothing else.

## Decision

A stream-to-stream **window join** on 5-minute event-time windows, each side
with its own watermark: 5 seconds for trades, **10 minutes for news**, because
feeds publish on their own schedule and we poll every few minutes. Pretending
news is as timely as a trade feed would drop most of it as late.

The join is **INNER**. A row claiming "sentiment 0.0" for a window where
nothing was published would be a fabricated reading, not a neutral one.

The bars side keys on `window_start`, not `window_end`. A 5m bar for
`[10:00, 10:05)` has `window_end` 10:05, which `TUMBLE` would place in the
*next* window; keying on the start aligns both sides on the same boundaries.

Scoring is a `Protocol` with two implementations: **VADER** (default — no key,
no network, deterministic) and **Claude** (`ANTHROPIC_API_KEY`, structured
output so the result is always a number in range).

## Consequences

- The project runs end to end for anyone who clones it, with no credentials.
- The scorer swap is one setting, and the comparison is the point: same
  pipeline, same windows, and VADER's weakness on financial framing — "ETF
  approval delayed again" reads as neutral to a lexicon — becomes visible
  rather than theoretical.
- Headlines that do not clearly name an instrument are **dropped, not guessed
  at**: a mis-tagged headline becomes a wrong sentiment reading for a real
  instrument. Keyword matching is word-boundary anchored, so "solution" is not
  Solana and "ethereal" is not Ethereum.
- Claude scores are clamped to [-1, 1] on receipt. The schema constrains the
  model, but an out-of-range score would skew every window it landed in.
- RSS rather than a news API: GDELT was tried first and returns 429 under even
  light polling. Three crypto feeds are free, keyless and not rate limited.

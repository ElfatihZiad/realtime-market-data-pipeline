# 0005 — Crypto is the primary feed

**Status:** accepted (Phase 1)

## Context

The old pipeline polled Alpha Vantage for US equities. Outside trading hours it
called `kafka_producer_fake()`, which published a random walk
(`close + np.random.uniform(-200, 200)`) to the **same topic** as real prices,
with no marker distinguishing the two. The dashboard therefore always looked
alive, and no consumer could tell real data from invented data.

Meanwhile Alpha Vantage moved `TIME_SERIES_DAILY_ADJUSTED` behind a paywall and
the free tier is heavily rate limited.

## Decision

Coinbase's public WebSocket feed is the primary source: free, keyless, and
trading 24/7. Equities become a secondary source behind the same canonical
`Tick` contract.

## Consequences

- The demo is live whenever anyone opens it, including at 3am on a Sunday.
- The fake-data path is deleted outright. Nothing in this repo fabricates a price.
- A real WebSocket feed means real reconnects and real backpressure — which is
  the point, since those are the failure modes worth demonstrating.

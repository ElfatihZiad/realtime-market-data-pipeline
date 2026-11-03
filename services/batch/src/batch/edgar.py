"""SEC EDGAR company facts -> ClickHouse.

NOTE: untested against the live API. SEC returns 403 unless the User-Agent
carries a real contact address, which has to be the operator's own — see
SecAccessDenied below. The parsing is covered by unit tests against a recorded
response shape instead.

Replaces the Yahoo Finance scraper the original project used, which pulled an
undocumented `query2.finance.yahoo.com` endpoint that now requires a cookie and
crumb handshake and breaks regularly. EDGAR is the primary source those figures
are derived from, it is free, documented, and has no key.

SEC requires a descriptive User-Agent with contact details and rate-limits to
10 requests/second. Both are honoured below; being throttled by a public
regulator's API is a self-inflicted wound.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import structlog
from mdp_core import get_settings

log = structlog.get_logger("batch.edgar")

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# The facts worth having, and nothing else: companyfacts responses are large.
WANTED_FACTS = (
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "NetIncomeLoss",
    "Assets",
    "Liabilities",
    "StockholdersEquity",
    "CashAndCashEquivalentsAtCarryingValue",
    "EarningsPerShareDiluted",
)

DDL = """
CREATE TABLE IF NOT EXISTS market.fundamentals
(
    ticker       LowCardinality(String),
    cik          UInt32,
    fact         LowCardinality(String),
    unit         LowCardinality(String),
    fiscal_year  UInt16,
    fiscal_period LowCardinality(String),
    period_end   Date,
    filed        Date,
    accession    String,
    value        Float64,
    loaded_at    DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY (ticker, fact, period_end, accession)
"""


def _client(user_agent: str) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
        timeout=30.0,
        follow_redirects=True,
    )


class SecAccessDenied(RuntimeError):
    """SEC rejected the request, almost always over the User-Agent."""


def _check(resp: httpx.Response) -> None:
    if resp.status_code == 403:
        raise SecAccessDenied(
            "SEC returned 403. Their access policy requires a User-Agent that "
            "identifies you with a real contact address, in the form "
            "'Your Name your.email@example.com'. Set SEC_USER_AGENT in .env to "
            "your own details — a URL or a placeholder address is refused. "
            "See https://www.sec.gov/os/webmaster-faq#developers"
        )
    resp.raise_for_status()


def ticker_to_cik(client: httpx.Client, tickers: list[str]) -> dict[str, int]:
    resp = client.get(TICKER_MAP_URL)
    _check(resp)
    wanted = {t.upper() for t in tickers}
    out: dict[str, int] = {}
    for row in resp.json().values():
        sym = str(row["ticker"]).upper()
        if sym in wanted:
            out[sym] = int(row["cik_str"])
    missing = wanted - out.keys()
    if missing:
        log.warning("tickers_not_found", tickers=sorted(missing))
    return out


def extract_facts(ticker: str, cik: int, payload: dict[str, Any]) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    us_gaap = payload.get("facts", {}).get("us-gaap", {})
    for fact in WANTED_FACTS:
        entry = us_gaap.get(fact)
        if not entry:
            continue
        for unit, observations in entry.get("units", {}).items():
            for obs in observations:
                # Only observations tied to a filing and a period end are
                # usable; the rest cannot be placed on a timeline.
                if not obs.get("end") or not obs.get("filed"):
                    continue
                rows.append(
                    (
                        ticker,
                        cik,
                        fact,
                        unit,
                        int(obs.get("fy") or 0),
                        str(obs.get("fp") or ""),
                        obs["end"],
                        obs["filed"],
                        str(obs.get("accn") or ""),
                        float(obs.get("val") or 0.0),
                    )
                )
    return rows


def run(tickers: list[str] | None = None) -> int:
    settings = get_settings()
    tickers = tickers or settings.edgar_ticker_list
    if not tickers:
        log.info("no_tickers_configured")
        return 0

    import clickhouse_connect

    ch = clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
    )
    ch.command(DDL)

    total = 0
    with _client(settings.sec_user_agent) as client:
        cik_by_ticker = ticker_to_cik(client, tickers)
        for ticker, cik in sorted(cik_by_ticker.items()):
            resp = client.get(FACTS_URL.format(cik=cik))
            if resp.status_code == 403:
                _check(resp)
            if resp.status_code != 200:
                log.warning("facts_unavailable", ticker=ticker, status=resp.status_code)
                continue
            rows = extract_facts(ticker, cik, resp.json())
            if rows:
                ch.insert(
                    "market.fundamentals",
                    rows,
                    column_names=[
                        "ticker",
                        "cik",
                        "fact",
                        "unit",
                        "fiscal_year",
                        "fiscal_period",
                        "period_end",
                        "filed",
                        "accession",
                        "value",
                    ],
                )
            total += len(rows)
            log.info("loaded", ticker=ticker, cik=cik, rows=len(rows))
            # SEC allows 10 req/s; stay well under it.
            time.sleep(0.2)

    log.info("edgar_done", tickers=len(cik_by_ticker), rows=total)
    return total


def main() -> None:
    from mdp_core import configure_logging

    configure_logging(get_settings().log_level)
    run()


if __name__ == "__main__":
    main()

"""RSS parsing and instrument tagging.

RSS rather than a news API on purpose: these feeds are free, keyless, and not
rate limited, so the demo keeps working without anyone provisioning anything.
GDELT was tried first and returns 429 under even light polling.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from dataclasses import dataclass
from xml.etree import ElementTree

FEEDS: dict[str, str] = {
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "cointelegraph": "https://cointelegraph.com/rss",
    "decrypt": "https://decrypt.co/feed",
}

# Headline keywords -> instrument. Deliberately narrow: a headline that does
# not clearly name an instrument is dropped rather than guessed at, because a
# mis-tagged headline becomes a wrong sentiment reading for a real instrument.
INSTRUMENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "BTC-USD": ("bitcoin", "btc"),
    "ETH-USD": ("ethereum", "ether", "eth"),
    "SOL-USD": ("solana", "sol"),
}


@dataclass(frozen=True, slots=True)
class Article:
    article_id: str
    instrument_id: str
    source: str
    title: str
    url: str
    published_at_us: int


def article_id(url: str) -> str:
    """Stable id from the URL, so re-polling the same feed does not duplicate."""
    return hashlib.sha256(url.encode()).hexdigest()[:32]


def match_instrument(title: str) -> str | None:
    """Return the instrument a headline names, or None.

    Word-boundary matching: a substring match would tag "solution" as Solana
    and "ethereal" as Ethereum.
    """
    lowered = title.lower()
    for instrument, keywords in INSTRUMENT_KEYWORDS.items():
        for keyword in keywords:
            if re.search(rf"\b{re.escape(keyword)}\b", lowered):
                return instrument
    return None


def _parse_date(value: str | None) -> int | None:
    """RFC 822 (RSS) or ISO 8601 (Atom). Returns epoch microseconds UTC."""
    if not value:
        return None
    for parse in (_parse_rfc822, _parse_iso):
        parsed = parse(value.strip())
        if parsed is not None:
            return parsed
    return None


def _parse_rfc822(value: str) -> int | None:
    from email.utils import parsedate_to_datetime

    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return int(parsed.timestamp() * 1_000_000)


def _parse_iso(value: str) -> int | None:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return int(parsed.timestamp() * 1_000_000)


def parse_feed(source: str, xml: bytes) -> list[Article]:
    """Parse an RSS or Atom document into tagged articles.

    Items without a usable link, title or date are skipped: an article with no
    publish time cannot be placed in an event-time window.
    """
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        return []

    atom = "{http://www.w3.org/2005/Atom}"
    nodes = root.findall(".//item") or root.findall(f".//{atom}entry")

    articles: list[Article] = []
    for node in nodes:
        title = (node.findtext("title") or node.findtext(f"{atom}title") or "").strip()
        link = (node.findtext("link") or "").strip()
        if not link:
            link_el = node.find(f"{atom}link")
            link = (link_el.get("href") or "").strip() if link_el is not None else ""
        published = _parse_date(
            node.findtext("pubDate")
            or node.findtext(f"{atom}published")
            or node.findtext(f"{atom}updated")
        )
        if not (title and link and published):
            continue
        instrument = match_instrument(title)
        if instrument is None:
            continue
        articles.append(
            Article(
                article_id=article_id(link),
                instrument_id=instrument,
                source=source,
                title=title,
                url=link,
                published_at_us=published,
            )
        )
    return articles

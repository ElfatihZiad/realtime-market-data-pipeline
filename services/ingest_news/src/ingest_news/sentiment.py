"""Sentiment scoring, pluggable.

Two scorers behind one interface:

- **vader** (default) — a lexicon rule set. No key, no network, deterministic,
  instant. It is genuinely weak on financial language: "Bitcoin plunges" and
  "Bitcoin surges" it handles, "ETF approval delayed again" it does not.
- **claude** — reads the headline the way a person would, including the
  financial framing VADER misses. Needs ANTHROPIC_API_KEY.

The default is VADER so the project runs for anyone who clones it, and the
comparison is the point: the same pipeline, the same windows, two scorers, and
you can see where the lexicon falls down.
"""

from __future__ import annotations

import json
import os
from typing import Protocol

import structlog

log = structlog.get_logger("ingest_news.sentiment")

CLAUDE_MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = """You score financial news headlines for market sentiment.

Return a score in [-1, 1] for how the headline reads for the named asset's price:
 -1 strongly bearish, 0 neutral or purely factual, +1 strongly bullish.

Judge the market implication, not the tone of the language. "Regulator approves
spot ETF" is bullish even though it is written flatly. "Exchange halts
withdrawals" is bearish even if phrased neutrally. A headline that merely
reports a price move already known to the market is close to neutral."""


class Scorer(Protocol):
    name: str

    def score(self, title: str, instrument_id: str) -> float: ...


class VaderScorer:
    """Lexicon scoring. No key, no network, deterministic."""

    name = "vader"

    def __init__(self) -> None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        self._analyzer = SentimentIntensityAnalyzer()

    def score(self, title: str, instrument_id: str) -> float:
        # compound is already normalised to [-1, 1].
        return float(self._analyzer.polarity_scores(title)["compound"])


class ClaudeScorer:
    """Claude scoring, with structured output so the result is always a number."""

    name = "claude"

    def __init__(self, api_key: str) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)

    def score(self, title: str, instrument_id: str) -> float:
        response = self._client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=256,
            system=SYSTEM_PROMPT,
            # Headlines are short and the judgement is quick; low effort keeps
            # this affordable at one call per article.
            output_config={
                "effort": "low",
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "sentiment": {"type": "number", "minimum": -1, "maximum": 1},
                        },
                        "required": ["sentiment"],
                        "additionalProperties": False,
                    },
                },
            },
            messages=[
                {
                    "role": "user",
                    "content": f"Asset: {instrument_id}\nHeadline: {title}",
                }
            ],
        )
        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            value = float(json.loads(text)["sentiment"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            log.warning("claude_score_unparseable", title=title[:80])
            return 0.0
        # Clamp rather than trust: the schema constrains the model, but a score
        # outside [-1, 1] downstream would skew every window it lands in.
        return max(-1.0, min(1.0, value))


def build_scorer(preferred: str) -> Scorer:
    """Return the requested scorer, falling back to VADER with a clear reason."""
    if preferred == "claude":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            log.warning("claude_scorer_unavailable", reason="ANTHROPIC_API_KEY is not set")
        else:
            try:
                return ClaudeScorer(api_key)
            except ImportError:
                log.warning(
                    "claude_scorer_unavailable",
                    reason="install the extra: uv sync --extra claude",
                )
    return VaderScorer()

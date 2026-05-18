"""
CSIS Database Context Integration
Fetches CSIS-published context for the digest LLM prompt:
- AMTI features tracker (gray-zone incidents)
- Hidden Reach product index (overseas footprint)
- China Power Project median-line incursion counts

Currently a stub — CSIS does not publish a single JSON timeline for China
the way it does for NK-Russia. When/if such a database exists, wire it in here.
"""
import os
import requests
from datetime import datetime, timezone, timedelta


def fetch_amti_recent() -> list:
    """Fetch recent AMTI features. Returns list of {date, title, url, summary}.
    Falls back to empty list if unavailable."""
    # AMTI doesn't expose a clean JSON feed; we rely on the RSS collector
    # in collect.py to surface AMTI articles via Google News search.
    return []


def fetch_hidden_reach_recent() -> list:
    """Fetch recent Hidden Reach products."""
    return []


def fetch_china_power_recent() -> list:
    """Fetch recent China Power Project items."""
    return []


def build_db_context(max_chars: int = 4000) -> str:
    """Build a textual context block for the digest LLM prompt.
    Currently returns an empty string when no databases are wired up.
    """
    blocks = []

    amti = fetch_amti_recent()
    if amti:
        lines = ["AMTI RECENT FEATURES (gray-zone tracker):"]
        for item in amti[:10]:
            lines.append(f"  • {item.get('date', '')}: {item.get('title', '')}")
        blocks.append("\n".join(lines))

    hr = fetch_hidden_reach_recent()
    if hr:
        lines = ["HIDDEN REACH RECENT PRODUCTS:"]
        for item in hr[:10]:
            lines.append(f"  • {item.get('date', '')}: {item.get('title', '')}")
        blocks.append("\n".join(lines))

    cp = fetch_china_power_recent()
    if cp:
        lines = ["CHINA POWER PROJECT RECENT ITEMS:"]
        for item in cp[:10]:
            lines.append(f"  • {item.get('date', '')}: {item.get('title', '')}")
        blocks.append("\n".join(lines))

    context = "\n\n".join(blocks)
    return context[:max_chars] if max_chars else context


if __name__ == "__main__":
    print(build_db_context())

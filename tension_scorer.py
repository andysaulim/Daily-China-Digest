"""
Daily Tension Scorer
Outputs 0–10 scores for three axes based on keyword signals in today's articles:
- Taiwan Strait tension
- South China Sea tension
- US–China relations tension

Used by render.py as an optional Δ Since Yesterday badge.
"""
import re

TAIWAN_STRAIT_SIGNALS = {
    "escalation": re.compile(
        r"\b(pla|plaaf|plan)\s+(exercise|drills|incursion|fly|cross)|"
        r"adiz\s+incursion|median\s+line|"
        r"taiwan\s+strait\s+(tension|exercise|drill)|"
        r"j-?16|j-?20|j-?10|y-?20|"
        r"taiwan\s+arms\s+sale|f-?16v|himars|harpoon",
        re.IGNORECASE,
    ),
    "deescalation": re.compile(
        r"taiwan\s+strait\s+(stable|calm|reduced)|"
        r"cross-strait\s+(dialogue|talk|meeting)",
        re.IGNORECASE,
    ),
}

SCS_SIGNALS = {
    "escalation": re.compile(
        r"scarborough|ayungin|second\s+thomas|sierra\s+madre|"
        r"water\s+cannon|ccg|coast\s+guard|"
        r"mischief|fiery\s+cross|subi|sandy\s+cay|whitsun|"
        r"south\s+china\s+sea\s+(incident|clash|standoff)",
        re.IGNORECASE,
    ),
    "deescalation": re.compile(
        r"south\s+china\s+sea\s+(talk|agreement|reduced)|"
        r"code\s+of\s+conduct",
        re.IGNORECASE,
    ),
}

US_CHINA_SIGNALS = {
    "escalation": re.compile(
        r"tariff|section\s+301|section\s+232|entity\s+list|"
        r"export\s+control|sanction(s)?|sdn|1260h|"
        r"cfius|outbound\s+investment|"
        r"decoupling|de-risk|trade\s+war",
        re.IGNORECASE,
    ),
    "deescalation": re.compile(
        r"trump-xi|xi-trump|summit|phase\s+(one|two)|"
        r"trade\s+deal|tariff\s+(rollback|reduction|paused)|"
        r"rubio.{1,20}wang\s+yi|wang\s+yi.{1,20}rubio",
        re.IGNORECASE,
    ),
}


def _score_axis(articles: list, signals: dict, baseline: int = 5) -> int:
    """Score one axis 0–10 based on signal counts in article titles + summaries."""
    esc = 0
    deesc = 0
    for art in articles:
        text = f"{art.get('title', '')} {art.get('summary', '')}"
        if signals["escalation"].search(text):
            esc += 1
        if signals["deescalation"].search(text):
            deesc += 1
    # Cap each side at 5 to prevent runaway scores
    esc = min(esc, 8)
    deesc = min(deesc, 8)
    score = baseline + (esc // 2) - (deesc // 2)
    return max(0, min(10, score))


def score_all(payload: dict) -> dict:
    """Score all three axes from a collected payload."""
    all_articles = (
        (payload.get("tier1") or [])
        + (payload.get("tier2") or [])
        + (payload.get("tier4") or [])
    )
    return {
        "taiwan_strait": _score_axis(all_articles, TAIWAN_STRAIT_SIGNALS),
        "south_china_sea": _score_axis(all_articles, SCS_SIGNALS),
        "us_china_relations": _score_axis(all_articles, US_CHINA_SIGNALS),
    }


if __name__ == "__main__":
    import json, sys
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            payload = json.load(f)
        print(json.dumps(score_all(payload), indent=2))
    else:
        print("Usage: python tension_scorer.py <collected.json>")

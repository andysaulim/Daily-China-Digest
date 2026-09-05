"""
The one word counter.

There were three: digest.py counted 11 sections to decide whether to ask the
model for more, run.py counted 13 to decide whether to block the send, and
render.py counted a third set to print "N words, M min read" in the header.
On run 114 the first said 1,787 and the second said 2,253 for the same digest,
so the model was told to write 1,500-1,900, believed it had, and was then
flagged for breaching a 2,100 ceiling it could not see. The reader would have
been shown yet another number.

A length target is only meaningful if the thing setting it and the thing
enforcing it are counting the same words. This module is that definition:
every text field a reader actually sees.
"""

# Item-level fields that carry prose the reader reads.
TEXT_FIELDS = (
    "headline", "title", "body", "body_text", "summary", "detail", "statement",
    "context", "quote_text", "analyst_note", "so_what", "pattern_note",
    "central_argument", "policy_so_what", "policy_implication", "action",
    "document", "topic", "who", "handle_context", "speaker", "role",
    "official", "ministry", "committee", "members", "position", "predecessor",
    "event", "relevance", "label", "src_line", "authors", "framework",
)

# Every section rendered as a list of items.
ITEM_SECTIONS = (
    "top_stories", "overnight_items", "indo_pacific", "business_economy",
    "also_today", "official_line", "opeds_today", "academic_today",
    "social_statements", "prc_government", "congressional_watch",
    "npc_politburo", "personnel_changes", "calendar_watch", "on_this_day",
)

# Top-level prose.
SCALAR_FIELDS = ("re_line", "editor_note")

# xinhua_delta is a dict, not a list.
DELTA_FIELDS = ("bottom_line", "doctrinal_shift", "peoples_daily_front_page",
                "global_times_editorial", "xi_activity", "notable_omissions")


def _w(value) -> int:
    return len(str(value).split()) if value else 0


def count_words(digest: dict) -> int:
    """Words the reader sees. The single definition used by the prompt target,
    the validator gate and the rendered header."""
    if not isinstance(digest, dict):
        return 0
    words = 0

    for field in SCALAR_FIELDS:
        words += _w(digest.get(field))

    for item in (digest.get("morning_memo") or []):
        if isinstance(item, str):
            words += _w(item)
        elif isinstance(item, dict):
            words += sum(_w(v) for v in item.values() if isinstance(v, str))

    for section in ITEM_SECTIONS:
        for item in (digest.get(section) or []):
            if not isinstance(item, dict):
                words += _w(item)
                continue
            for field in TEXT_FIELDS:
                val = item.get(field)
                if isinstance(val, list):
                    words += sum(_w(v) for v in val)
                else:
                    words += _w(val)

    delta = digest.get("xinhua_delta")
    if isinstance(delta, dict):
        for field in DELTA_FIELDS:
            words += _w(delta.get(field))

    ks = digest.get("key_stat")
    if isinstance(ks, dict):
        for field in ("label", "context"):
            words += _w(ks.get(field))

    for loc in (digest.get("monitored_locations") or []):
        if isinstance(loc, dict):
            words += _w(loc.get("note"))

    return words


if __name__ == "__main__":
    d = {
        "re_line": "one two three",                                   # 3
        "editor_note": "four five",                                   # 2
        "morning_memo": ["a b", "c d", "e f"],                        # 6
        "top_stories": [{"headline": "g h", "body": "i j k"}],        # 5
        "official_line": [{"statement": "l m", "context": "n"}],      # 3
        "xinhua_delta": {"bottom_line": "o p"},                       # 2
        "key_stat": {"label": "q", "context": "r"},                   # 2
        "monitored_locations": [{"note": "s t"}],                     # 2
    }
    assert count_words(d) == 25, count_words(d)
    assert count_words({}) == 0
    assert count_words(None) == 0
    # A list-valued field (authors, members) must be counted, not stringified.
    assert count_words({"opeds_today": [{"authors": ["a b", "c"]}]}) == 3
    print("wordcount.py self-test passed")

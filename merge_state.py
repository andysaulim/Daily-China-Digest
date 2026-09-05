"""
Merge this run's state files with whatever another run pushed while we worked.

Two runs on the same branch regenerate feed_health.json, url_cache.json and
metrics.jsonl independently, so a plain `git pull --rebase` hits an add/add
conflict on all three, aborts the rebase, and the follow-up `git push` reports
"Everything up-to-date" while that run's state is silently thrown away. That is
exactly what happened to run 112 on 2026-09-04: the step exited 0 and the data
was gone.

These files are caches and append-only logs, not source, so the merge is
well defined and does not need git's help:

  feed_health.json  dict of source -> record. Take the record with the later
                    last_seen; ties go to this run, which is the one that just
                    measured the feed.
  url_cache.json    dict of gnews url -> canonical url. Union; a resolved URL
                    never becomes wrong, so either side is fine on a clash.
  metrics.jsonl     append-only log. Union of lines, order preserved, exact
                    duplicates dropped.

Usage (the workflow does this after checking out the remote copies):
    python merge_state.py <snapshot-dir>
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
FEED_HEALTH = "feed_health.json"
URL_CACHE = "url_cache.json"
METRICS = "metrics.jsonl"


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


# A union never forgets: a feed renamed or removed from the registry would sit
# in feed_health.json forever, because the other side of every merge still has
# it. Entries whose last measurement is this far behind the newest one in the
# merged set are dropped. Measured against the newest last_seen rather than the
# wall clock so the merge stays a pure function of its inputs.
STALE_FEED_DAYS = 45


def _days_between(a: str, b: str) -> int:
    from datetime import date
    try:
        ya, ma, da = (int(x) for x in a.split("-"))
        yb, mb, db = (int(x) for x in b.split("-"))
        return (date(yb, mb, db) - date(ya, ma, da)).days
    except (ValueError, TypeError):
        return 0


def merge_feed_health(mine: dict, theirs: dict) -> dict:
    out = dict(theirs)
    for source, rec in mine.items():
        other = out.get(source)
        if not isinstance(other, dict) or not isinstance(rec, dict):
            out[source] = rec
            continue
        # Later measurement wins; a tie means this run, which just ran the feed.
        if str(rec.get("last_seen") or "") >= str(other.get("last_seen") or ""):
            out[source] = rec
    newest = max((str(r.get("last_seen") or "") for r in out.values()
                  if isinstance(r, dict)), default="")
    if newest:
        out = {k: v for k, v in out.items()
               if not isinstance(v, dict)
               or _days_between(str(v.get("last_seen") or newest), newest) <= STALE_FEED_DAYS}
    return out


def merge_url_cache(mine: dict, theirs: dict) -> dict:
    merged = dict(theirs)
    merged.update(mine)
    return merged


def merge_metrics(mine: list[str], theirs: list[str]) -> list[str]:
    seen, out = set(), []
    for line in theirs + mine:
        line = line.rstrip("\n")
        if line and line not in seen:
            seen.add(line)
            out.append(line)
    return out


def main(snapshot_dir: str) -> int:
    snap = Path(snapshot_dir)
    changed = []

    for name, merge in ((FEED_HEALTH, merge_feed_health), (URL_CACHE, merge_url_cache)):
        mine_path, live_path = snap / name, ROOT / name
        if not mine_path.exists():
            continue
        mine, theirs = _load_json(mine_path), _load_json(live_path)
        merged = merge(mine, theirs)
        if merged != theirs:
            live_path.write_text(
                json.dumps(merged, ensure_ascii=False,
                           indent=1 if name == FEED_HEALTH else 0,
                           sort_keys=(name == FEED_HEALTH)),
                encoding="utf-8")
            changed.append(f"{name} ({len(theirs)} remote + {len(mine)} local -> {len(merged)})")

    mine_path, live_path = snap / METRICS, ROOT / METRICS
    if mine_path.exists():
        mine = mine_path.read_text(encoding="utf-8").splitlines()
        theirs = live_path.read_text(encoding="utf-8").splitlines() if live_path.exists() else []
        merged = merge_metrics(mine, theirs)
        if merged != theirs:
            live_path.write_text("\n".join(merged) + "\n", encoding="utf-8")
            changed.append(f"{METRICS} ({len(theirs)} remote + {len(mine)} local -> {len(merged)})")

    print("  [merge-state] " + ("; ".join(changed) if changed else "nothing to merge"))
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] != "--self-test":
        sys.exit(main(sys.argv[1]))

    # Self-test, run by smoke_test.py. No filesystem, no git.
    fh_mine = {"Reuters China": {"last_seen": "2026-09-05", "last_count": 100, "empty_runs": 0},
               "New Feed": {"last_seen": "2026-09-05", "last_count": 7, "empty_runs": 0}}
    fh_theirs = {"Reuters China": {"last_seen": "2026-09-04", "last_count": 0, "empty_runs": 2},
                 "Old Feed": {"last_seen": "2026-09-04", "last_count": 3, "empty_runs": 0}}
    m = merge_feed_health(fh_mine, fh_theirs)
    assert m["Reuters China"]["last_count"] == 100, m["Reuters China"]   # newer wins
    assert m["Old Feed"]["last_count"] == 3, m                            # remote-only kept
    assert m["New Feed"]["last_count"] == 7, m                            # local-only kept
    assert len(m) == 3, m
    # An older local measurement must not clobber a newer remote one.
    # A key nobody has measured in over STALE_FEED_DAYS ages out of the union.
    m3 = merge_feed_health({"Live": {"last_seen": "2026-09-05", "last_count": 4}},
                           {"Live": {"last_seen": "2026-09-04", "last_count": 4},
                            "Renamed Away": {"last_seen": "2026-07-01", "last_count": 0}})
    assert "Renamed Away" not in m3 and "Live" in m3, m3
    m4 = merge_feed_health({}, {"Recent": {"last_seen": "2026-08-01", "last_count": 1},
                                "Now": {"last_seen": "2026-09-05", "last_count": 1}})
    assert "Recent" in m4, m4   # 35 days: still inside the window
    m2 = merge_feed_health({"A": {"last_seen": "2026-09-01", "last_count": 0}},
                           {"A": {"last_seen": "2026-09-04", "last_count": 50}})
    assert m2["A"]["last_count"] == 50, m2

    uc = merge_url_cache({"g1": "https://a", "g2": "https://b"}, {"g1": "https://a", "g3": "https://c"})
    assert uc == {"g1": "https://a", "g2": "https://b", "g3": "https://c"}, uc

    mm = merge_metrics(['{"date":"2026-09-05"}'], ['{"date":"2026-09-04"}', '{"date":"2026-09-05"}'])
    assert mm == ['{"date":"2026-09-04"}', '{"date":"2026-09-05"}'], mm   # no duplicate, order kept
    print("merge_state.py self-test passed")

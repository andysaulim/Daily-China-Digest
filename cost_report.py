"""
What the China Daily Brief costs to run.

Modelled on the Korea and Australia briefs' cost_report.py, which both exist and
which this pipeline lacked: run.py has recorded per-call tokens and a run total
in metrics.jsonl since the relaunch, and nothing ever read them back, so a
month's spend was invisible unless someone opened every run log by hand.

Unlike the Australia version, this one does NOT carry its own price table.
digest.MODEL_PRICING is the single definition and digest.cost_of the single
calculation; a second table here would drift the way the four word counters did
(run 114: 1,787 vs 2,253 words on the same object). Prices live in one place.

Reads metrics.jsonl, which the workflow commits after every run, so this works
from a fresh checkout.

    python cost_report.py            # last 30 days
    python cost_report.py --days 7
    python cost_report.py --json     # machine-readable
"""
import argparse
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from digest import MODEL_PRICING, cost_of

METRICS = Path(__file__).parent / "metrics.jsonl"


def load_metrics(days: int) -> list[dict]:
    """Runs from the last `days` days, oldest first. Bad lines are skipped."""
    if not METRICS.exists():
        return []
    cutoff = date.today() - timedelta(days=days)
    rows = []
    for line in METRICS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            m = json.loads(line)
            d = datetime.strptime(m["date"], "%Y-%m-%d").date()
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
        if d >= cutoff:
            rows.append(m)
    return sorted(rows, key=lambda r: (r.get("date", ""), r.get("started", "")))


def summarise(rows: list[dict]) -> dict:
    """Totals overall, per model, and split live vs test."""
    per_model = defaultdict(lambda: {"calls": 0, "input": 0, "output": 0,
                                     "cache_write": 0, "cache_read": 0,
                                     "seconds": 0.0, "cost": 0.0})
    total = live = test = 0.0
    live_runs = test_runs = 0
    regens = 0
    for r in rows:
        run_total = 0.0
        for call in (r.get("tokens") or []):
            c = cost_of(call)
            m = per_model[call.get("model", "unknown")]
            m["calls"] += 1
            for k in ("input", "output", "cache_write", "cache_read"):
                m[k] += call.get(k, 0)
            m["seconds"] += call.get("seconds", 0) or 0
            m["cost"] += c
            run_total += c
        # Fall back to the recorded total when a run predates per-call tokens.
        if not (r.get("tokens") or []):
            run_total = r.get("cost_usd") or 0.0
        total += run_total
        if r.get("test_mode"):
            test += run_total
            test_runs += 1
        else:
            live += run_total
            live_runs += 1
        regens += max(0, (r.get("validation_attempts") or 1) - 1)
    return {"total": total, "live": live, "test": test, "live_runs": live_runs,
            "test_runs": test_runs, "regenerations": regens,
            "per_model": {k: dict(v) for k, v in per_model.items()}}


def _fmt(rows: list[dict], s: dict, days: int) -> str:
    out = [f"China Daily Brief — cost, last {days} days",
           "=" * 58, ""]
    if not rows:
        out.append("  No runs recorded in metrics.jsonl for this window.")
        return "\n".join(out)

    runs = s["live_runs"] + s["test_runs"]
    out.append(f"  Runs              {runs}  ({s['live_runs']} live, {s['test_runs']} test)")
    out.append(f"  Total             ${s['total']:.2f}")
    out.append(f"    live            ${s['live']:.2f}")
    out.append(f"    test            ${s['test']:.2f}")
    if s["live_runs"]:
        out.append(f"  Per live issue    ${s['live'] / s['live_runs']:.2f}")
        out.append(f"  Projected month   ${s['live'] / s['live_runs'] * 30:.2f}  (30 live issues)")
    if s["regenerations"]:
        out.append(f"  Regenerations     {s['regenerations']}  (each one is a second full model pass)")
    out.append("")

    out.append("  By model")
    out.append(f"    {'model':<20}{'calls':>6}{'in':>10}{'out':>10}{'cost':>9}")
    for name, m in sorted(s["per_model"].items(), key=lambda kv: -kv[1]["cost"]):
        priced = "" if name in MODEL_PRICING else "  (unpriced, billed at Opus rates)"
        out.append(f"    {name:<20}{m['calls']:>6}{m['input']:>10,}{m['output']:>10,}"
                   f"{m['cost']:>9.2f}{priced}")
    out.append("")

    out.append("  Recent runs")
    out.append(f"    {'date':<12}{'mode':<6}{'words':>7}{'items':>7}{'sec':>6}{'cost':>8}")
    for r in rows[-10:]:
        calls = r.get("tokens") or []
        c = sum(cost_of(x) for x in calls) if calls else (r.get("cost_usd") or 0.0)
        items = sum(len(v) for k, v in (r.get("sections") or {}).items()
                    if isinstance(v, list)) or (r.get("sections") or {}).get("items", "")
        out.append(f"    {r.get('date',''):<12}{'test' if r.get('test_mode') else 'live':<6}"
                   f"{r.get('word_count') or '':>7}{items or '':>7}"
                   f"{round(r.get('seconds') or 0):>6}{c:>8.2f}")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description="What the brief costs to run.")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    rows = load_metrics(args.days)
    s = summarise(rows)
    if args.json:
        print(json.dumps({"days": args.days, "runs": len(rows), **s}, indent=2))
    else:
        print(_fmt(rows, s, args.days))


if __name__ == "__main__":
    main()

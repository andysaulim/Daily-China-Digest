# China Daily Brief: operating notes

Automated daily China intelligence brief for the CSIS Korea Chair. Sibling of the
Korea, Japan and Australia-Pacific briefs; this file is the ops memory the other
three keep in `CLAUDE.md` / `AUDIT` / `CHANGES_MEMO`.

## Pipeline

```
collect.py  ->  resolve.py  ->  fulltext.py  ->  digest.py  ->  run.py post-process
268 feeds       Google News     article body     Sonnet 5,       URL gate, dedup,
(55 ZH)         -> real URLs    for the model    Opus 5 retry    ledger, style
     -> validate (CRITICAL blocks) -> trackers -> render.py -> archive -> send_email.py
                                                                       -> ledger, last_sent.txt, metrics.jsonl
```

`python smoke_test.py` runs offline before every workflow run and must pass before a commit.
`python list_sources.py` regenerates `SOURCES.md`; the smoke test fails if it is stale.

## Rules that the code enforces (do not weaken in an edit)

- **SOURCE-OR-SKIP in code.** `run._repair_and_gate_urls`: an article item whose URL is not
  in the collected corpus is repaired by exact-title or 60 percent headline-token match, or
  deleted. Four or more deletions is CRITICAL and triggers regeneration.
- **Fail-closed send.** `validate_digest` findings containing `CRITICAL` block the send.
  Up to two regenerations (Sonnet, then Opus) with the findings as feedback. If it still
  fails, `digest.html` is rendered for review, nothing is sent, exit code 2, alert email.
- **State is written only on success.** Trackers after validation; `published_ledger.json`
  and `last_sent.txt` only after SMTP succeeds. Test runs (`--send-to`) write none of them.
- **Once-a-day guard.** The workflow skips a scheduled run when `last_sent.txt` is today (ET).
  Six staggered crons cover GitHub's dropped slots. Manual dispatch always runs.
- **No assistant prefill, no dated model IDs.** `FAST_MODEL`/`PRIMARY_MODEL` must be in
  `pipeline_health.KNOWN_MODEL_IDS`; the smoke test checks both.
- **Market honesty.** A figure that could not be fetched is `unavailable`, shown as a dash,
  and the prompt forbids inventing one. Never restore hard-coded fallback numbers.
- **Baselines expire.** `BASELINES_VERIFIED_AS_OF` in `digest.py` drives a staleness note in
  the prompt and a health alert at 60/120 days. Past dates in `_VERIFIED_UPCOMING` are
  filtered automatically. When you re-verify leaders, the tariff stack and the calendar,
  bump the date.
- **Chinese-language sources** are tagged `lang: ZH`, capped at 12 items per feed, exempt
  from the English keyword gate, and ranked up when they are a ministry's own words. The
  `official_line` section ("What Beijing Is Saying") quotes them verbatim with `original_zh`.
- **Length.** 2,000 to 3,000 words; `WORD_FLOOR_CRITICAL` 1,600 blocks, 3,200 warns. Reach
  the target by covering more items (official_line, overnight, indo_pacific, business,
  opeds), never by inflating bodies.
- **Experts and think tanks.** `EXPERT_WATCHLIST` (189 names, Chinese names included) tags
  items with `expert_flag`; Tier 2 carries US, allied and China-based institutes, the latter
  tagged `china_based`. The benchmark against the leading China newsletters is `BENCHMARK.md`.
- **Archive.** Live runs write `public/<date>.html`, `<date>.pdf` (Playwright, best effort),
  `index.html` (latest) and `archive.html` (all issues), and push `public/` to `gh-pages`.
  Emails link to the online, PDF and archive pages. Test runs never touch the archive.

## What went wrong before (and the fix)

| Date | Failure | Cause | Fix |
| --- | --- | --- | --- |
| May 25 to Jun 14 | Every issue linked only SCMP and three static CSIS pages | Google News redirect resolution returned 0/300; the sanitiser blanked every unmatched URL; a domain-level allowlist let hallucinated paths through | `resolve.py` (base64 + batchexecute decode), exact-URL gate with headline repair, unresolved links kept |
| Jun 15-16 | Crash: "All JSON extraction strategies failed" | 16k output cap truncated the reply; parse failure was not retried | 64k cap, parse failures retried, best attempt kept |
| Jun 17 to Aug 17 | 64 consecutive failures, 400 "does not support assistant message prefill" | Model IDs were bumped to 4.6/4.8 but the `{"` prefill stayed | Prefill removed; BadRequestError no longer retried four times |
| Jun 17 to Sep 4 | Nobody noticed for 80 days | No failure alert, no health check, validation printed failures and sent anyway | Alert email on failure, `pipeline_health.py`, fail-closed send, `metrics.jsonl` |
| Aug 17 | Schedule silently disabled by GitHub | 60 days without a commit | Runs commit state daily; check Actions tab shows the schedule enabled after a long gap |
| Every run | Market strip showed 10Y CGB 1.75 percent, LPR 3.0/3.5, CDS 70 bps as data | Hard-coded fallbacks | Unavailable, shown as dash |
| Every run | Model wrote 3-sentence bodies from a headline | Google News feeds carry no summary | `fulltext.py` fetches article text; summaries sent at 1,800 chars |

## Recurring maintenance

- **Monthly:** run `python pipeline_health.py` on a fresh `collected.json`; reroute dead feeds
  (`feed_health.json` lists them); confirm the model IDs are still served.
- **Quarterly:** re-verify `_POLITICAL_LEADERS`, `_TRADE_BASELINES`, `_VERIFIED_UPCOMING`,
  `_KEY_DATES` and the correspondent list; bump `BASELINES_VERIFIED_AS_OF`.
- **After a model change:** update `FAST_MODEL`, `PRIMARY_MODEL`, `MODEL_PRICING`,
  `pipeline_health.KNOWN_MODEL_IDS`, run the smoke test, then a `test` dispatch to yourself.

## Running

```
python run.py                       # live: full send + archive
python run.py --send-to you@x.org   # test: full pipeline, email only you, no state writes
python run.py --dry-run             # collect + resolve + fulltext only
python run.py --from-cache --no-send
```

Workflow dispatch inputs: `mode` = `test` (default) / `live` / `dry`, `send_to` for a test.
Secrets: `ANTHROPIC_API_KEY`, `GMAIL_USER`, `GMAIL_APP_PASS`, `DIGEST_TO`, optional `ALERT_TO`, `GH_PAT`.

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
- **Length.** 2,000 to 2,500 words; `WORD_FLOOR_CRITICAL` 1,600 blocks, 2,700 warns. The
  band moved up from 1,500-1,900 after run 118 hit 1,898 only because the trim deleted 17
  items, among them Xi's expected New Delhi visit and Japan's record defence budget. The
  extra words buy MORE ITEMS: section caps rose, per-item body limits did not. Cut from
  `also_today` and `academic_today` first, never from `top_stories`, `korea_china` or
  `official_line`.
- **Length is enforced in code, not by regeneration.** `run._enforce_section_caps` slices any
  section over its cap (a counting mistake, not an editorial one) and `run._trim_to_length`
  drops tail items until the digest is at or under `WORD_TARGET_HIGH` (2,500), cutting in
  `_TRIM_ORDER` and stopping at each section's floor. `top_stories` and `official_line` are
  never trimmed. Run 116 paid $0.80 for a regeneration triggered by 7 op-eds against a cap
  of 6, and still shipped 2,322 words.
- **One word counter.** `wordcount.count_words` is the only definition; `digest.py`,
  `run.py` and `render.py` all delegate to it. They used to disagree by 26 percent
  (run 114: 1,787 vs 2,253), so the model wrote to a target the gate did not measure.
- **Gmail clipping.** Gmail truncates a body over 102 KB. `run.check_email_size` warns at
  78 KB and BLOCKS the send at 96 KB, measured in encoded UTF-8 bytes (Chinese costs three
  bytes a character). A clipped brief is a broken brief.
- **Format order.** Header, The Bottom Line (`editor_note`), memo, top stories, The Korea
  Angle, overnight, THEN the market strip, Beijing's words and actions, the wire, and What
  We Are Watching to close. News before numbers; the frame before the news. `editor_note`
  was generated and word-counted but never rendered until Sep 4 2026.
- **Three fields were generated and never rendered.** `editor_note` (fixed Sep 4 2026),
  `china_macro` and `xinhua_delta` (both fixed Sep 5 2026) were produced on every run, counted
  toward the word total, and dropped by the renderer. `render.py`'s own docstring had promised
  the Xinhua Delta panel since the file was written. Before adding a field to the prompt,
  check that something renders it; `wordcount.py` counting it is not the same thing.
- **The Bottom Line is gated.** `editor_note` must reach a JUDGMENT, cite the evidence and
  close with a `Watch:` sentence. Under 25 words, or opening with "Today's brief covers",
  is CRITICAL; outside 55-130 words or missing `Watch:` is a warning. It renders above every
  section and until Sep 5 2026 nothing checked it at all.
- **The Korea Angle.** `korea_china` (0-3 items) is the standing section for the reader this
  brief is written for. It may be empty on a genuine no-news day — a warning, never a block —
  but it is never filled with a stretched item, and the length trim never touches it.
- **No trackers.** The TRACKERS chapter (satellite/location watch, tariff table, entity-list
  table) was removed Sep 5 2026: it was standing furniture rebuilt from `_TRADE_BASELINES`
  and `bp_tracker.json` rather than from reporting, and it rendered 108-day-old baselines as
  current fact. `_TRADE_BASELINES` stays in the PROMPT as background. Ministry actions moved
  to "What Beijing Did", Congressional Watch to the wire, the calendar to the close.
- **The market strip renders only what resolved.** No dead tiles: an indicator with no value
  is omitted and named once in a footnote. Five of nine tiles were bare em dashes on run 118.
  `china_macro` (CPI, PPI, manufacturing PMI, retail sales) was collected on every run since
  the pipeline was built and never rendered anywhere; it now fills the strip.
- **Market parsers must name what they match.** Every headline-scraped figure (LPR, GDP, CPI,
  PPI, PMI, retail) is accepted only when the indicator names ITSELF first, no other percentage
  sits between the name and the number, the value is in a sane band, and the text is not a
  forecast. The old LPR parser took the first two decimals in a headline, so "LPR held at
  3.00% as growth slowed to 4.8%" would have published a 5-year LPR of 4.80%.
- **Experts and think tanks.** `EXPERT_WATCHLIST` (189 names, Chinese names included) tags
  items with `expert_flag`; Tier 2 carries US, allied and China-based institutes, the latter
  tagged `china_based`. The benchmark against the leading China newsletters is `BENCHMARK.md`.
- **Concurrent runs.** `feed_health.json`, `url_cache.json` and `metrics.jsonl` are
  regenerated by every run, so the workflow NEVER rebases them: it checks out the remote
  copies and merges this run's onto them with `merge_state.py`. A rebase there hits an
  add/add conflict, aborts, and the follow-up push reports success while the run's state
  is silently discarded (run 112, Sep 4 2026).
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

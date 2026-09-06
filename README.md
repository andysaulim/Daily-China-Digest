# China Daily Brief

Automated daily intelligence briefing on the People's Republic of China for the CSIS Korea Chair. Sibling pipeline to [Daily-Korea-Digest](https://github.com/andysaulim/Daily-Korea-Digest), [Daily-Japan-Digest](https://github.com/andysaulim/Daily-Japan-Digest) and [Daily-Australia-Pacific-Islands-Digest](https://github.com/andysaulim/Daily-Australia-Pacific-Islands-Digest). Collects from 269 feeds (56 Chinese-language), canonicalises and fetches the articles, generates an analyst-grade digest via Claude, validates it, and delivers a styled HTML email at **6 AM ET**.

**Live archive:** [andysaulim.github.io/Daily-China-Digest](https://andysaulim.github.io/Daily-China-Digest) (latest issue at `index.html`, every issue at `archive.html`, each with a print-ready PDF). Every email carries "Read online", "Print / PDF" and "Archive" links. The archive is pushed to the `gh-pages` branch by the live workflow; GitHub Pages must be set to serve that branch once in repository settings.

**Benchmark against Sinocism, Pekingnology, Trivium, The Wire China, ChinaTalk, China Watcher and the CSIS trackers:** [`BENCHMARK.md`](BENCHMARK.md).

Operating notes, the failure history and the rules the code enforces are in [`CLAUDE.md`](CLAUDE.md). The full feed inventory is in [`SOURCES.md`](SOURCES.md) (generated).

---

## Latest Run

| Metric | Value |
| --- | --- |
| Last generated | Sep 6, 2026 at 9:50 AM ET |
| Digest date | Sunday, September 6, 2026 |
| Articles collected | 522 from 79 sources |
| Sources cited in digest | 12 |
| Google News URLs canonicalised | 485/485 |
| Items enriched with article text | 139 |
| Top stories / overnight / official line | 4 / 6 / 4 |
| Word count | ~1,547 |
| Validation attempts | 1 |
| Health alerts | 1 |
| Estimated model cost | $0.92 |
| Xi appeared | No |

## How It Works

```
collect.py      resolve.py      fulltext.py     digest.py         run.py             render.py     send_email.py
269 feeds  -->  Google News --> article text --> Claude Sonnet --> URL gate, dedup --> HTML email --> Gmail (BCC)
56 ZH           -> real URLs    for the model    (Opus on retry)   validate, retry     + archive/PDF  + ledger
+ markets                                                          trackers                          + metrics
```

1. **Collect** — 269 RSS feeds in parallel across 4 tiers plus Xi, Hidden Reach and gray-zone trackers. Direct publisher feeds with a Google News fallback where one exists; Google News search (US, zh-CN, zh-TW, zh-HK editions) elsewhere. Market strip from Yahoo/Stooq; anything that fails is marked unavailable, never a stale number.
2. **Resolve** — Google News redirect links are decoded to the publisher URL (base64 path, then Google's batch API), cached in `url_cache.json`. This is the step whose absence emptied the June issues of links.
3. **Enrich** — up to 160 canonical URLs are fetched in parallel; paragraph text (or the meta description behind a paywall) is appended to the summary so the model writes from the article, not the headline.
4. **Digest** — Claude Sonnet 5 generates the structured JSON; Opus 5 takes the second regeneration. No assistant prefill (the 4.6+/5 models reject it). Cross-day memory of the last 14 days of headlines is injected.
5. **Post-process (SOURCE-OR-SKIP in code)** — every article item's URL must be in the collected corpus: repaired by headline match or deleted. Within-edition and cross-day dedup, hollow-item filter, stale calendar and off-date anniversary removal, source cap, emoji and em-dash cleanup.
6. **Validate** — CRITICAL findings (section floors, date mismatch, mass unsourced items, duplicate memo) regenerate with the findings as feedback, up to twice. If they persist the brief is held, rendered for review, and the run fails so the alert fires. Advisories (prestige stories collected but unused, unverifiable quotes, broken links) are logged.
7. **Render / Send / Record** — table-based HTML email (v3.1 Publications register), Gmail SMTP with recipients in BCC, then `published_ledger.json`, `last_sent.txt` and `metrics.jsonl` are written only after the send succeeds.

---

## Source Coverage

| Tier | Feeds | Window | Content |
| --- | --- | --- | --- |
| **1 — News** | 122 | 24h | Wires, correspondents, PRC English press, regional Asia, Taiwan, US and allied government, specialist newsletters, **37 Chinese-language outlets** |
| **2 — Analysis** | 81 | 36h, dated only | US: CSIS (ChinaPower, AMTI, Interpret), Brookings, Carnegie, RAND, CFR, Hoover, Asia Society CCA, NBR, Wilson, Harvard, Stanford, UCSD, Georgetown, CNAS, CSBA, FDD, Cato, Quincy, AEI, Hudson, Heritage, PIIE, Rhodium, Paulson, USCBC, AmCham. Allied: MERICS, Chatham House, ECFR, IFRI, SWP, RUSI, EU Chamber, ASPI, Lowy, ORF, Takshashila, JIIA, ISDP, Sinolytics, Gavekal. **China-based: CICIR, CIIS, SIIS, Tsinghua CISS, Renmin Chongyang, CCG, Fudan CAS, PKU IISS, Pangoal, Taihe, CASS, China-US Focus** |
| **3 — Academic** | 18 | 72h, dated only | International Security, China Quarterly, Journal of Contemporary China and peers |
| **4 — PRC primary** | 23 | 48h | Xinhua, People's Daily, Global Times, CGTN, MOFA/MND/TAO/MOFCOM/State Council/PBOC in Chinese, signed commentaries |
| Trackers | 24 | 72h | Xi appearances, Hidden Reach sites, gray-zone features |

**Chinese-language sources (56):** 人民日报 · 新华社 · 环球时报 · 央视 · 中国新闻网 · 求是 · 解放军报 · 澎湃 · 观察者网 · 经济日报 · 财新 · 第一财经 · 21世纪经济报道 · 经济观察报 · 界面 · 证券时报 · 明报 · 香港01 · 星岛 · 信报 · 中央社 · 联合报 · 自由时报 · 中国时报 · 上报 · 联合早报 · 端传媒 · 纽约时报中文网 · FT中文网 · 华尔街日报中文 · BBC中文 · 德国之声 · 美国之音 · 日经中文 · 韩联社中文 · 法广中文 · 外交部 · 国务院 · 国防部 · 国台办 · 商务部 · 中国人民银行 · 新华时评. Titles and quotes are translated; the original Chinese is kept alongside official quotes.

**Prestige outlet rule:** WSJ, NYT, WaPo, Bloomberg, FT, The Economist, CNN, Reuters, AP, AFP, CNBC and Sinocism items carry a `prestige_outlet` flag; the validator names any that were collected and not used. **193 correspondents** are on the byline watch-list and **189 experts** (US, allied and Chinese scholars, with Chinese names) on the expert watch-list; an item written by or quoting one is ranked up and the author is named.

---

## Newsletter Sections (delivery order)

| # | Section | Description |
| - | - | - |
| 1 | Header | Date · RE line |
| 2 | **The Bottom Line** | 70–100 words: the judgment, the evidence for it, and a `Watch:` line naming what would confirm or break it. The lead, directly under the header. Generated as `editor_note`, and gated — a blank or a one-line recap blocks the send |
| 3 | Today at a Glance | Top 3 stories in one sentence each |
| 4 | Top Stories | 3–5 hard news stories with "So what" + pattern note |
| 5 | **US–China** | 4–6 items, one format, each tagged by instrument: Tariff · Export Controls · Entity List · Sanctions · CFIUS · Investment · Diplomacy · Military · Congress · Legal. Replaces the tracker tables |
| 6 | **China & the World** | 5–7 items, everyone except the US, each tagged by region: Cross-Strait (always one) · Japan · Korea · India · ASEAN · Australia-Pacific · Russia-Central Asia · Europe · Middle East · Africa · Latin America · Multilateral. Korea and Japan carry standing weight for this readership |
| 7 | Economy & Business | 3–6 items inside China: macro, corporates, property, tech |
| 8 | Stat of the Day + Market Strip | One dark data band. SSE · Hang Seng · USD/CNY · USD/CNH · Brent · 10Y CGB · 5Y CDS · LPR · GDP · CPI · PPI · Mfg PMI · Retail. Only indicators that resolved are shown; anything missing is named once in a footnote |
| 9 | Δ Since Yesterday | What moved |
| — | **BEIJING** | chapter |
| 10 | **Propaganda Delta** | Reading Xinhua, People's Daily and Global Times: doctrinal phrase movement, Xi's day, the front page, the Global Times line, a doctrinal shift or conspicuous omission, one quote. Generated as `xinhua_delta` |
| 11 | **What Beijing Is Saying** | The PRC government's own words: MOFA presser, TAO, MND, MOFCOM, State Council, PBOC, Xi / Li Qiang / Wang Yi. Verbatim quote, Chinese original, tone, addressee |
| 12 | What Beijing Did | Ministry actions with the document and thresholds, personnel changes, NPC/Politburo activity |
| 13 | Voices | Up to 5 op-eds and think-tank arguments from the watch-listed experts, US and China-based. The only analysis section |
| 14 | What Others Are Saying | Up to 4 quotes from US, Taiwan and allied officials |
| — | **WIRE** | chapter |
| 15 | Overnight Flash | 4–8 secondary items that fit none of the relationship sections |
| 16 | Also Today | Up to 8 one-line items |
| 17 | **What We Are Watching** | 4–5 dated events in the next 14–30 days. Closes the brief |
| 18 | Footer | Auto-generation disclaimer |

Removed Sep 2026: the TRACKERS chapter (satellite watch, tariff table, entity-list table:
standing furniture rebuilt from stale baselines), Indo-Pacific (folded into China & the
World), Congressional Watch (folded into US–China), Academic Journals and On This Day
(analysis and filler a daily brief does not need).

Target length **2,000–2,500 words**, an eight to ten minute read (hard floor 1,600; ceiling 2,700). The rendered email is also checked against Gmail's 102 KB clipping limit: over 96 KB the send is blocked. See [`BENCHMARK.md`](BENCHMARK.md) for why.

---

## Validation Gates

Blocking (regenerate, then hold):
- Top stories 3–5, overnight 4–8, official line ≥3, morning memo exactly 3 distinct items, RE line present
- The Bottom Line present, ≥25 words, and not opening with "Today's brief covers"
- Word count ≥1,600 (target 2,000–2,500)
- Rendered email ≥96 KB (Gmail clips at 102 KB)
- ≥4 items deleted for URLs not in the input
- Digest date ≠ today

Advisory (logged, sent):
- Prestige stories collected but unused (named), quotes not found verbatim in fetched text, broken links (404/410 only), source over 7 appearances, calendar under 3 events, market indicators unavailable, China & the World missing its Cross-Strait item or spanning one region, Bottom Line outside 55–130 words or missing its `Watch:` line

Health checks (`pipeline_health.py`, never block): model IDs in the known set, tier floors, unique sources ≥20, Google News resolution ≥50 percent, dead feeds (5 empty runs), baseline age (60/120 days), send cadence.

---

## Setup

### Prerequisites
- Python 3.12+, `anthropic>=1.0`
- Anthropic API key
- Gmail account with app password
- GitHub PAT (for the archive commit), optional

### Install
```bash
git clone https://github.com/andysaulim/Daily-China-Digest.git
cd Daily-China-Digest
pip install -r requirements.txt
python smoke_test.py            # offline, no key needed
```

### Environment Variables
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export GMAIL_USER="you@gmail.com"
export GMAIL_APP_PASS="xxxx xxxx xxxx xxxx"
export DIGEST_TO="recipient1@example.com,recipient2@example.com"
export ALERT_TO="operator@example.com"        # failure alerts; defaults to GMAIL_USER
export WEB_URL="https://andysaulim.github.io/Daily-China-Digest"
```

### Run
```bash
python run.py                        # Live: collect -> digest -> validate -> send -> archive
python run.py --send-to you@x.org    # Test: full pipeline, email only you, no state writes
python run.py --dry-run              # Collect + resolve + fetch only (collected.json)
python run.py --from-cache --no-send # Reuse collected.json, render only
python run.py --force-send           # Send despite CRITICAL findings (review digest.html first)
```

---

## Schedule

`.github/workflows/daily-digest.yml` fires six staggered attempts from 6:07 AM ET (10:07 UTC) to 10:17 AM ET. The first that succeeds writes `last_sent.txt`; every later attempt that day is a no-op. A failed or held run emails `ALERT_TO` with the run link and the reason. Manual dispatch offers `mode` = `test` (email to `send_to` only), `live`, or `dry`.

Required secrets: `ANTHROPIC_API_KEY`, `GMAIL_USER`, `GMAIL_APP_PASS`, `DIGEST_TO`. Optional: `ALERT_TO`, `GH_PAT`.

If the repository goes 60 days without a commit, GitHub disables the schedule; the Actions tab shows an "Enable workflow" button. Daily state commits keep it alive.

---

## Project Structure

```
├── run.py                   # Orchestration, post-processing, validation, ledger, metrics
├── collect.py               # 269 feeds, market data, feed-health ledger
├── resolve.py               # Google News redirect -> publisher URL (cached)
├── fulltext.py              # Article-body fetch for the model
├── digest.py                # System/user prompts, Claude call, regeneration
├── render.py                # HTML email (v3.1 Publications register)
├── send_email.py            # Gmail SMTP, BCC
├── pipeline_health.py       # Post-run health checks
├── smoke_test.py            # Offline tests (run before commit; runs in CI)
├── list_sources.py          # Generates SOURCES.md
├── databases.py             # CSIS context hooks (AMTI, Hidden Reach)
├── xi_tracker.py / .json    # Xi appearance persistence
├── xinhua_tracker.py / .json# Propaganda phrase tracking
├── bp_tracker.py / .json    # Monitored locations
├── tension_scorer.py        # Cross-Strait / SCS / US-China tension
├── update_readme.py         # README auto-updater
├── published_ledger.json    # Last 14 days of published items (cross-day dedup)
├── url_cache.json           # Resolved Google News URLs
├── feed_health.json         # Consecutive-empty counts per feed
├── metrics.jsonl            # One record per run (counts, validation, tokens, cost)
├── last_sent.txt            # Once-a-day send marker
├── CLAUDE.md                # Operating notes and failure history
├── SOURCES.md               # Generated feed inventory
└── public/                  # GitHub Pages archive
```

---

*CSIS Korea Chair*

*Prepared by Andy Lim*

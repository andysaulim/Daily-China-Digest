# Daily Intelligence Digest — How It Works

*CSIS Korea Chair · Andy Lim · May 2026*

---

## What Is This?

Two automated daily briefings — one on China, one on Korea — delivered to your inbox at **6:30 AM every morning**, formatted like a professional intelligence digest.

Each email covers overnight news, expert analysis, market indicators, government actions, and satellite imagery flags — across 130+ sources — in roughly a 5-minute read.

No manual curation. No staff time. Runs entirely on its own.

---

## The Basic Idea

Every morning, a small program wakes up on GitHub's servers and does four things:

1. **Reads the news** — scans 130+ RSS feeds from wire services, think tanks, academic journals, and PRC state media simultaneously
2. **Calls Claude** (Anthropic's AI) — sends all those articles to Claude with a detailed set of instructions and asks it to write the digest
3. **Formats the email** — turns Claude's output into a styled HTML email
4. **Sends it** — delivers via Gmail to whoever is on the list

Total cost of running this: about **$2–4 per day** for both digests combined.

---

## What It Covers (China Digest)

| Section | What you get |
|---|---|
| Market strip | SSE Composite, Hang Seng, USD/CNY, Brent, 10Y CGB — with daily moves |
| What changed since yesterday | Key deltas: rates, tariff actions, PLA flights, coast guard activity |
| Morning Memo | Top 3 stories in 2 sentences each — the elevator brief |
| Top Stories | 2–4 major hard news stories with "So what" analysis |
| Overnight Flash | 6 secondary items |
| Expert Analysts | What CSIS, CFR, Brookings, Sinocism, Foreign Affairs published today |
| Satellite & Location Watch | Flags on AMTI gray-zone sites, Hidden Reach overseas footprint |
| PRC Government | State Council, MOFA, MOFCOM, personnel changes |
| US–China Trade | Section 301/232/IEEPA tariff stack, Entity List adds, CFIUS |
| Congressional Watch | Select Committee on CCP, SFRC, USCC activity |
| Business & Economy | Corporate, macro, property, tech |
| Indo-Pacific | Cross-Strait, Japan, Philippines, Australia, India |
| Also Today / The Wire | Everything else worth noting |
| On This Day | A verified historical China event matching today's date |

---

## Source Tiers

| Tier | Count | Examples | Window |
|---|---|---|---|
| **News** | 85+ feeds | Reuters, AP, Bloomberg, NYT, WSJ, FT, Nikkei, SCMP, Xinhua, Global Times | 24 hours |
| **Analysis** | 28 feeds | CSIS, CFR, Brookings, Carnegie, MERICS, RAND, Sinocism, Stimson | 36 hours |
| **Academic** | 16 feeds | International Security, China Quarterly, Journal of Contemporary China | 72 hours |
| **PRC Primary** | 8 feeds | 人民日报, 新华社, 环球时报, CCTV, MOFA Presser, State Council, TAO | 24 hours |

---

## How We Built It

### Tools Used

| Tool | What it does | Cost |
|---|---|---|
| **Python** | The programming language the pipeline is written in | Free |
| **GitHub Actions** | Runs the pipeline on a schedule (like a timer) — no server needed | Free |
| **Claude API (Anthropic)** | AI that reads all the articles and writes the digest | ~$1–2 per run |
| **Gmail SMTP** | Sends the email | Free |
| **GitHub Pages** | Hosts a public archive of past digests | Free |
| **Claude Code** | AI coding assistant used to build and iterate the pipeline | ~$20/month subscription |

### Total Monthly Cost (Both Digests)

| Item | Monthly |
|---|---|
| Claude API (digest generation) | ~$50–80 |
| Claude Code (development tool) | ~$20 |
| Everything else (GitHub, Gmail) | $0 |
| **Total** | **~$70–100/month** |

*Cost per issue: roughly $1–2. The Korea digest is slightly cheaper because it's narrower in scope.*

---

## Replicating for Another Country or Topic

This is the key point: **the hard work is already done.** The pipeline architecture is country-agnostic. Replicating it for, say, a Japan digest or a Southeast Asia digest would take:

- **1–2 days** to swap in the right RSS feeds and update source lists
- **Half a day** to rewrite the Claude prompt with the right analytical frame (e.g., Japan-US alliance dynamics instead of cross-strait tensions)
- **A few hours** to adjust the section structure (drop what doesn't apply, add what does)

### What You'd Change

```
collect.py     →   Swap in Japan/SEA/India RSS feeds
digest.py      →   Rewrite the Claude prompt instructions for the new topic
render.py      →   Update branding, header, section names
send_email.py  →   Update recipients
```

Everything else — the scheduler, email delivery, GitHub archive, validation gates, market strip — stays exactly the same.

### What Would Be Harder

- **Paywalled sources** — WSJ, FT, Bloomberg require subscriptions to read full text. Right now we use RSS headlines + summaries (publicly available), not full articles.
- **Non-English primary sources** — Chinese and Korean sources are handled because Claude reads them natively. Adding Arabic, Russian, or Farsi sources would work similarly, but the RSS feeds need to exist.
- **Highly specialized topics** — The more niche the topic (e.g., specific military procurement), the fewer good RSS feeds exist and the more manual curation the source list needs.

---

## Quality Controls

A few things we built to prevent bad output:

- **Validation gate** — every digest is automatically checked for minimum word count, section completeness, and source diversity before sending
- **No hallucinated links** — the system resolves and verifies every URL before Claude sees it; Claude is instructed to copy URLs verbatim and not construct them
- **Prestige outlet guarantee** — WSJ, NYT, Bloomberg, FT, The Economist stories are never dropped, regardless of AI prioritization
- **Deduplication** — articles appearing in multiple feeds are automatically deduplicated
- **Content filtering** — lifestyle, celebrity, and entertainment content is hard-blocked

---

## What This Is Not

- It does not replace an analyst. It replaces the 90 minutes a morning it takes an analyst to scan news and write a read-ahead.
- It does not have access to classified information, signals intelligence, or subscription databases.
- The "So what" analysis and pattern notes are AI-generated — they are useful prompts for thinking, not finished analytical judgments.

---

## The Korea Digest (Sibling Pipeline)

Identical architecture. Launched first, served as the template for China. Covers:

- Korean Peninsula security (North Korea, US-ROK alliance, USFK)
- ROK domestic politics and economy
- KCNA / Rodong Sinmun state media delta
- Kim Jong Un appearance tracker (with anomaly flag if absent >7 days)
- US-ROK-Japan trilateral tracker

Both digests share the same codebase pattern, email design language, and delivery infrastructure.

---

*Questions? The full code is on GitHub: `github.com/andysaulim/Daily-China-Digest`*

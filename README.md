# China Daily Brief

Automated daily intelligence briefing on the People's Republic of China for the CSIS Korea Chair. Sibling pipeline to [Daily-Korea-Digest](https://github.com/andysaulim/Daily-Korea-Digest). Collects from 130+ sources, generates an analyst-grade digest via Claude, and delivers a styled HTML email at **6:30 AM ET**.

**Live archive:** `andysaulim.github.io/Daily-China-Digest` (planned)

---

## Latest Run

| Metric | Value |
| --- | --- |
| Last generated | Jun 14, 2026 at 8:08 AM ET |
| Digest date | Sunday, June 14, 2026 |
| Articles collected | 88 |
| Unique sources | 10 |
| Top stories | 3 |
| Overnight items | 6 |
| Word count | ~1,154 |
| Xi appeared | No |

## How It Works

```
collect.py          digest.py           render.py          send_email.py
130+ RSS feeds  -->  Claude Sonnet  -->  HTML email  -->  Gmail SMTP
  + market data       (Opus retry)       + archive        + GitHub Pages
  + Xi tracker         + CSIS context     (public/)
  + Xinhua delta        (AMTI, Hidden Reach)
```

1. **Collect** — Scrapes 130+ RSS feeds in parallel across 4 tiers, plus market data (SSE Composite, Hang Seng, USD/CNY, USD/CNH, 10Y CGB, PBOC LPR, Brent)
2. **Enrich** — Fetches CSIS context: AMTI gray-zone tracker, Hidden Reach overseas footprint, China Power Project median-line incursions
3. **Digest** — Claude Sonnet generates the initial briefing; Opus escalates on retry if content minimums aren't met (target 1,200–1,400 words)
4. **Validate** — Pre-send quality gate: word count, source diversity, duplicates, prestige outlet inclusion, data integrity
5. **Render** — JSON to table-based HTML email, v3.1 Publications register typography, optimized for Gmail / Outlook / Apple Mail
6. **Send** — Gmail SMTP with 3x retry, 5s backoff
7. **Archive** — Pushes to GitHub Pages

---

## Source Coverage

| Tier | Sources | Window | Content |
| --- | --- | --- | --- |
| **1 — News** | 85+ feeds | 24h | Wire services, correspondents, PRC English press, regional Asia, government |
| **2 — Analysis** | 28 feeds | 36h | Think tanks (CSIS, Brookings, Carnegie, RAND, CFR, MERICS, ASPI, Sinocism) — A/B/C prestige |
| **3 — Academic** | 16 feeds | 72h | Journals (Int'l Security, China Quarterly, Journal of Contemporary China) — A+/A/B tiers |
| **4 — PRC Primary** | 8 feeds | 24h | Xinhua, People's Daily, Global Times, CCTV, MOFA presser, State Council, TAO |

**Chinese-language sources:** 人民日报 · 新华社 · 环球时报 · 财新 · 第一财经 · 央视新闻. Titles translated in the digest.

**Prestige outlet rule:** China stories from WSJ, NYT, WaPo, Bloomberg, FT, The Economist, CNN, Reuters, CNBC are always included.

---

## Newsletter Sections (19 in delivery order)

| # | Section | Description |
| - | - | - |
| 1 | Header | Date · RE line · editor's note |
| 2 | Market Strip | SSE · Hang Seng · USD/CNY · USD/CNH · 10Y CGB · Brent · PBOC LPR · China 5Y CDS · GDP |
| 3 | Δ Since Yesterday | What moved: rates, tariff actions, sanctions, PLA flights, CCG presence |
| 4 | Morning Memo | Top 3 stories at a glance — elevator brief |
| 5 | Key Stat | Single striking number from today's news |
| 6 | Top Stories | 2–4 biggest hard news stories with "So what" + pattern_note |
| 7 | Overnight Flash | 6 secondary items |
| 8 | Xinhua / People's Daily Delta | **DARK SECTION** — propaganda analysis, Xi appearances, doctrinal language |
| 9 | Expert Analysts | Op-eds + academic — Scott Kennedy, Bonny Lin, Hass, Glaser, Mastro, Bishop |
| 10 | Social Statements | Quotes from Xi, Wang Yi, Li Qiang, MOFA spokespersons, US / Taiwan officials |
| 12 | Satellite & Location Watch | Gray-zone (8 AMTI / China Power) + Hidden Reach (8 CSIS) — only active sites shown |
| 13 | PRC Government | State Council, MOFA, MOD, MOFCOM, PBOC + Personnel Changes + NPC/Politburo + Calendar Watch |
| 14 | US–China Trade & Sanctions | Section 301 / 232 / IEEPA fentanyl / Section 122 / Entity List / SDN / 1260H / OIS / CFIUS |
| 15 | Congressional Watch | Select Committee on the CCP, SFRC, HFAC, USCC, CECC |
| 16 | Business & Economy | Major corporates, M&A, macro indicators, property, tech sector |
| 17 | Indo-Pacific | Cross-Strait, Japan, Philippines, Australia, India, Korea, Vietnam, ASEAN |
| 18 | Also Today / The Wire | Up to 6 third-tier items, 1–2 sentence summaries |
| 19 | On This Day | Verified historical event matching today's exact date |
| 20 | Footer | — |

---

## Monitored Locations

### PLA & Gray-Zone (AMTI / China Power Project)

| # | Location | CSIS product |
| - | - | - |
| 1 | Taiwan Strait Median Line | China Power Project — incursions tracker |
| 2 | Scarborough Shoal | AMTI |
| 3 | Second Thomas Shoal (Ayungin) | AMTI |
| 4 | Sandy Cay | AMTI |
| 5 | Mischief Reef | AMTI |
| 6 | Fiery Cross Reef | AMTI |
| 7 | Subi Reef | AMTI |
| 8 | Senkaku / Diaoyu | AMTI East China Sea |

### Hidden Reach (PRC overseas footprint + dual-use)

| # | Location | Hidden Reach product |
| - | - | - |
| 1 | Chancay, Peru (COSCO) | "No Safe Harbor" — June 2025 LAC ports report |
| 2 | Cuba SIGINT (Bejucal / Wajay) | May 2025 satellite update — antenna array construction |
| 3 | Tier 1 Chinese shipyards | "Ship Wars" / "Murky Waters" — Mar 2025, 307 shipyards dataset |
| 4 | Djibouti PLA Support Base | "Dire Straits" Middle East — Feb 2023 |
| 5 | Khalifa Port, UAE | "Dire Straits" — alleged dual-use military facility |
| 6 | Ream Naval Base, Cambodia | Ongoing Hidden Reach tracking |
| 7 | Hambantota / Bay of Bengal | "Surveying the Seas" — Jan 2024, research vessel mapping |
| 8 | Russian Arctic + Polar Silk Road | "Frozen Frontiers" — Apr 2023 |

---

## Setup

### Prerequisites
- Python 3.12+
- Anthropic API key (Claude Sonnet)
- Gmail account with app password
- GitHub PAT (for Pages deployment)

### Install
```bash
git clone https://github.com/andysaulim/Daily-China-Digest.git
cd Daily-China-Digest
pip install -r requirements.txt
```

### Environment Variables
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export GMAIL_USER="you@gmail.com"
export GMAIL_APP_PASS="xxxx xxxx xxxx xxxx"
export DIGEST_TO="recipient1@example.com,recipient2@example.com"
export GITHUB_TOKEN="ghp_..."
export WEB_URL="https://andysaulim.github.io/Daily-China-Digest"
```

### Run
```bash
python run.py                # Full pipeline: collect -> digest -> render -> send
python run.py --dry-run      # Collection only (outputs collected.json)
python run.py --from-cache   # Skip collection, reuse collected.json
python run.py --no-send      # Generate HTML but don't email
python run.py --no-archive   # Skip writing to public/ archive
python run.py --force-send   # Send even if validation gates fail
```

---

## Schedule

GitHub Actions workflow (`.github/workflows/daily-digest.yml`) runs daily at **6:30 AM ET** with a **7:30 AM ET fallback**. Cron handles both EST and EDT. Manual trigger via `workflow_dispatch`.

Required secrets: `ANTHROPIC_API_KEY`, `GMAIL_USER`, `GMAIL_APP_PASS`, `DIGEST_TO`, `GH_PAT`.

---

## Validation Gates

- **Word count**: Hard minimum 1,000 (target 1,200–1,400)
- **Section minimums**: 2–4 top stories, 6 overnight, 3 morning memo
- **Source diversity**: No single source >3 times in top + overnight
- **Prestige outlets**: WSJ/NYT/WaPo/Bloomberg/FT/Economist/CNN/Reuters/CNBC never dropped
- **Deduplication**: URL-based + headline word-overlap (50% threshold, min 2 words)
- **Content filters**: Lifestyle/celebrity/entertainment hard-blocked
- **Data integrity**: No placeholder URLs, no "None" strings, date matches today

---

## Project Structure

```
├── run.py                   # Entry + validation
├── collect.py               # 130+ RSS feeds, market data, Xi tracker
├── digest.py                # Claude system prompt and generation
├── render.py                # HTML email (v3.1 Publications register)
├── send_email.py            # Gmail SMTP
├── databases.py             # CSIS context (AMTI, Hidden Reach)
├── xi_tracker.py            # Xi Jinping appearance persistence
├── xi_tracker.json          # Appearance history
├── xinhua_tracker.py        # Propaganda rhetoric tracking
├── xinhua_tracker.json      # Rhetoric history
├── bp_tracker.py            # Gray-Zone + Hidden Reach location tracker
├── bp_tracker.json          # Location status history
├── tension_scorer.py        # Cross-Strait / SCS / US-China tension
├── update_readme.py         # README auto-updater
├── build_test_fixture.py    # Test fixture builder
├── requirements.txt
├── .github/workflows/
│   └── daily-digest.yml     # 6:30 AM ET cron
└── public/                  # GitHub Pages archive (generated)
```

---

*CSIS Korea Chair*

*Prepared by Andy Lim*

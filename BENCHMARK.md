# Does the China Daily Brief pass the snuff test?

A comparison of this brief against the China newsletters its readers already
open every morning, written September 4, 2026 as part of the relaunch. The
question is not "is it as good as Sinocism" (Bill Bishop has been doing this
for a decade and reads Chinese all day) but "would a China desk officer,
a Select Committee staffer, or a Beijing bureau chief keep reading it after a
week." The answer today is "yes, if the copy run holds up," with the gaps
listed at the end.

## The benchmarks

| Newsletter | What it does best | Cadence, length | What we borrow |
| --- | --- | --- | --- |
| **Sinocism** (Bill Bishop) | Editorial opener that tells you what matters and why; deep reading of PRC-language sources; "The Essential Eight" ranking | Daily, 4,000+ words | Opener discipline (our RE line + editor's note); PRC-language primary reading (44 ZH feeds, `official_line`); a ranked top tier |
| **Pekingnology** (Zichen Wang) | Full translations of official documents, speeches and think-tank pieces; the Chinese original alongside | Several per week, long | Verbatim quotation with `original_zh`; Chinese think tanks (CICIR, CIIS, SIIS, CISS, RDCY, CCG) as sources, not just objects |
| **Trivium China** | Policy-document tracker: NDRC, MOFCOM, PBOC, State Council notices, with what changed | Daily, ~1,500 words | `prc_government` now asks for the document title and the specific thresholds; ZH government feeds (国务院, 商务部, 央行) |
| **The Wire China** | Investigative business and personnel coverage; data on companies | Weekly | Byline and expert watch-lists; `business_economy` and `personnel_changes` sections |
| **ChinaTalk** (Jordan Schneider) | Tech and semiconductor policy depth; interviews with practitioners | Several per week | Export-control and chip coverage weighting in relevance scoring; ChinaTalk and Sinification as feeds |
| **Politico China Watcher / Axios China** | Washington-side China policy: Congress, agencies, personalities | Weekly / twice weekly | `congressional_watch`, US agency feeds (BIS, OFAC, USTR, Select Committee), `social_statements` for US officials |
| **Bloomberg Next China / WSJ China / FT** | Wire-grade markets and corporates with real numbers | Daily | Prestige-outlet mandatory inclusion; honest market strip; correspondent watch-list |
| **CSIS ChinaPower / AMTI / Interpret: China** | Trackers with primary data (median-line crossings, feature imagery) and translated PRC sources | As published | `monitored_locations`, tracker carry-forward, CSIS product mandatory inclusion |
| **MERICS China Briefing / Sinolytics** | European regulatory and industrial-policy lens | Weekly | MERICS, Sinolytics, EU Chamber, ECFR, SWP, IFRI as feeds |
| **Ginger River / Sinification / China Media Project** | Discourse analysis: what phrases the Party is pushing | Weekly | `xinhua_delta` phrase tracking and the Xinhua rhetoric tracker |

## Where the brief now stands

**Clears the bar**

- **Breadth of collection.** 268 feeds across wires, correspondents, PRC party and state media, financial press, Hong Kong and Taiwan press, US and allied government sites, US, European, Asian and Chinese think tanks, and academic journals. No single benchmark reads this wide; the trade-off is that a model is doing the reading, so grounding matters more.
- **Chinese-language primary reading.** 55 Chinese-language feeds, including the ministries' own sites. The `official_line` section quotes Beijing verbatim with the Chinese original, tone and addressee, which is what Pekingnology and Sinocism readers value and what a wire paraphrase loses.
- **Grounding.** Every article item's URL is checked against the collected corpus in code; unsourced items are deleted, not shipped. Quotes are checked against fetched article text. Market figures that were not collected are shown as unavailable. The benchmarks rely on a human author's integrity; this brief has to rely on gates, and now has them.
- **Trackers with memory.** Xi appearances, Xinhua phrase counts, sixteen monitored sites, a 14-day published ledger, and a calendar that expires. The benchmarks carry this in the author's head.
- **Length and structure.** 2,000 to 3,000 words in twenty sections with a scannable memo, top stories with "so what", and the official line before the reactions to it. Comparable to Sinocism's daily in scope; shorter than its full read.
- **Reliability engineering.** Six staggered sends, once-a-day guard, failure alerts, fail-closed validation, offline test suite, health checks, cost per run. None of the benchmarks publish this, and none of the sibling briefs had it in June.

**Does not yet clear the bar**

1. **Editorial voice.** Sinocism's first three paragraphs are judgment; ours are facts. The prompt forbids editorializing by design (the audience is expert). The RE line and editor's note are the only place a reader gets a frame. Worth testing a 120-word "Read this first" paragraph that connects the day's items, sourced to them, without opinion.
2. **Documents.** Trivium and Pekingnology link and summarise the notice itself. We ask for the document title in `prc_government` and collect the ministry sites, but a scraped RSS blurb is not the document. Next step: fetch the notice page (fulltext already does this for resolved URLs) and add a `documents_today` section with title, issuing body, effective date and a two-sentence summary.
3. **Depth on the top story.** A Bishop or Wire lead runs 400 words with history. Ours is capped at three sentences plus a "so what" and a pattern note. The cap protects against invention; with article text now in the prompt it can be relaxed to five sentences for the lead story only.
4. **Human review before send.** Every benchmark has an author who reads it before it goes out. This brief sends unattended at 6 AM. The validator and the BCC test mode reduce the risk; they do not replace a five-minute read. A "hold for review" mode (render, email the operator, send to the list on a reply or a second dispatch) is a small addition to the workflow.
5. **Verified baselines.** The leaders, tariff stack and calendar blocks were last hand-verified in May 2026. The prompt is told they are stale and the health check nags at 60 and 120 days, but only a person can update them.
6. **Weekly synthesis.** Korea and Australia have a Friday week-in-review; this brief does not yet.

## Expert and think-tank roster

**US-based.** CSIS (Trustee Chair, ChinaPower, AMTI, Hidden Reach, Interpret: China), Brookings, Carnegie, CFR, RAND, Atlantic Council, Hoover (China Leadership Monitor), Asia Society Center for China Analysis, NBR, Wilson Center Kissinger Institute, Harvard Fairbank and Belfer, Stanford FSI, UCSD 21st Century China Center, Georgetown Initiative for US-China Dialogue, CNAS, CSBA, FDD, Cato, Quincy, AEI, Hudson, Heritage, PIIE, Rhodium, Paulson Institute, USCBC, AmCham China, GMF, USIP, Stimson, CRS, GAO, Jamestown, MERICS (Berlin), Chatham House, ECFR, IFRI, SWP, RUSI, EU Chamber, ASPI and the Strategist, Lowy and the Interpreter, ORF, Takshashila, JIIA, ISDP, Sinolytics, Gavekal.

**China-based.** CICIR (中国现代国际关系研究院), CIIS (中国国际问题研究院), SIIS (上海国际问题研究院), Tsinghua CISS (清华战略与安全研究中心), Renmin Chongyang (人大重阳), CCG (全球化智库), Fudan Center for American Studies (复旦美国研究中心), PKU IISS (北大国际战略研究院), Pangoal (盘古智库), Taihe (太和智库), CASS (中国社科院), China-US Focus, CGTN Think Tank.

**Named experts (189).** The full watch-list is in `collect.py` (`EXPERT_WATCHLIST`) and in `SOURCES.md`. It runs from Scott Kennedy, Bonny Lin, Jude Blanchette and Ryan Hass through Susan Shirk, Evan Medeiros, Taylor Fravel, Oriana Mastro, Elizabeth Economy and Rush Doshi to Wang Jisi, Jia Qingguo, Yan Xuetong, Wu Xinbo, Da Wei, Zhou Bo and Hu Xijin, with the Chinese names included so ZH press quoting them is caught. An item that carries one of these names is ranked up and the prompt is told to name the author or the quoted expert.

## Verdict

On sourcing the brief is now wider than any single benchmark and reads the PRC-language primary record, which most English newsletters do not. On grounding it is more defensible than a human newsletter because every claim has a machine-checked source. Where it still trails is the two things a human author brings: a point of view in the opener, and a last read before send. Both are tractable and neither should hold up the relaunch.

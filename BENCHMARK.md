# Format: what the best briefs do, and what this one now does

Written September 4, 2026, during the relaunch, to answer a direct question:
is this the best format, and how does it compare to Politico, China Watcher
and Bloomberg? Short answer: the structure was sound and the length was wrong.
The brief targets **2,000-2,500 words**, the
frame has been moved to the top, and the market data has been moved off the
first screen.

## The two kinds of digest

Every serious morning product is one of two things, and the failure mode is
trying to be both.

**The read.** Axios China, Politico's Playbook and China Watcher, Bloomberg's
Next China and Five Things, the Economist's Espresso. Roughly 800 to 2,000
words. It has a lead, it has a bottom, and the reader finishes it. Its promise
is *you are caught up*.

**The reference.** Sinocism, at 4,000-plus words. Nobody reads it start to
finish; they skim the headers and search it later. Its promise is *nothing
important is missing*.

This brief was drifting into the second category while being formatted as the
first: twenty sections, 2,833 words and 80 KB in the first relaunch issue, with
no lead paragraph and a nine-tile market strip above the news. That is the
worst of both. A reference document that opens like a newsletter gets abandoned
in week two.

## What the benchmarks actually do

| Product | Shape | Typical length | The device worth stealing |
| --- | --- | --- | --- |
| **Axios China** | 1 big thing, then short items, every item with a "why it matters" line | ~800-1,200 words | The bolded one-line stake under each item. We have `so_what`; it now has to earn its place on every top story. |
| **Politico China Watcher** | One reported lead with a named byline, then the week ahead, then short hits | ~1,500-2,000 words | The lead IS the product. A brief with no author's frame reads like a feed. |
| **Politico Playbook** | Driving the day, then tightly bolded scannable blocks | ~2,000+ words | Scannability through typography, not through length. |
| **Bloomberg Next China / Five Things** | An opening take, then five or six bullets, usually one chart | ~800-1,000 words | Ruthless item count. Five things, not eighteen. |
| **Economist Espresso** | Five items, ~100 words each | ~500 words | A hard stop. The product is defined by what it excludes. |
| **Sinocism** | Ranked link digest with commentary, deep PRC-language reading | 4,000+ words | PRC-language primary sources, and a ranked top tier. Not the length. |
| **Trivium China** | Policy-document tracker: what the ministry actually issued | ~1,500 words | Name the document, the effective date and the threshold. |
| **Pekingnology** | Full translations, Chinese original alongside | Long, irregular | Verbatim quotation with the original text. This is the model for `official_line`. |

The pattern across the ones people stay subscribed to: **one frame at the top,
a small number of items, a hard stop.** None of them lead with a data strip.

## What changed

1. **Length: 2,000-2,500 words**, hard floor 1,600, ceiling 2,700. An eight to
   seven minute read. The prompt now says selection is the product and tells
   the model to cut from `also_today` and `overnight_items` first, never from
   the top stories or Beijing's own words.
2. **The Bottom Line now renders.** `editor_note` was being generated, counted
   in the word total, and silently dropped by the renderer on every run since
   May. The reader got twenty sections of facts and no lead. It now sits
   directly under the header in its own block, 45-70 words, connecting the
   day's items and naming the specific thing that moved. This is the Axios "1
   big thing" and the Politico lead, and it was already being paid for.
3. **Market data moved below the news.** The nine-tile strip and the delta bar
   were the first thing on the screen. They now render after the top stories
   and overnight items. News before numbers.
4. **Item counts cut:** top stories 3-4 (was 3-5), overnight 5-7 (was 6-8),
   also_today 6 one-line items (was 8 summaries), official_line 4-6 (was
   5-10), opeds 4-6 (was 6-12), business 3-5, Indo-Pacific 4-6.
5. **A Gmail clipping guard.** Gmail truncates a message body over 102 KB and
   shows "[Message clipped]". The relaunch issue was at 79,924 bytes, and
   Chinese characters cost three bytes each in `official_line`. The pipeline
   now measures encoded bytes after rendering, warns at 78 KB and blocks the
   send at 96 KB, because a brief that Gmail cuts off mid-item is a broken
   brief. This was a live risk nobody was watching.

## Where this brief wins

- **Beijing's own words.** `official_line` quotes MOFA, TAO, MND, MOFCOM, the
  State Council and the PBOC verbatim, in Chinese, with tone and addressee.
  No English-language daily carries this. It is the single best reason to open
  the brief, which is why it keeps its space when the length is cut.
- **Breadth with grounding.** 269 feeds, 56 Chinese-language. Every article
  item's URL is checked against the collected corpus in code and deleted if it
  is not there; quotes are checked against fetched article text; market figures
  that were not collected show a dash. The human-authored benchmarks rely on
  the author's integrity. This one relies on gates, and now has them.
- **Memory.** Xi appearances, Xinhua phrase counts, sixteen monitored sites, a
  14-day published ledger that stops a story running twice, a calendar that
  expires. The benchmarks carry this in the author's head.
- **It does not break.** Six staggered sends, a once-a-day guard, failure
  alerts, fail-closed validation, 481 offline tests, health checks and a cost
  line per run.

## Where it still trails

1. **No reported lead.** China Watcher's lead is an interview or a scoop. The
   Bottom Line can only connect items that already exist in the feed. That gap
   closes with a human, not with a prompt.
2. **Documents, not document summaries.** Trivium links the notice itself. We
   collect the ministry sites and ask for the document title, but an RSS blurb
   is not the document. Next: fetch the notice page and add a `documents_today`
   block with issuing body, effective date and thresholds.
3. **No human read before send.** Every benchmark has an author who reads it.
   This sends unattended at 6 AM. A hold-for-review mode is a small change to
   the workflow and probably worth it for the first month.
4. **Stale baselines.** Leaders, tariff stack and calendar were hand-verified
   on May 20, 2026. The prompt is told they are stale and the health check
   nags at 60 and 120 days, but only a person can refresh them.
5. **No weekly synthesis.** Korea and Australia have a Friday week-in-review.

## Roster

**US.** CSIS (Trustee Chair, ChinaPower, AMTI, Hidden Reach, Interpret: China),
Brookings, Carnegie, CFR, RAND, Atlantic Council, Hoover, Asia Society CCA,
NBR, Wilson Kissinger Institute, Harvard Fairbank and Belfer, Stanford FSI,
UCSD 21st Century China Center, Georgetown, CNAS, CSBA, FDD, Cato, Quincy,
AEI, Hudson, Heritage, PIIE, Rhodium, Paulson, USCBC, AmCham China, GMF, USIP,
Stimson, CRS, GAO, Jamestown.

**Allied.** MERICS, Chatham House, ECFR, IFRI, SWP, RUSI, EU Chamber, ASPI and
the Strategist, Lowy and the Interpreter, ORF, Takshashila, JIIA, ISDP,
Sinolytics, Gavekal.

**China-based.** CICIR (中国现代国际关系研究院), CIIS (中国国际问题研究院),
SIIS (上海国际问题研究院), Tsinghua CISS (清华战略与安全研究中心), Renmin
Chongyang (人大重阳), CCG (全球化智库), Fudan Center for American Studies
(复旦美国研究中心), PKU IISS (北大国际战略研究院), Pangoal (盘古智库), Taihe
(太和智库), CASS (中国社科院), China-US Focus, CGTN Think Tank.

**189 named experts** in `EXPERT_WATCHLIST`, from Scott Kennedy, Bonny Lin,
Jude Blanchette and Ryan Hass through Susan Shirk, Evan Medeiros, Taylor
Fravel, Oriana Mastro and Rush Doshi to Wang Jisi, Jia Qingguo, Yan Xuetong,
Wu Xinbo, Da Wei, Zhou Bo and Hu Xijin, Chinese names included so ZH press
quoting them is caught. A flagged item is ranked up and the author is named.

## Verdict

On sourcing, the brief now reads wider than any single benchmark and reads the
PRC-language primary record, which most English products do not. On grounding
it is more defensible than a human newsletter, because every claim is checked
against a collected source. At 2,000-2,500 words with a lead at the top it is
now shaped like the products people actually finish rather than the one they
archive. What it still lacks is the thing only a person supplies: a reported
lead, and a last read before it goes out.

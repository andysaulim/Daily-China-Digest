"""
China Daily Brief — Digest Generator
Sends collected articles to Claude and returns a structured digest JSON.
"""
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import anthropic


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are the senior intelligence analyst producing the China Daily Brief for the CSIS Korea Chair — a daily Presidential Daily Brief-style product read by top government officials, leading China scholars, senior policymakers, and elite journalists.

Your readers include: Victor Cha (CSIS Korea Chair), Scott Kennedy (CSIS Trustee Chair), Bonny Lin (China Power Project), senior NSC staff, State Department China desk officers, Pentagon Asia policy officials, House Select Committee on the CCP staff, leading academics (Stanford, Harvard, Georgetown, MIT China programs), top correspondents (WSJ, NYT, WaPo, FT Beijing bureaus), Taiwan officials, allied government analysts (Japan, Australia, Philippines, India), and Treasury / Commerce sanctions practitioners.

YOUR AUDIENCE IS EXPERT. They do not need your opinion — they need facts, data, and connective context to form their own. Your job is to save them time, surface what they might miss, and connect data points across sources. Do NOT editorialize. Do NOT tell the reader what to think. Do NOT use phrases like "this is significant", "notably", "importantly", or "this matters because." Present the facts and let the expert draw conclusions.

YOUR JOB: Process all incoming China-related content and produce a single structured JSON briefing package. Write like an intelligence analyst producing raw intelligence summaries — precise, factual, sourced. Add value through: (1) connecting data points across sources the reader hasn't seen together, (2) providing specific historical precedents with dates, (3) flagging what changed vs. yesterday's baseline.

GROUNDING — ZERO HALLUCINATION RULE (CRITICAL):

You are writing an intelligence product. Getting a name, title, date, or fact wrong destroys credibility. One wrong name and the reader stops trusting every fact in the digest.

SOURCE-OR-SKIP PRINCIPLE: For EVERY factual claim you write, you must be able to point to either (a) a source article in this batch, or (b) a reference baseline provided in this prompt. If a fact comes from neither, DO NOT INCLUDE IT. An omission is always better than an invention.

- ONLY use names, titles, figures, and claims that appear explicitly in the source articles provided. If an article says "the foreign minister" without naming them, use "the foreign minister" — do NOT fill in a name from your training data.

- NEVER substitute a name from your memory when the source text is ambiguous. Your training data may be outdated — leaders change, officials rotate, titles shift. The source article is ground truth.

- If two sources conflict on a fact, note both. If a source is vague, stay vague. Precision means knowing what you DON'T know.

- Cross-check: before writing any person's name + title, verify that BOTH the name AND the title appear together in at least one source article in this batch. If not, do not assert the pairing.

- HISTORICAL CLAIMS: Do NOT cite specific historical dates or precedents from memory. pattern_note and analyst_note fields should ONLY reference precedents that are mentioned in today's source articles or the reference baselines provided in this prompt. If no relevant precedent appears in the provided data, set the field to null rather than inventing one. A wrong date is worse than no date.

- FACILITY STATUS: For monitored_locations, if today's articles contain a new report about a facility (satellite imagery, AMTI / Hidden Reach analysis, news article), update that facility's status and note from the article. If no article mentions a facility today, CARRY FORWARD the last known status and note from the LOCATIONS HISTORY tracker — do NOT blank it to "No new reporting". The tracker preserves context from prior reports so readers always see the most recent known status. Only set note to "No new reporting" if a facility has NEVER had a report in the tracker history.

- OMISSIONS & STREAKS: Do NOT claim "X absent for N days" or "no mention of Y for N days" unless the XINHUA RHETORIC HISTORY tracker data provided in this prompt supports the specific count. If no tracker history is available, do not fabricate streak counts.

- ARITHMETIC & TOTALS: When this prompt provides a PRE-CALCULATED total, percentage, or sum, use it EXACTLY as given. Do NOT recalculate — LLMs make arithmetic errors. Only adjust a pre-calculated value if today's articles introduce a NEW data point not already in the baseline.

- DATES: For calendar_watch and on_this_day, only use dates that appear in (a) today's source articles, (b) the VERIFIED CHINA DATES list, or (c) the baseline references in this prompt. Do NOT generate dates from memory.

- EVERY ARTICLE MUST EXIST IN THE INPUT: Every item in top_stories, overnight_items, also_today, opeds_today, business_economy, indo_pacific, and social_statements MUST correspond to an actual article from the input data above — with a real URL from that input. Do NOT generate articles from your training data. Do NOT present old events as today's news. Do NOT fabricate generic think tank analyses when no such article exists in today's feed. If a section has fewer qualifying articles than its target count, return fewer items or an empty array. An empty section is ALWAYS better than a fabricated entry.

- THINK TANK FABRICATION — HARD BLOCK: You have a strong tendency to fabricate generic-sounding think tank articles from CSIS, CFR, Brookings, Carnegie, RAND, MERICS, etc. when the feed is thin. These fabrications follow a telltale pattern: vague titles ("examines evolving security environment", "argues for export control modernization", "analyzes expanding dimensions"), no specific data points, and no real URL. STOP. If a think tank article does not appear in the input data with a real URL, it does not exist. Do NOT create it.

- ACADEMIC FABRICATION — HARD BLOCK: Same rule applies to academic_today. Do NOT include any journal article that does not appear in the Tier 3 input with a real URL. The authors field must come from the article metadata — do NOT populate it from training data or invent it. If the authors field is missing from the source, set it to null. A news outlet name (e.g. "Ratopati", "The Hindu") appearing as "author" means the source is a news article, not a journal paper — exclude it entirely from academic_today.

- URL INTEGRITY — ZERO TOLERANCE: Every url field must be copied CHARACTER-FOR-CHARACTER from the input article's url field. Do NOT reconstruct, guess, shorten, or invent URLs. Do NOT write a URL based on knowing the publication's domain — only use the exact URL from the input. If an article in the input has no URL or an empty URL, set the url field to "" in your output. A missing URL is always better than a fabricated one.

QUALITY STANDARD — THE EXPERT TEST: Every entry must pass these tests:

1. FACTUAL — Does this state what happened with specifics (who, what, when, numbers)?
2. CONNECTIVE — Does this link to a pattern, precedent, or upcoming event with a specific date?
3. PRECISE — Are claims sourced, numbers specific, and attributions clear?
4. NON-OBVIOUS — Would the reader get this from the headline alone? If yes, rewrite.

Do not add commentary that an expert would find patronizing. An empty section is better than filler.

CSIS CHINA COVERAGE — INSTITUTIONAL CONTEXT:

The CSIS China coverage spans multiple programs: ChinaPower Project (Bonny Lin) — PLA modernization, Cross-Strait, Taiwan Strait incursions; Trustee Chair (Scott Kennedy) — economic policy, trade, semiconductors; Asia Maritime Transparency Initiative (AMTI, Greg Poling) — South China Sea, East China Sea features; Hidden Reach — PRC overseas infrastructure footprint, dual-use facilities, ports, shipyards, SIGINT.

GRAY-ZONE MONITORED LOCATIONS (AMTI / China Power): Taiwan Strait Median Line, Scarborough Shoal, Second Thomas Shoal (Ayungin), Sandy Cay, Mischief Reef, Fiery Cross Reef, Subi Reef, Senkaku/Diaoyu.

HIDDEN REACH MONITORED LOCATIONS: Chancay (Peru, COSCO), Cuba SIGINT (Bejucal/Wajay), Tier 1 Chinese shipyards (Jiangnan/Hudong-Zhonghua/Dalian), Djibouti PLA Support Base, Khalifa Port (UAE), Ream Naval Base (Cambodia), Hambantota/Bay of Bengal, Russian Arctic/Polar Silk Road.

CROSS-STRAIT AS SPINE: Cross-Strait is the central axis of China policy analysis. Almost every other story (US-China, Japan-China, Philippines-China, Australia-AUKUS, India-China) routes back to it. When a story has Taiwan implications, surface them.

PRESTIGE OUTLET RULE — MANDATORY INCLUSION: If ANY China-related article appears from WSJ, Washington Post, NYT, Bloomberg, Financial Times, The Economist, CNN, Reuters, or CNBC, it MUST be included in the digest — in top_stories if it's a major story, otherwise in overnight_items or also_today. These outlets assign China stories selectively; when they publish on China it is inherently noteworthy. Never drop a China story from these outlets.

CSIS PRODUCTS — MANDATORY INCLUSION: If ANY same-day article appears from CSIS Trustee Chair, ChinaPower, AMTI, or Hidden Reach, it MUST appear in opeds_today or also_today. These are the in-house products of the institution publishing this digest; they must surface.

JOURNALIST FLAGGING: The following reporters have special China expertise. When their bylines appear, treat the story as higher priority and note the journalist in your analysis:

- Lingling Wei (WSJ Beijing chief)
- Joe Leahy, Cheng Leng, Wenjie Ding (FT Beijing)
- Keith Bradsher, Vivian Wang, David Pierson, Olivia Wang (NYT Beijing)
- Lily Kuo, Christian Shepherd, Eva Dou (WaPo Beijing)
- Brenda Goh, Yew Lun Tian, Laurie Chen (Reuters Beijing)
- Stephen McDonell (BBC Beijing)
- Stella Yifan Xie, Rebecca Feng, Liyan Qi (WSJ China)
- Tom Hancock, Sarah Zheng (Bloomberg)
- Bill Bishop (Sinocism — independent)
- James Kynge, Sun Yu (FT China business)
- Yoko Kubota (WSJ tech)
- Helen Davidson (Guardian Taipei)
- William Yang (DW Taipei)

VOICE — ECONOMIST-STYLE, FACTS FIRST:

Write like a senior Economist correspondent: crisp, declarative, no throat-clearing. Every sentence earns its place. Lead with the verb. Never start with "In a move that..." or "According to..." — state what happened.

- Summaries: state the facts — who did what, when, with what numbers. Then add ONE beat of context the reader can't see from the headline (a connection, a precedent, a date)
- Do NOT interpret for the reader. Do NOT say "this suggests X" or "this could mean Y." State the facts and the precedent; the expert reader draws the inference
- Do NOT use hedging phrases: "notably", "importantly", "significantly", "it is worth noting", "interestingly"
- Do NOT start sentences with "This comes as...", "The move comes amid...", "This is significant because..."
- Prefer active voice
- "So what" blocks: name the specific decision, meeting, or timeline this affects. One sentence, no editorializing
- Pattern blocks: cite specific historical precedents with exact dates. No interpretation

BREVITY: Body text: 2-3 sentences max — lead with the specific, add one beat of context. "So what": 1 sentence. Pattern notes: 1 sentence with dates. Academic summaries: 3 sentences. Cut all filler.

PRC GOVERNMENT MONITORING: Track activity from these institutions and report any meetings, statements, press briefings, policy announcements, or personnel changes:

- State Council (Premier Li Qiang) — economic and social policy
- MOFA (FM Wang Yi + spokespersons Mao Ning, Lin Jian) — diplomatic posture, daily presser
- MOD (Defense Minister Dong Jun) — military signaling, PLA activity
- MOFCOM — trade actions, export controls, AD/CVD investigations
- PBOC — monetary policy, FX intervention, capital controls
- NDRC — industrial policy, FAI direction, project approvals
- MSS — state security signals (rare public, but watch for arrests, espionage cases)
- SAFE — foreign exchange administration, capital flow controls
- CSRC — securities regulation, IPO approvals
- Customs (海关) — trade data, sanctions enforcement
- Taiwan Affairs Office (TAO) — cross-strait statements
- NPC Standing Committee — legislative actions

Include only substantive actions (not routine admin). Each entry: ministry, action (1-line headline), detail (1-2 sentences), source URL.

FORMATTING: Do NOT use emojis anywhere in the output. Plain text only.

DEDUPLICATION — CRITICAL (ZERO TOLERANCE):

- ONE TOPIC = ONE ENTRY across the ENTIRE digest. Before placing ANY item, ask: "Is this the same underlying event, decision, or announcement as something already placed?" If yes, DO NOT include it — regardless of source, angle, or section.

- Common duplicates to watch for:
  * "PBOC holds rates" / "Central bank keeps LPR steady" / "China keeps benchmark rate" — ONE entry
  * "Xi meets foreign leader" / "Beijing summit" / "Xi-X bilateral" — ONE entry
  * "BYD Q1 earnings" / "BYD profit rises" / "BYD EV sales up" — ONE entry
  * "PLA crosses median line" / "Taiwan reports PLAAF sorties" — ONE entry
  * Any wire story (Reuters/AP/AFP) picked up by other outlets — same story, ONE entry

- Pick the BEST source for each topic and place it in the HIGHEST appropriate section.

- SAME POLICY across sections: If a tariff rate is mentioned in tariff_tracker, do NOT repeat in trade_policy. Tariff rates belong ONLY in tariff_tracker. Section 301 investigations, export controls, CFIUS reviews belong ONLY in trade_policy.

- LIFESTYLE / ENTERTAINMENT — HARD BLOCK: NEVER include celebrity, lifestyle, fashion, entertainment, or cultural-only content in any section. This newsletter covers geopolitics, trade policy, technology, security, and foreign affairs ONLY. Cultural content qualifies ONLY if it has clear policy or security implications (e.g. Hollywood-China censorship, TikTok divestiture).

- CATEGORIES: Valid categories for top_stories are: Cross-Strait, US-China, PRC-Economy, PLA, Indo-Pacific, Technology, Sanctions, Energy, Diplomacy.

Return ONLY valid JSON. No markdown, no preamble, no commentary outside the JSON structure."""


# ─────────────────────────────────────────────────────────────────────────────
# REFERENCE BASELINES
# ─────────────────────────────────────────────────────────────────────────────

_POLITICAL_LEADERS = """\
CURRENT POLITICAL LEADERS — REFERENCE (update from today's articles if changed):

PRC TOP LEADERSHIP (as of early 2026):
- CCP General Secretary, President, CMC Chairman: Xi Jinping (习近平) — since 2012
- Premier of State Council: Li Qiang (李强) — since March 2023
- NPC Standing Committee Chairman: Zhao Leji (赵乐际)
- CPPCC Chairman: Wang Huning (王沪宁) — top political theorist
- Top Five / Party affairs: Cai Qi (蔡奇)
- First-Ranked Vice Premier: Ding Xuexiang (丁薛祥)
- Vice Premier (US-China econ point person, CFEAC Director): He Lifeng (何立峰)
- Foreign Minister, Politburo, CFAC Office Director: Wang Yi (王毅)
- Defense Minister: Dong Jun (董军)
- CMC Vice Chairmen: Zhang Youxia (张又侠), He Weidong (何卫东) — verify He Weidong status, was under investigation in 2024-2025
- MSS Minister: Chen Yixin (陈一新) — verify, may have rotated
- International Department head: Liu Jianchao (刘建超) — sometimes mentioned as potential FM successor

MOFA SPOKESPERSONS (rotating, verify from today's articles):
- Mao Ning (毛宁)
- Lin Jian (林剑)
- Wang Wenbin (汪文斌) — verify current rotation status

TAIWAN LEADERSHIP:
- President: Lai Ching-te (賴清德) — DPP, inaugurated May 20 2024
- Vice President: Hsiao Bi-khim (蕭美琴)
- Foreign Minister: Lin Chia-lung (林佳龍)
- Defense Minister: Wellington Koo (顧立雄)
- NSC Secretary-General: Joseph Wu (吳釗燮) — was previously FM
- Premier: Cho Jung-tai (卓榮泰)
- MAC Chairman: Chiu Chui-cheng (邱垂正)

US LEADERSHIP (Trump 2nd term, inaugurated Jan 2025):
- President: Donald Trump
- Vice President: JD Vance
- SecState: Marco Rubio
- SecDef: Pete Hegseth
- Treasury Sec: Scott Bessent
- Commerce Sec: Howard Lutnick
- USTR: Jamieson Greer
- NSA: Mike Waltz
- DNI: Tulsi Gabbard
- INDOPACOM Commander: verify current — was Adm. Samuel Paparo

KEY US CONGRESSIONAL FIGURES on China:
- House Select Committee on the CCP: Chair John Moolenaar (R-MI), Ranking Raja Krishnamoorthi (D-IL)
- Senate Foreign Relations: Chair Jim Risch (R-ID), Ranking Jeanne Shaheen (D-NH)
- House Foreign Affairs: Chair Brian Mast (R-FL)
- CECC: Co-Chairs Chris Smith (R-NJ) + Jeff Merkley (D-OR)
- USCC Chair: verify current

If today's articles name a different officeholder for any position, USE THE NAME FROM THE ARTICLE."""


_TRADE_BASELINES = """\
BASELINE TRADE & SANCTIONS POLICY (as of early 2026 — carry forward unless today's articles report a change):

US-CHINA TARIFF STACK — current rates applied to Chinese goods (different products subject to different combinations):

SECTION 301 (Trump 2018, expanded Biden 2024, expanded again Trump 2.0):
- List 1 (industrial intermediates, $34B trade): 25%, ACTIVE since Jul 2018
- List 2 (industrial inputs, $16B): 25%, ACTIVE since Aug 2018
- List 3 ($200B, broad consumer/industrial): 25%, ACTIVE since 2018-2019
- List 4A (consumer goods, $300B): 7.5%, ACTIVE
- Biden 2024 additions: EVs raised to 100%, lithium batteries 25%, semiconductors 50%, solar cells 50%, syringes/needles 50%, steel/aluminum tied to Section 232
- Trump 2.0 additions (2025-2026): track from today's articles

SECTION 232 — applies to all countries including China:
- Steel & Aluminum: 50% universal, ACTIVE since Mar 2025 (all country exemptions eliminated)
- Copper: 50%, ACTIVE since Mar 2025
- Automobiles: 25%, ACTIVE
- Semiconductors (narrow): 25%, ACTIVE since Jan 15 2026

IEEPA FENTANYL TARIFF — China-specific:
- 20% across-the-board on Chinese-origin goods, layered on top of other duties
- Justification: fentanyl precursor exports
- ACTIVE — Trump executive order

IEEPA RECIPROCAL TARIFFS — STATUS: STRUCK DOWN:
- Feb 20 2026: Supreme Court struck down all IEEPA tariffs (6-3 ruling)
- White House immediately imposed 10% Section 122 surcharge on ALL countries (effective Feb 24 2026, expires Jul 24 2026 unless Congress extends)
- USTR launched Section 301 investigations Mar 11 2026 against 16 trading partners as potential replacement legal basis

SECTION 122 SURCHARGE:
- 10% global surcharge, effective Feb 24 2026, expires Jul 24 2026 (150-day statutory limit)
- Applies to China same as all other countries

BIS EXPORT CONTROLS:
- Entity List: 600+ Chinese entities (verify count from today's articles)
- Advanced semiconductor rules: Oct 2022 + Oct 2023 + Dec 2024 expansions covering AI chips, HBM, advanced manufacturing equipment, EUV-relevant
- Validated End User (VEU) status: most major Chinese fabs lost VEU status; operating on annual licenses with restrictive conditions
- Connected Vehicles Rule (Commerce, Jan 2025): bans certain Chinese-origin hardware/software in US vehicles

OFAC SDN PROGRAM:
- Running designations on Chinese entities/individuals (Xinjiang, Hong Kong, Russia-related, narcotics, cyber, NPWMD)
- Track 7-day adds from today's articles

DOD SECTION 1260H "CHINESE MILITARY COMPANIES" LIST:
- Annual list of Chinese companies with PLA ties, restricts DoD procurement
- Notable adds: SMIC, CATL, Tencent
- Track today's articles for new adds/removals

CFIUS:
- Reviews of inbound Chinese investment in US tech, real estate, critical infrastructure
- Recent divestiture orders: track from today's articles

OUTBOUND INVESTMENT SCREENING (Treasury):
- EO 14105 (Sept 2023, implemented Jan 2025): restricts US investment in PRC semiconductors, quantum, AI
- Program activity: track notifications and prohibited transactions

ICTS RULE (Commerce):
- Information and Communications Technology Services rule — covers connected vehicles, drones, smart devices

USE THESE BASELINES EXACTLY unless today's articles report a NEW policy action or status change. Do NOT invent trade policy items from memory.

CRITICAL ACCURACY NOTE — Section 301 vs IEEPA vs Section 232: These are DIFFERENT statutory authorities with DIFFERENT scope:
(1) Section 301: targeted tariffs on Chinese goods only, USTR-administered, justified by "unfair trade practices"
(2) IEEPA: presidential national-emergency tariffs, can apply globally (e.g. fentanyl on China specifically) or reciprocally
(3) Section 232: national security tariffs on specific products (steel, aluminum, autos, semiconductors), apply globally
(4) Section 122: temporary global surcharge, 150-day limit
Do NOT conflate. Stack rates ADDITIVELY when discussing total tariff burden on a specific product."""


_KEY_DATES = """\
VERIFIED CHINA DATES (use ONLY these for on_this_day unless today's articles contain a sourced historical reference):

Jan 1 1979: US-PRC diplomatic recognition (Carter administration)
Jan 13 2024: Lai Ching-te elected Taiwan President (DPP third consecutive term)
Feb 21 1972: Nixon-Mao meeting, Beijing — start of US-PRC opening
Feb 28 1947: Taiwan 2-28 Incident (KMT massacre, foundational to Taiwanese identity)
Mar 5 1953: Stalin death (Sino-Soviet relations turning point)
Apr 1 2001: EP-3 incident (US Navy EP-3E vs PLAAF J-8 collision over Hainan)
Apr 12 1979: Taiwan Relations Act signed
May 7 1999: NATO bombing of Chinese embassy in Belgrade
Jun 4 1989: Tiananmen Square crackdown
Jul 1 1921: CCP founding (claimed date)
Jul 1 1997: Hong Kong handover from UK to PRC
Jul 12 2016: SCS Arbitration ruling against China (PCA, Philippines case)
Aug 8 2008: Beijing Olympics opening
Sep 18 1931: Mukden Incident (Japan invades Manchuria)
Sep 21 2021: Xi launches Global Development Initiative
Sep 30 2017: Solomon Islands switches recognition from Taiwan to PRC
Oct 1 1949: PRC founding
Oct 25 1971: UN General Assembly Resolution 2758 (PRC seat replaces ROC)
Nov 12 2014: Xi-Obama Beijing summit, US-China climate agreement
Dec 11 2001: China accedes to WTO
Dec 13 1937: Nanjing Massacre begins
Dec 26 1893: Mao Zedong birth (CCP holiday context)
Mar 4 1979: Sino-Vietnamese War begins
Aug 17 1982: US-PRC Joint Communique on Taiwan arms sales
Jan 30 1979: Deng Xiaoping US visit (post-recognition)"""


_VERIFIED_UPCOMING = """\
VERIFIED UPCOMING DATES (use these + any dated events from today's articles):

May 14-15 2026: Trump-Xi summit in Beijing — rescheduled from March. Major US-China bilateral.
May 20-23 2026: APEC Ministers Responsible for Trade Meeting (MRT) — Suzhou, China.
May 20 2026: Lai Ching-te's 2-year anniversary in office (Taiwan).
Jun 4 2026: Tiananmen 37th anniversary — sensitive date, watch for censorship spikes and dissident commemorations abroad.
Jul 1 2026: Hong Kong handover 29th anniversary; CCP founding 105th anniversary.
Jul 12 2026: SCS Arbitration ruling 10th anniversary — Philippines marks the date.
Jul 24 2026: Section 122 surcharge expiry — 150-day statutory limit; Congress must extend or surcharge lapses.
Aug 1 2026: PLA founding anniversary (建军节) — typically accompanied by military parades and Xi appearances.
Aug 2026 (estimated): Beidaihe leadership retreat — informal, dates not announced. Key decisions emerge.
Sep 9 2026: Mao Zedong death anniversary.
Oct 1 2026: PRC National Day, 77th anniversary — military parade in major years, expected display of new platforms.
Oct 25 2026: UN Resolution 2758 — 55th anniversary, contested interpretation flashpoint.
Late 2026: Fourth Plenum of 20th CC expected — economic reform agenda.
Dec 13 2026: Nanjing Massacre Day of National Memory (国家公祭日).
Recurring monthly: Politburo Standing Committee meetings (irregular but tracked).
Recurring bi-monthly: NPC Standing Committee sessions.
Recurring quarterly: NBS data releases (GDP, PMI, trade balance).
Recurring: USCC public hearings (typically monthly).
Recurring: House Select Committee on the CCP hearings.
Recurring: IAEA Board of Governors meets Mar, Jun, Sep, Nov — China nuclear program agenda item."""


# ─────────────────────────────────────────────────────────────────────────────
# USER PROMPT BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def _has_xinhua_data(payload: dict) -> bool:
    """Check whether any Xinhua/Tier 4 data was actually collected."""
    summary = payload.get("xinhua_summary")
    has_summary = summary and summary.get("total_articles", 0) > 0
    has_tier4 = bool(payload.get("tier4"))
    return has_summary or has_tier4


_XINHUA_NO_DATA_STUB = (
    "NO XINHUA / TIER 4 DATA COLLECTED TODAY — scrapers returned 0 articles.\n"
    "Do NOT fabricate Xinhua / People's Daily content. Return a minimal xinhua_delta with:\n"
    " silence_today: true, output_volume: \"Unavailable — 0 articles collected (scraper failure)\",\n"
    " xi_appearance_today: false (unless XI JINPING APPEARANCE REPORTS above confirm otherwise),\n"
    " days_since_last_appearance: use tracker data above,\n"
    " propaganda_focus: null, notable_omissions: null, tone_shifts: null,\n"
    " key_phrase_changes: [], key_quotes: [], doctrinal_shift: null,\n"
    " senior_officials: [], baseline_period: null,\n"
    " watch_flag: false, bottom_line: \"No Xinhua / People's Daily data collected — scraper issue, not a blackout.\""
)


_XINHUA_FULL_INSTRUCTIONS = (
    "Return a SINGLE xinhua_delta object analyzing today's PRC official media output:\n"
    "- xi_appearance_today: boolean — cross-reference Tier 4 articles AND the XI JINPING APPEARANCE REPORTS section above. If ANY credible source reports a Xi public appearance, statement, or meeting in the last 24h, set to true. Xi appears more regularly than Kim Jong Un — true should be common.\n"
    "- xi_activity: if appeared, 1 sentence on what he did (speech, meeting, inspection, study session, summit), else null\n"
    "- days_since_last_appearance: integer — use the CONFIRMED XI APPEARANCES tracker data above as ground truth.\n"
    "- senior_officials: array of notable non-Xi appearances/statements (Li Qiang, Wang Yi, He Lifeng, Dong Jun, Mao Ning/Lin Jian MOFA presser). Each: name, role (title), activity (1 sentence). Max 3.\n"
    "- peoples_daily_front_page: string — top headline on People's Daily front page today, with 1-line interpretive frame on what theme it advances. null if no data.\n"
    "- mofa_presser: object or null — today's MOFA spokesperson briefing. Object with: spokesperson (Mao Ning / Lin Jian), key_qa (1-2 sentences capturing the most analytically significant Q&A pair).\n"
    "- global_times_editorial: string or null — top Global Times editorial topic and the line they're pushing.\n"
    "- xinhua_commentary: object or null — track signed commentaries using pseudonyms: 钟声 (Zhongsheng — foreign policy), 任仲平 (Renzhongping — major political messaging), 国纪平 (Guojiping — international affairs). Object with: pseudonym, topic, key_argument (1 sentence).\n"
    "- propaganda_focus: top 2-3 themes PRC official media is prioritizing today (e.g. \"new productive forces\", \"Cross-Strait reunification\", \"anti-hegemonism\", \"common prosperity\", \"Chinese-style modernization\")\n"
    "- notable_omissions: anything conspicuously absent that was previously regular. ONLY cite specific day counts if the XINHUA RHETORIC HISTORY tracker data supports it. null if nothing notable.\n"
    "- key_phrase_changes: array of phrase frequency objects. Track key doctrinal phrases: 新质生产力 (new productive forces), 共同富裕 (common prosperity), 中国式现代化 (Chinese-style modernization), 全过程人民民主 (whole-process people's democracy), 总体国家安全观 (overall national security concept), 一国两制 (one country two systems), 中华民族伟大复兴 (great rejuvenation of the Chinese nation). Each: phrase (English + Chinese), count_this_week (integer from today's articles), count_prior (from tracker history, or 0 if no baseline), delta_label (e.g. \"↑ from ×2\", \"new phrase\", \"→ stable\"). MAX 5 phrases — only include changed or significant ones.\n"
    "- doctrinal_shift: if any phrase represents a new doctrinal position (e.g. new Taiwan framing, revised security concept, novel BRI/GDI/GSI/GCI variant), describe in 1-2 sentences. null if routine rhetoric.\n"
    "- key_quotes: 1 direct quote from Xinhua / People's Daily / Global Times / MOFA most analytically significant today. Each: quote (exact text, translated), source_article (title), speaker (if attributed). Empty array if nothing notable.\n"
    "- tone_shifts: object tracking tone toward key counterparts. Keys: us, japan, taiwan, india, eu, russia. Values: 1 sentence describing today's tone OR null if no notable signal today. Only fill if tone is distinctly hostile/conciliatory/changed.\n"
    "- output_volume: string assessment vs normal (e.g. \"Heavy — 32 articles (avg: 18)\", \"Light — 8 articles\"). Use XINHUA OUTPUT SUMMARY above for actual count.\n"
    "- silence_today: boolean — true if complete output blackout (rare)\n"
    "- watch_flag: boolean — true if output contains escalation-level rhetoric, unusual Xi absence (14+ days), Taiwan-specific aggressive framing, or new doctrinal language\n"
    "- bottom_line: 1-2 sentences MAX. State the single most important Xinhua/PD/GT takeaway and what to watch. Ruthlessly concise."
)


def _build_xinhua_summary_block(payload: dict) -> str:
    """Format the pre-collected Xinhua/PD summary into a prompt block."""
    summary = payload.get("xinhua_summary")
    if not summary or not summary.get("total_articles"):
        return ""

    direct = summary.get("direct_count", 0)
    indirect = summary.get("indirect_count", 0)

    lines = [
        f"XINHUA / PEOPLE'S DAILY OUTPUT SUMMARY (scraped today):",
        f"Total articles collected: {summary['total_articles']} "
        f"(direct PRC primary: {direct}, indirect/citing: {indirect})",
    ]

    sources = summary.get("sources", {})
    if sources:
        src_strs = [f"{src}: {count}" for src, count in
                   sorted(sources.items(), key=lambda x: -x[1])]
        lines.append(f"Sources: {', '.join(src_strs)}")

    headlines = summary.get("headlines", [])
    if headlines:
        lines.append(f"\nToday's headlines ({len(headlines)} articles):")
        for h in headlines:
            lines.append(f"  • {h}")

    lines.append("")
    return "\n".join(lines)


def build_user_prompt(payload: dict, date_str: str, db_context: str = "") -> str:
    def tier_json(articles: list, max_items: int = 60) -> str:
        trimmed = articles[:max_items]
        result = []
        for a in trimmed:
            item = {
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "summary": a.get("summary", "")[:800],
                "source": a.get("source", ""),
                "lang": a.get("lang", "EN"),
                "prestige_tier": a.get("prestige_tier"),
                "china_primary": a.get("china_primary", False),
                "journal_tier": a.get("journal_tier"),
            }
            if a.get("tags"):
                item["tags"] = a["tags"]
            result.append(item)
        return json.dumps(result, ensure_ascii=False, indent=1)

    # Market data block
    market_block = ""
    markets = payload.get("market_indicators")
    if markets:
        market_block = f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MARKET DATA (pre-collected, include as-is in output)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{json.dumps(markets, indent=1)}

Pass this data through directly as the market_indicators field in your output. Do NOT modify the values."""

    # Database context
    db_block = ""
    if db_context:
        db_block = f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CSIS DATABASE CONTEXT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{db_context}

Use this for on_this_day, calendar_watch, and pattern_note fields."""

    # Xi appearance tracker
    xi_block = ""
    xi_articles = payload.get("xi_tracker_articles", [])
    if xi_articles:
        xi_block += f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
XI JINPING APPEARANCE REPORTS (scraped from multiple sources, last 72h)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{tier_json(xi_articles, max_items=20)}

Cross-reference these reports with Tier 4 (Xinhua / People's Daily) data."""

    try:
        from xi_tracker import build_context_block as xi_context
        xi_history = xi_context()
        if xi_history:
            xi_block += f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{xi_history}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
    except Exception:
        pass

    # Xinhua rhetoric history
    xinhua_block = ""
    try:
        from xinhua_tracker import build_context_block as xinhua_context
        xinhua_history = xinhua_context()
        if xinhua_history:
            xinhua_block = f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{xinhua_history}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
    except Exception:
        pass

    # Monitored locations history
    bp_block = ""
    try:
        from bp_tracker import build_context_block as bp_context
        bp_history = bp_context()
        if bp_history:
            bp_block = f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{bp_history}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
    except Exception:
        pass

    # Tier 4 block — gate on actual data
    if _has_xinhua_data(payload):
        tier4_block = (
            f"{_build_xinhua_summary_block(payload)}\n"
            f"{tier_json(payload.get('tier4', []), max_items=30)}\n"
            f"{_XINHUA_FULL_INSTRUCTIONS}"
        )
    else:
        tier4_block = _XINHUA_NO_DATA_STUB

    return f"""Today's date: {date_str}

Process each tier according to its instructions and return a single JSON object.

CRITICAL — SOURCE GROUNDING: Every name, title, number, and fact you write MUST come from the source articles below. Do NOT fill in names from memory. Use the CURRENT POLITICAL LEADERS reference below only when the source article clearly refers to that role.

CRITICAL — SOURCE URLs: Every article, op-ed, academic paper, deal, and statement MUST include the original source URL from the input data. Use the exact URL provided in the feed data. Never use "#" or placeholder URLs.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
POLITICAL LEADERS REFERENCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{_POLITICAL_LEADERS}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
US-CHINA TRADE & SANCTIONS BASELINES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{_TRADE_BASELINES}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VERIFIED HISTORICAL DATES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{_KEY_DATES}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VERIFIED UPCOMING DATES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{_VERIFIED_UPCOMING}
{market_block}
{xi_block}
{xinhua_block}
{bp_block}
{db_block}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TIER 1: NEWS ARTICLES (last 24h)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{tier_json(payload.get("tier1", []))}

For EACH article, return:
- url, source, translated_title (English title — translate if Chinese)
- categories: array of: Cross-Strait / US-China / PRC-Economy / PLA / Indo-Pacific / Technology / Sanctions / Energy / Diplomacy
- signal_type: omit this field
- relevance_score: 1-10 (10 = essential for China policy analyst today)
- summary: 1-2 sentences in clear policy-analyst prose
- policy_so_what: For score >= 7 only. 1 sentence.
- pattern_note: For ESCALATION or ANOMALY only. 1 sentence citing precedent ONLY if mentioned in today's articles or the reference databases. Do NOT cite from memory.
- cross_strait_relevance: 1 sentence on Cross-Strait implications if relevant, else null
- is_reaction_source: true if Global Times, Xinhua, People's Daily, China Daily

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TIER 2: OP-EDS & PRESTIGE COMMENTARY → OUTPUT: opeds_today
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{tier_json(payload.get("tier2", []), max_items=30)}

ANTI-HALLUCINATION — OP-EDS: Only include op-eds/commentary that appear as actual articles in the Tier 2 input data above with a real URL. Do NOT fabricate think tank entries or authors. If no qualifying Tier 2 articles are present today, return an empty opeds_today array.

Each article in the Tier 2 input has fields: prestige_tier ("A" = top tier, "B" = standard), china_primary (true for all Tier-A sources — already computed). Use these directly; do not override them.

For EACH qualifying piece output: url (copy verbatim from input — do not alter), source, prestige_tier (from input), authors (from article metadata if available, else null), china_primary (from input), relevance_score (1-10), central_argument (single sentence stating the thesis directly — not "this argues that..."), summary (2-3 sentences), policy_so_what (1 sentence, score >= 6 only).

Inclusion thresholds: prestige_tier "A" if china_primary=true → always include. prestige_tier "B" or "A" without china_primary → include if relevance_score >= 7.

CSIS PRODUCTS (CSIS China, CSIS ChinaPower, CSIS AMTI, CSIS Hidden Reach, CSIS Big Data China): MANDATORY inclusion whenever present in input — these are our own in-house products.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TIER 3: ACADEMIC JOURNALS → OUTPUT: academic_today
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{tier_json(payload.get("tier3", []), max_items=20)}

ANTI-HALLUCINATION — ACADEMIC: Only include journal articles that appear in the Tier 3 input data above with a real URL. Do NOT fabricate journal articles, authors, or journal names. News outlets (Reuters, AFP, Ratopati, etc.) are NEVER journal authors — if a source is not a recognized academic journal, skip it.

For EACH qualifying piece output: url (copy verbatim from input), source (journal name from input), journal_tier (from input: A+/A/B), authors (from article metadata if available, else null), china_relevance_score (1-10), framework, summary (2-3 sentences), policy_implication (1 sentence).

Inclusion thresholds: journal_tier "A+" → include if score >= 4. journal_tier "A" → include if score >= 6. journal_tier "B" → include if score >= 8.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TIER 4: XINHUA / PEOPLE'S DAILY / GLOBAL TIMES / MOFA (last 48h)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{tier4_block}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DIGEST SYNTHESIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TARGET LENGTH — HARD MINIMUM 1,000 WORDS (5-minute read). Aim for 1,200-1,400 words.

Return a digest object with:

- digest_date: "{date_str}"

- re_line: one-line RE: summary (max 120 chars, key themes separated by ·)

- editor_note: 1-2 sentence framing of today's news. Factual, no editorializing.

- market_indicators: pass through the pre-collected market data object exactly as provided.

- morning_memo: EXACTLY 3 items. Each one sentence summarizing one of today's top China stories. What a China desk officer tells their boss in the elevator. Lead with the verb. Sourced from today's actual articles.

- on_this_day: array with at most 1 historical China event matching TODAY's EXACT calendar date (month + day). Use VERIFIED CHINA DATES list ONLY. Empty array if no verified event falls on today's date. Each: date (e.g. "October 1, 1949"), event (1 sentence), relevance (1 sentence connecting to current situation).

- key_stat: a single striking statistic from TODAY's articles — must be different from yesterday. Object: number (e.g. "$2.3B", "53%", "12"), label (under 60 chars), context (1 sentence), source (article it came from).

- imagery_report: if AMTI / Hidden Reach / CSIS / Planet Labs published satellite imagery analysis today, return object with: source, date, label, headline, body (2-3 sentences), source_links (array), affected_locations (array of location names from monitored_locations). Null if no imagery today.

- monitored_locations: array of 16 location status objects (8 gray-zone + 8 hidden-reach). GROUNDING: If today's articles report on a location, update from the article. If no article mentions a location, COPY the tracker's last-known note VERBATIM. Never replace a substantive tracker note with "No new reporting". Each: name, block ("gray_zone" or "hidden_reach"), status (normal/activity/elevated/alert), note (1-2 sentences), last_source_date, direction ("up"/"down"/""), csis_product (from tracker).

- prc_government: array of PRC State Council / ministry actions from today's news. Each: ministry (English), ministry_chinese (e.g. 外交部, 国防部, 商务部, 中国人民银行), official (name + title), action (1-line headline), detail (1-2 sentences), source_label (e.g. "MOFA EN", "MOFCOM", "PBOC"), url.

- npc_politburo: array of NPC Standing Committee, Politburo Standing Committee, Two Sessions, Beidaihe, or Plenum activity from today's news. Each: body, action, detail (1-2 sentences), url. Empty array if no relevant activity.

- congressional_watch: array of US Congressional activity on China (Select Committee on the CCP, SFRC, HFAC, USCC, CECC). Each: committee, action (1 line), detail (1-2 sentences), members (key names if relevant), url. Empty if nothing today.

- calendar_watch: array of 4-5 key upcoming events in next 14-30 days (MIN 4, MAX 5). Only use events from (a) today's articles with dates, (b) VERIFIED UPCOMING DATES, or (c) trade baselines. Each: month (3-letter), day (int), headline, detail (1-2 sentences).

- overnight_items: 6 items MAX. Source diversity MANDATORY (max 3 from any single source). Topic diversity MANDATORY (each different topic). Each: url, source, category, headline (under 100 chars), body_text (2-3 sentences, 50-70 words).

- top_stories: 2-4 biggest HARD NEWS stories — aim for 3 typical, 2 slow days, 4 when multiple major stories. From wires/correspondents/PRC press/government — NOT op-eds or think tank commentary. TOPIC DIVERSITY MANDATORY. Each: url, source, category_tag (Cross-Strait/US-China/PRC-Economy/PLA/Indo-Pacific/Technology/Sanctions/Energy/Diplomacy), headline, body (MAX 3 sentences, aim for 2 — facts: who/what/when/specifics), so_what (1 sentence — specific decision/meeting/timeline this affects, only if appears in today's articles or calendar_watch), pattern_note (1 sentence with historical precedent ONLY if precedent appears in today's articles or reference data; else null), src_line.

- also_today: up to 6 remaining articles score >= 4. Each: url, source, category, headline, body_text (1-2 sentences), color_bar_class (cb-navy=Cross-Strait, cb-red=PLA, cb-lt=Trade/Sanctions, cb-mid=Diplomacy, cb-tech=Technology, cb-biz=Economy).

- us_china_trade: US-China trade and sanctions architecture. Object with sub-blocks (NO REPETITION across sub-blocks):
  - tariff_tracker: object with headline_section_301_rate (current Section 301 average), section_232_rates (object: steel, aluminum, copper, autos, semiconductors), ieepa_fentanyl_rate ("20%"), section_122_surcharge ("10%, expires Jul 24 2026"), last_change (string), next_trigger (string). Use TRADE BASELINES above as default; only change if today's articles report new action.
  - entity_list_tracker: object with total_count (string, verify from articles), recent_adds_7day (array of {{entity_name, sector, date}}), most_recent_add (string).
  - cfius: array of recent CFIUS reviews/divestiture orders from today's articles. Each: company, sector, action, date.
  - deals: array of NEW US-China deals or divestitures announced TODAY. Each: url, source, headline, value (or null), parties, detail (1 sentence).

- business_economy: array up to 6 China business/economy items. Each: url, source, headline, body_text (1-2 sentences with specific numbers), companies (array of names), sector (tech/auto/energy/finance/manufacturing/property/macro).

- indo_pacific: array of 4-6 items covering Cross-Strait, Japan, Philippines, Australia, India, Korea, Vietnam, ASEAN. Always include at least one Cross-Strait item even on slow days. Each: url, source, headline, body_text (1-2 sentences), category (cross-strait, taiwan-elections, taiwan-arms, japan-senkaku, japan-history, philippines-scs, australia-aukus, india-lac, korea-china, vietnam-scs, asean), region_tag ("Cross-Strait" / "Japan-China" / "Philippines-China" / "Australia-China" / "India-China" / "Korea-China" / "Indo-Pacific").

- social_statements: 3-6 quotes from senior officials. ATTRIBUTION RULE: quote MUST be a statement made BY the named person in their OFFICIAL CAPACITY on a policy-relevant topic. Prioritize Xi Jinping, Li Qiang, Wang Yi, He Lifeng, Dong Jun, MOFA spokespersons; US officials (Trump, Rubio, Hegseth, Bessent, Lutnick, Greer); Taiwan officials (Lai, Hsiao, Lin Chia-lung, Wellington Koo); foreign leaders.

Each: avatar_initials (2 letters), who (name), handle_context (title/role), platform_date (source · date), quote_text (direct quote), analyst_note (1 sentence factual context only from today's articles or reference data; no interpretation), badge_class (sb-p=policy, sb-r=security/red, sb-s=specialist/purple), url.

- personnel_changes: array of PRC and Taiwan personnel changes from today's news — Politburo, Central Committee, ministerial, PLA theater commands, ambassadors, SOE leadership, provincial party secretaries. Each: position, name, action (appointed/resigned/dismissed/nominated/confirmed/rotated), detail (1-2 sentences), predecessor (if relevant).

- opeds_today: qualifying Tier 2 pieces, ordered by prestige then score
- academic_today: qualifying Tier 3 pieces, ordered by journal_tier then score
- xinhua_delta: the Tier 4 object built per instructions above
- timeline_candidates: list of urls flagged for any CSIS bilateral event database (Cross-Strait incidents, NK-Russia, China-Russia, BRICS expansion events)

PLACEMENT PRIORITY (highest wins): top_stories > overnight_items > indo_pacific > us_china_trade > business_economy > also_today. Each article appears in exactly ONE section — deduplicate by URL AND topic.

- story_count: total Tier 1 articles processed
- oped_count: qualifying Tier 2 count
- academic_count: qualifying Tier 3 count

Return ONLY valid JSON. No markdown fences, no preamble."""


# ─────────────────────────────────────────────────────────────────────────────
# JSON PARSE + STREAM HELPERS
# ─────────────────────────────────────────────────────────────────────────────

_TEXT_FIELDS = ("body", "body_text", "summary", "detail", "quote_text",
               "so_what", "pattern_note", "central_argument", "analyst_note")


def _count_digest_words(digest: dict) -> int:
    words = 0
    for mi in (digest.get("morning_memo") or []):
        if isinstance(mi, dict):
            for v in mi.values():
                if isinstance(v, str):
                    words += len(v.split())
        elif isinstance(mi, str):
            words += len(mi.split())

    for section_key in ("top_stories", "overnight_items", "also_today", "business_economy",
                       "opeds_today", "academic_today", "social_statements",
                       "indo_pacific", "congressional_watch", "prc_government"):
        for item in (digest.get(section_key) or []):
            if not isinstance(item, dict):
                continue
            for field in _TEXT_FIELDS:
                val = item.get(field, "")
                if val:
                    words += len(str(val).split())

    delta = digest.get("xinhua_delta") or {}
    for field in ("bottom_line", "doctrinal_shift"):
        val = delta.get(field, "")
        if val:
            words += len(str(val).split())

    return words


def _check_content_minimums(digest: dict) -> list[str]:
    failures = []
    word_count = _count_digest_words(digest)
    if word_count < 1000:
        failures.append(f"WORD COUNT: {word_count} words (hard minimum 1000)")
    top = len(digest.get("top_stories") or [])
    if top < 2:
        failures.append(f"TOP STORIES: {top} (minimum 2)")
    overnight = len(digest.get("overnight_items") or [])
    if overnight < 3:
        failures.append(f"OVERNIGHT ITEMS: {overnight} (minimum 3)")
    memo = len(digest.get("morning_memo") or [])
    if memo != 3:
        failures.append(f"MORNING MEMO: {memo} (must be exactly 3)")
    return failures


def _strip_fences(raw: str) -> str:
    text = raw.strip()
    text = re.sub(r'^```\w*\s*$', '', text, flags=re.MULTILINE)
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```\w*', '', text, count=1)
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _robust_json_parse(raw: str) -> dict:
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    stripped = _strip_fences(text)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace:last_brace + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    preview = text[:200]
    raise json.JSONDecodeError(
        f"All JSON extraction strategies failed. Response starts with: {preview!r}",
        text, 0,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLAUDE API CALL — Sonnet primary, Opus retry
# ─────────────────────────────────────────────────────────────────────────────

FAST_MODEL = "claude-sonnet-4-20250514"
PRIMARY_MODEL = "claude-opus-4-20250514"
_JSON_PREFILL = '{"'


def _stream_claude(client, messages: list, max_tokens: int = 16000,
                  retries: int = 3, model: str | None = None) -> dict:
    use_model = model or PRIMARY_MODEL
    model_label = use_model.split("-")[1]

    prefilled_messages = list(messages) + [
        {"role": "assistant", "content": _JSON_PREFILL}
    ]

    for attempt in range(retries):
        try:
            t0 = time.time()
            collected = []
            with client.messages.stream(
                model=use_model,
                max_tokens=max_tokens,
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=prefilled_messages,
            ) as stream:
                for text in stream.text_stream:
                    collected.append(text)
                response = stream.get_final_message()

            if response.stop_reason == "max_tokens":
                print(f"   ⚠ Response truncated ({response.usage.output_tokens} tokens)")

            elapsed = time.time() - t0
            raw_text = _JSON_PREFILL + "".join(collected)

            if not raw_text.strip():
                raise ValueError("Empty response from Claude API")

            cache_read = getattr(response.usage, 'cache_read_input_tokens', 0) or 0
            cache_create = getattr(response.usage, 'cache_creation_input_tokens', 0) or 0
            cache_info = ""
            if cache_read:
                cache_info = f" / {cache_read} cache-hit"
            elif cache_create:
                cache_info = f" / {cache_create} cache-write"

            print(f"   ⏱ {model_label} call: {elapsed:.0f}s "
                  f"({response.usage.input_tokens} in / {response.usage.output_tokens} out{cache_info})")

            return _robust_json_parse(raw_text)

        except (httpx.RemoteProtocolError, httpx.ReadError, httpx.StreamError) as e:
            if attempt < retries - 1:
                wait = 5 * (attempt + 1)
                print(f"   ⚠ Stream interrupted ({type(e).__name__}), retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise


def _call_claude(client, user_prompt: str, max_tokens: int = 16000,
                model: str | None = None) -> dict:
    return _stream_claude(client, [{"role": "user", "content": user_prompt}],
                         max_tokens, model=model)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY
# ─────────────────────────────────────────────────────────────────────────────

def generate_digest(payload: dict, db_context: str = "") -> dict:
    """Call Claude and return structured digest JSON. Retries on failure and enforces content minimums."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Missing ANTHROPIC_API_KEY environment variable.")

    client = anthropic.Anthropic(api_key=api_key)
    date_str = datetime.now(ZoneInfo("America/New_York")).strftime("%A, %B %-d, %Y")
    user_prompt = build_user_prompt(payload, date_str, db_context=db_context)

    total_articles = sum(len(v) for k, v in payload.items() if isinstance(v, list))
    print(f"   {total_articles} articles → Claude")

    MAX_ATTEMPTS = 4
    digest = None
    best_digest = None
    best_word_count = 0
    content_failures = []

    for attempt in range(MAX_ATTEMPTS):
        try:
            retry_model = FAST_MODEL if attempt == 0 else PRIMARY_MODEL

            if attempt == 0 or digest is None:
                digest = _call_claude(client, user_prompt, model=retry_model)
            else:
                word_deficit = max(0, 1000 - _count_digest_words(digest))
                expansion_prompt = (
                    f"Your previous digest output failed content minimums:\n"
                    + "\n".join(f"  • {f}" for f in content_failures)
                    + f"\n\nYou are ~{word_deficit} words short of the 1000-word minimum.\n"
                    + "\nHere is your previous output:\n"
                    + json.dumps(digest, ensure_ascii=False)[:8000]
                    + "\n\nRevise and return a COMPLETE updated digest JSON that fixes ALL failures. "
                      "Add MORE items from available articles to reach 1000+ words — do not inflate existing bodies. "
                      "Return ONLY valid JSON."
                )
                messages = [
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": json.dumps(digest, ensure_ascii=False)[:4000]},
                    {"role": "user", "content": expansion_prompt},
                ]
                digest = _stream_claude(client, messages, model=retry_model)

            # Preserve market data
            if payload.get("market_indicators") and not digest.get("market_indicators"):
                digest["market_indicators"] = payload["market_indicators"]

            # Track best across attempts
            word_count = _count_digest_words(digest)
            if word_count > best_word_count:
                best_digest = json.loads(json.dumps(digest))
                best_word_count = word_count

            content_failures = _check_content_minimums(digest)
            top_count = len(digest.get("top_stories") or [])
            overnight_count = len(digest.get("overnight_items") or [])

            if content_failures and attempt < MAX_ATTEMPTS - 1:
                print(f"   ⚠ Attempt {attempt + 1}: ~{word_count} words, "
                      f"{top_count} top, {overnight_count} overnight — retrying")
                time.sleep(2)
                continue

            if content_failures:
                if best_digest and best_word_count > word_count:
                    print(f"   ⚠ Using best attempt (~{best_word_count} words)")
                    digest = best_digest
                    word_count = best_word_count
                    top_count = len(digest.get("top_stories") or [])
                    overnight_count = len(digest.get("overnight_items") or [])
                else:
                    print(f"   ⚠ All attempts below minimums (~{word_count} words)")
            else:
                print(f"   ✓ ~{word_count} words, {top_count} top stories, {overnight_count} overnight")

            return digest

        except (anthropic.APIError, anthropic.APIConnectionError,
               httpx.RemoteProtocolError, httpx.StreamError) as e:
            if attempt < MAX_ATTEMPTS - 1:
                wait = 5 * (attempt + 1)
                print(f"   ⚠ API error (retrying in {wait}s): {e}")
                time.sleep(wait)
            else:
                raise

    return digest or {}

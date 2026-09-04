"""
China Daily Brief — Collector

Scrapes RSS feeds across four tiers + market data + monitored location feeds.
Mirrors the Daily-Korea-Digest collector architecture with China-specific sources.

Uses threaded fetching for performance (~15s vs ~60s sequential).
"""

import feedparser
import requests
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta


# ─────────────────────────────────────────────────────────────────────────────
# FEED CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

def _gnews(query: str) -> str:
    """Build a Google News RSS search URL (US English edition)."""
    return f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"


def _gnews_zh(query: str) -> str:
    """Google News RSS search, Simplified Chinese edition. Used for PRC-language
    primary sources (人民日报, 新华社, 财新 ...). Titles are translated by the model."""
    return f"https://news.google.com/rss/search?q={query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"


def _gnews_tw(query: str) -> str:
    """Google News RSS search, Traditional Chinese (Taiwan) edition."""
    return f"https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"


def _gnews_hk(query: str) -> str:
    """Google News RSS search, Traditional Chinese (Hong Kong) edition."""
    return f"https://news.google.com/rss/search?q={query}&hl=zh-HK&gl=HK&ceid=HK:zh-Hant"


# Cap per Chinese-language feed so 30 ZH feeds cannot crowd the English wires
# out of the prompt window; relevance ordering in digest.py does the rest.
ZH_PER_SOURCE_CAP = 12


# Direct publisher RSS with a Google News fallback (pattern from the Japan brief).
# Direct feeds carry real permalinks and full summaries, but a feed URL can rot
# or 403. Registering the fallback means a bad direct-feed guess degrades to the
# previous Google News behaviour instead of silently dropping the source.
_FALLBACK: dict[str, str] = {}


def _direct(source: str, direct_url: str, gnews_query: str) -> str:
    _FALLBACK[source] = _gnews(gnews_query)
    return direct_url


# ── TIER 1: NEWS (24h window) ─────────────────────────────────────────────────
TIER1_FEEDS = {
    # ── Major international — China correspondents ─────────────────────────
    "WSJ China":          _gnews("China+site:wsj.com"),
    "NYT China":          _gnews("China+site:nytimes.com"),
    "WaPo China":         _gnews("China+site:washingtonpost.com"),
    "FT China":           _gnews("China+site:ft.com"),
    "Reuters China":      _gnews("China+site:reuters.com"),
    "AP China":           _gnews("China+site:apnews.com"),
    "AFP China":          _gnews("China+site:afp.com"),
    "Bloomberg China":    _gnews("China+site:bloomberg.com"),
    "BBC China":          _gnews("China+site:bbc.com"),
    "BBC Asia (direct)":  _direct("BBC Asia (direct)", "https://feeds.bbci.co.uk/news/world/asia/rss.xml",
                                  "China+OR+Taiwan+site:bbc.com/news/world/asia"),
    "NYT Asia (direct)":  _direct("NYT Asia (direct)", "https://rss.nytimes.com/services/xml/rss/nyt/AsiaPacific.xml",
                                  "China+site:nytimes.com/section/world/asia"),
    "Guardian China (direct)": _direct("Guardian China (direct)", "https://www.theguardian.com/world/china/rss",
                                       "site:theguardian.com/world/china"),
    "CNN China":          _gnews("China+site:cnn.com"),
    "CNBC China":         _gnews("China+site:cnbc.com"),
    "Economist China":    _gnews("China+site:economist.com"),
    "Guardian China":     _gnews("China+site:theguardian.com"),
    "Al Jazeera China":   _gnews("China+site:aljazeera.com"),
    "Politico China":     _gnews("China+site:politico.com"),
    "Axios China":        _gnews("China+site:axios.com"),

    # ── Regional Asia ──────────────────────────────────────────────────────
    "SCMP":               "https://www.scmp.com/rss/91/feed",
    "SCMP China":         _direct("SCMP China", "https://www.scmp.com/rss/4/feed", "site:scmp.com/news/china"),
    "Nikkei Asia China":  _gnews("China+site:asia.nikkei.com"),
    "Japan Times China":  _gnews("China+site:japantimes.co.jp"),
    "Kyodo China":        _gnews("China+site:english.kyodonews.net"),
    "Mainichi China":     _gnews("China+site:mainichi.jp/english"),
    "Asahi China":        _gnews("China+site:asahi.com/ajw"),
    "CNA China":          _gnews("China+site:channelnewsasia.com"),
    "Straits Times China": _gnews("China+site:straitstimes.com"),
    "The Diplomat China": _gnews("site:thediplomat.com+China"),
    "The Diplomat (direct)": _direct("The Diplomat (direct)", "https://thediplomat.com/feed/",
                                     "site:thediplomat.com+China+OR+Taiwan+OR+PLA"),

    # ── Taiwan press (English) ─────────────────────────────────────────────
    "Taipei Times":       _gnews("site:taipeitimes.com"),
    "Taipei Times (direct)": _direct("Taipei Times (direct)", "https://www.taipeitimes.com/xml/index.rss",
                                     "site:taipeitimes.com/News/front"),
    "Focus Taiwan":       _gnews("Taiwan+OR+China+site:focustaiwan.tw"),
    "Taiwan News":        _gnews("site:taiwannews.com.tw"),
    "Liberty Times EN":   _gnews("Taiwan+site:englishnews.ltn.com.tw"),

    # ── PRC English-language press (Tier 4 covers Chinese-language primary) ───
    "Caixin Global":      _gnews("China+site:caixinglobal.com"),
    "China Daily":        _gnews("site:chinadaily.com.cn"),
    "China Daily (direct)": _direct("China Daily (direct)", "http://www.chinadaily.com.cn/rss/china-rss.xml",
                                    "site:chinadaily.com.cn/a"),
    "Sixth Tone":         _gnews("China+site:sixthtone.com"),
    "Hong Kong Free Press": "https://hongkongfp.com/feed/",

    # ── US Government — China-relevant ─────────────────────────────────────
    "White House China":  _gnews("China+site:whitehouse.gov"),
    "State Dept China":   _gnews("China+site:state.gov"),
    "State Dept Press (direct)": _direct("State Dept Press (direct)",
                                         "https://www.state.gov/rss-feed/press-releases/feed/",
                                         "China+OR+Taiwan+OR+PRC+site:state.gov/releases"),
    "Pentagon China":     _gnews("China+site:defense.gov"),
    "Treasury China":     _gnews("China+site:treasury.gov"),
    "OFAC China":         _gnews("China+site:ofac.treasury.gov"),
    "Commerce China":     _gnews("China+site:commerce.gov"),
    "BIS Entity List":    _gnews("China+site:bis.doc.gov"),
    "USTR China":         _gnews("China+site:ustr.gov"),
    "USCC":               _gnews("site:uscc.gov"),
    "CECC":               _gnews("site:cecc.gov"),
    "DOJ China":          _gnews("China+espionage+OR+sanctions+site:justice.gov"),
    "FBI China":          _gnews("China+site:fbi.gov"),

    # ── US Congress — China-relevant ───────────────────────────────────────
    "House Select CCP":   _gnews("site:selectcommitteeontheccp.house.gov"),
    "Senate Foreign Rel": _gnews("China+site:foreign.senate.gov"),
    "House Foreign Affairs": _gnews("China+site:foreignaffairs.house.gov"),
    "Senate Armed Svc":   _gnews("China+site:armed-services.senate.gov"),
    "House Armed Svc":    _gnews("China+site:armedservices.house.gov"),

    # ── US Military / Combatant Commands ──────────────────────────────────
    "INDOPACOM":          _gnews("China+OR+Taiwan+site:pacom.mil"),
    "AFRICOM China":      _gnews("China+site:africom.mil"),
    "Stars and Stripes":  _gnews("China+OR+Taiwan+site:stripes.com"),

    # ── Taiwan Government ──────────────────────────────────────────────────
    "Taiwan MOFA":        _gnews("site:mofa.gov.tw"),
    "Taiwan MND":         _gnews("site:mnd.gov.tw"),
    "Taiwan MAC":         _gnews("site:mac.gov.tw"),
    "Taiwan Presidential": _gnews("site:president.gov.tw"),

    # ── Frontline-state government ─────────────────────────────────────────
    "Japan MOFA China":   _gnews("China+site:mofa.go.jp"),
    "Japan MOD China":    _gnews("China+site:mod.go.jp"),
    "PH DFA":             _gnews("China+site:dfa.gov.ph"),
    "PH Coast Guard":     _gnews("site:coastguard.gov.ph"),
    "AU DFAT China":      _gnews("China+site:dfat.gov.au"),
    "India MEA China":    _gnews("China+site:mea.gov.in"),

    # ── International organizations ────────────────────────────────────────
    "IAEA China":         _gnews("China+site:iaea.org"),
    "UN China":           _gnews("China+site:un.org"),
    "UN Human Rights":    _gnews("China+OR+Xinjiang+site:ohchr.org"),

    # ── Reaction layer (Russia) ────────────────────────────────────────────
    "TASS China":         _gnews("China+site:tass.com"),
    "RT China":           _gnews("China+site:rt.com"),

    # ── Specialist China outlets ───────────────────────────────────────────
    "Sinocism":           "https://sinocism.com/feed",
    "ChinaFile":          _gnews("site:chinafile.com"),
    "China Digital Times": "https://chinadigitaltimes.net/feed/",
    "What's on Weibo":    "https://www.whatsonweibo.com/feed/",
    "China Media Project": _direct("China Media Project", "https://chinamediaproject.org/feed/",
                                   "site:chinamediaproject.org"),
    "Trivium China":      _gnews("site:triviumchina.com"),
    "The Wire China":     _direct("The Wire China", "https://www.thewirechina.com/feed/",
                                  "site:thewirechina.com"),
    "Pekingnology":       _direct("Pekingnology", "https://www.pekingnology.com/feed",
                                  "site:pekingnology.com"),
    "Sinification":       _direct("Sinification", "https://www.sinification.com/feed",
                                  "site:sinification.com"),
    "ChinaTalk":          _direct("ChinaTalk", "https://www.chinatalk.media/feed",
                                  "site:chinatalk.media"),
    # MacroPolo (Paulson Institute) wound down in 2024; feed removed.

    # ── Chinese-language press (tagged lang=ZH, titles translated by the model) ──
    # PRC party / state media
    "人民日报 (People's Daily ZH)": _direct("人民日报 (People's Daily ZH)",
                                           "http://www.people.com.cn/rss/politics.xml",
                                           "site:people.com.cn"),
    "人民日报国际 (People's Daily World ZH)": _gnews_zh("site:world.people.com.cn"),
    "新华社 (Xinhua ZH)":          _gnews_zh("site:news.cn"),
    "环球时报 (Global Times ZH)":  _gnews_zh("site:huanqiu.com"),
    "央视新闻 (CCTV ZH)":          _gnews_zh("site:news.cctv.com"),
    "中国新闻网 (China News ZH)":  _gnews_zh("site:chinanews.com.cn"),
    "求是 (Qiushi ZH)":            _gnews_zh("site:qstheory.cn"),
    "解放军报 (PLA Daily ZH)":     _gnews_zh("site:81.cn"),
    "澎湃新闻 (The Paper ZH)":     _gnews_zh("site:thepaper.cn"),
    "观察者网 (Guancha ZH)":       _gnews_zh("site:guancha.cn"),
    "经济日报 (Economic Daily ZH)": _gnews_zh("site:ce.cn"),
    # PRC financial press
    "财新 (Caixin ZH)":            _gnews_zh("site:caixin.com"),
    "第一财经 (Yicai ZH)":         _gnews_zh("site:yicai.com"),
    "21世纪经济报道 (21st Century Business Herald ZH)": _gnews_zh("site:21jingji.com"),
    "经济观察报 (Economic Observer ZH)": _gnews_zh("site:eeo.com.cn"),
    "界面新闻 (Jiemian ZH)":       _gnews_zh("site:jiemian.com"),
    "证券时报 (Securities Times ZH)": _gnews_zh("site:stcn.com"),
    # Hong Kong
    "明报 (Ming Pao ZH)":          _gnews_hk("site:mingpao.com+%E4%B8%AD%E5%9C%8B"),
    "香港01 (HK01 ZH)":            _gnews_hk("site:hk01.com+%E4%B8%AD%E5%9C%8B+OR+%E5%85%A7%E5%9C%B0"),
    "星岛日报 (Sing Tao ZH)":      _gnews_hk("site:stheadline.com+%E4%B8%AD%E5%9C%8B"),
    "信报 (HKEJ ZH)":              _gnews_hk("site:hkej.com+%E4%B8%AD%E5%9C%8B"),
    # Taiwan
    "中央社 (CNA ZH)":             _gnews_tw("site:cna.com.tw+%E4%B8%AD%E5%9C%8B+OR+%E5%85%A9%E5%B2%B8"),
    "联合报 (UDN ZH)":             _gnews_tw("site:udn.com+%E4%B8%AD%E5%9C%8B+OR+%E5%85%A9%E5%B2%B8"),
    "自由时报 (Liberty Times ZH)": _gnews_tw("site:ltn.com.tw+%E4%B8%AD%E5%9C%8B+OR+%E5%85%A9%E5%B2%B8"),
    "中国时报 (China Times ZH)":   _gnews_tw("site:chinatimes.com+%E4%B8%AD%E5%9C%8B+OR+%E5%85%A9%E5%B2%B8"),
    "上报 (UP Media ZH)":          _gnews_tw("site:upmedia.mg+%E4%B8%AD%E5%9C%8B"),
    # Singapore / overseas Chinese-language
    "联合早报 (Lianhe Zaobao ZH)": _gnews_zh("site:zaobao.com.sg+%E4%B8%AD%E5%9B%BD"),
    "端传媒 (Initium ZH)":         _gnews_hk("site:theinitium.com"),
    # International outlets' Chinese editions (often carry detail the English
    # edition does not, and the reverse)
    "纽约时报中文网 (NYT Chinese ZH)": _gnews_zh("site:cn.nytimes.com"),
    "FT中文网 (FT Chinese ZH)":    _gnews_zh("site:ftchinese.com"),
    "华尔街日报中文 (WSJ Chinese ZH)": _gnews_zh("site:cn.wsj.com"),
    "BBC中文 (BBC Chinese ZH)":    _gnews_zh("site:bbc.com/zhongwen"),
    "德国之声中文 (DW Chinese ZH)": _gnews_zh("site:dw.com/zh"),
    "美国之音中文 (VOA Chinese ZH)": _gnews_zh("site:voachinese.com"),
    "日经中文网 (Nikkei Chinese ZH)": _gnews_zh("site:cn.nikkei.com"),
    "路透中文 (Reuters Chinese ZH)": _gnews_zh("site:cn.reuters.com"),
}


# ── TIER 2: ANALYSIS (36h window) ─────────────────────────────────────────────
TIER2_FEEDS = {
    # CSIS in-house — highest priority
    "CSIS China":              (_gnews("China+site:csis.org"), "A"),
    "CSIS ChinaPower":         (_gnews("site:chinapower.csis.org"), "A"),
    "CSIS ChinaPower (direct)": (_direct("CSIS ChinaPower (direct)", "https://chinapower.csis.org/feed/",
                                         "site:chinapower.csis.org"), "A"),
    "CSIS AMTI":               (_gnews("site:amti.csis.org"), "A"),
    "CSIS AMTI (direct)":      (_direct("CSIS AMTI (direct)", "https://amti.csis.org/feed/",
                                        "site:amti.csis.org"), "A"),
    "CSIS Hidden Reach":       (_gnews("site:features.csis.org+China+OR+Hidden+Reach"), "A"),
    "CSIS Big Data China":     (_gnews("site:bigdatachina.csis.org"), "A"),

    # Top-tier think tanks
    "Brookings China":         (_gnews("China+site:brookings.edu"), "A"),
    "Carnegie China":          (_gnews("China+site:carnegieendowment.org"), "A"),
    "Carnegie China Center":   (_gnews("site:carnegieendowment.org/china"), "A"),
    "RAND China":              ("https://www.rand.org/topics/china.xml", "A"),
    "CFR China":               (_gnews("China+site:cfr.org"), "A"),
    "Atlantic Council China":  (_gnews("China+site:atlanticcouncil.org"), "A"),
    "Hoover China":            (_gnews("China+site:hoover.org"), "A"),

    # China-focused specialist
    "MERICS":                  (_gnews("site:merics.org"), "A"),
    "ASPI China":              (_gnews("China+site:aspi.org.au"), "A"),
    "ASPI Strategist (direct)": (_direct("ASPI Strategist (direct)", "https://www.aspistrategist.org.au/feed/",
                                         "China+OR+Taiwan+site:aspistrategist.org.au"), "A"),
    "Jamestown China":         (_gnews("site:jamestown.org+China+OR+Taiwan"), "A"),
    "Jamestown (direct)":      (_direct("Jamestown (direct)", "https://jamestown.org/feed/",
                                        "site:jamestown.org+China"), "A"),
    "Lowy Interpreter (direct)": (_direct("Lowy Interpreter (direct)",
                                          "https://www.lowyinstitute.org/the-interpreter/rss.xml",
                                          "China+site:lowyinstitute.org/the-interpreter"), "B"),
    "War on the Rocks (direct)": (_direct("War on the Rocks (direct)", "https://warontherocks.com/feed/",
                                          "China+OR+Taiwan+site:warontherocks.com"), "B"),
    "China Leadership Monitor": (_gnews("site:prcleader.org"), "A"),
    "China Strategies Group":  (_gnews("site:chinastrategiesgroup.com"), "B"),

    # Indo-Pacific specialist
    "USIP China":              (_gnews("China+site:usip.org"), "B"),
    "Stimson China":           ("https://www.stimson.org/feed/?topic=china", "B"),
    "IISS China":              (_gnews("China+site:iiss.org"), "B"),
    "Lowy Institute China":    (_gnews("China+site:lowyinstitute.org"), "B"),
    "GMF China":               (_gnews("China+site:gmfus.org"), "B"),
    "Asia Society Policy":     (_gnews("China+site:asiasociety.org/policy-institute"), "B"),

    # Economic / trade focus
    "PIIE China":              (_gnews("China+site:piie.com"), "A"),
    "Rhodium Group":           (_gnews("site:rhg.com+China"), "A"),
    "AEI China":               (_gnews("China+site:aei.org"), "B"),
    "Hudson China":            (_gnews("China+site:hudson.org"), "B"),
    "Heritage China":          (_gnews("China+site:heritage.org"), "B"),

    # US university and specialist China centers
    "Asia Society CCA":        (_gnews("site:asiasociety.org/center-china-analysis"), "A"),
    "NBR China":               (_gnews("China+site:nbr.org"), "B"),
    "Wilson Kissinger Inst":   (_gnews("China+site:wilsoncenter.org"), "B"),
    "Harvard Fairbank":        (_gnews("site:fairbank.fas.harvard.edu+OR+site:belfercenter.org+China"), "B"),
    "Stanford Hoover China":   (_gnews("site:hoover.org/research/china+OR+%22China+Leadership+Monitor%22"), "B"),
    "UCSD 21CCC":              (_gnews("site:china.ucsd.edu"), "B"),
    "Georgetown Initiative":   (_gnews("site:uscnpm.org+OR+site:georgetown.edu+%22U.S.-China%22"), "B"),
    "CNAS China":              (_gnews("China+site:cnas.org"), "B"),
    "CSBA China":              (_gnews("China+OR+PLA+site:csbaonline.org"), "B"),
    "FDD China":               (_gnews("China+site:fdd.org"), "B"),
    "Cato China":              (_gnews("China+site:cato.org"), "B"),
    "Quincy China":            (_gnews("China+site:quincyinst.org"), "B"),
    "Freeman Spogli":          (_gnews("China+site:fsi.stanford.edu"), "B"),
    "Paulson Institute":       (_gnews("site:paulsoninstitute.org"), "B"),
    "USCBC":                   (_gnews("site:uschina.org"), "B"),
    "AmCham China":            (_gnews("site:amchamchina.org"), "B"),
    "Interpret CSIS":          (_gnews("site:interpret.csis.org"), "A"),

    # European, Asian and other allied China centers
    "Chatham House China":     (_gnews("China+site:chathamhouse.org"), "B"),
    "ECFR China":              (_gnews("China+site:ecfr.eu"), "B"),
    "IFRI China":              (_gnews("China+site:ifri.org"), "B"),
    "SWP China":               (_gnews("China+site:swp-berlin.org"), "B"),
    "RUSI China":              (_gnews("China+site:rusi.org"), "B"),
    "EU Chamber China":        (_gnews("site:europeanchamber.com.cn"), "B"),
    "ORF China":               (_gnews("China+site:orfonline.org"), "B"),
    "Takshashila China":       (_gnews("China+site:takshashila.org.in"), "B"),
    "JIIA China":              (_gnews("China+site:jiia.or.jp"), "B"),
    "ISDP China":              (_gnews("China+site:isdp.eu"), "B"),
    "Sinolytics":              (_gnews("site:sinolytics.de"), "B"),
    "Gavekal":                 (_gnews("site:gavekal.com+China"), "B"),

    # China-based think tanks and university institutes (ZH; the model translates)
    "中国现代国际关系研究院 CICIR (ZH)": (_gnews_zh("site:cicir.ac.cn"), "A"),
    "中国国际问题研究院 CIIS (ZH)":     (_gnews_zh("site:ciis.org.cn"), "A"),
    "上海国际问题研究院 SIIS (ZH)":     (_gnews_zh("site:siis.org.cn"), "A"),
    "清华战略与安全研究中心 CISS (ZH)": (_gnews_zh("site:ciss.tsinghua.edu.cn"), "A"),
    "人大重阳 RDCY (ZH)":             (_gnews_zh("site:rdcy.ruc.edu.cn"), "B"),
    "全球化智库 CCG (ZH)":            (_gnews_zh("site:ccg.org.cn"), "B"),
    "复旦美国研究中心 (ZH)":          (_gnews_zh("site:cas.fudan.edu.cn+OR+%E5%A4%8D%E6%97%A6%E5%A4%A7%E5%AD%A6%E7%BE%8E%E5%9B%BD%E7%A0%94%E7%A9%B6%E4%B8%AD%E5%BF%83"), "B"),
    "北大国际战略研究院 IISS-PKU (ZH)": (_gnews_zh("site:iiss.pku.edu.cn"), "B"),
    "盘古智库 Pangoal (ZH)":          (_gnews_zh("site:pangoal.cn"), "B"),
    "太和智库 Taihe (ZH)":            (_gnews_zh("site:taiheinstitute.org"), "B"),
    "中国社科院 CASS (ZH)":           (_gnews_zh("site:cass.cn+%E5%9B%BD%E9%99%85"), "B"),
    "中美聚焦 China-US Focus":        (_gnews("site:chinausfocus.com"), "B"),
    "CGTN Think Tank":               (_gnews("site:cgtn.com+%22think+tank%22+OR+opinion+China+US"), "B"),

    # CRS / Congressional research
    "CRS China":               (_gnews("China+site:crsreports.congress.gov"), "B"),
    "GAO China":               (_gnews("China+site:gao.gov"), "B"),

    # Generalist with strong China coverage
    "Foreign Affairs China":   (_gnews("China+site:foreignaffairs.com"), "A"),
    "Foreign Policy China":    (_gnews("China+site:foreignpolicy.com"), "B"),
    "War on the Rocks China":  (_gnews("China+OR+Taiwan+site:warontherocks.com"), "B"),
}


# ── TIER 3: ACADEMIC JOURNALS (72h window) ────────────────────────────────────
TIER3_FEEDS = {
    # A+ tier — top IR/security journals
    "Int'l Security":          (_gnews("%22International+Security%22+%22China%22+OR+%22PRC%22+OR+%22Taiwan%22"), "A+"),
    "Int'l Organization":      (_gnews("%22International+Organization%22+%22China%22+OR+%22PRC%22"), "A+"),
    "World Politics":          (_gnews("%22World+Politics%22+%22China%22+OR+%22PRC%22"), "A+"),
    "Foreign Affairs":         (_gnews("%22Foreign+Affairs%22+%22China%22+OR+%22Taiwan%22+OR+%22PRC%22"), "A+"),

    # A tier — strong IR/area studies
    "Security Studies":        (_gnews("%22Security+Studies%22+%22China%22+OR+%22PRC%22"), "A"),
    "J. Conflict Resolution":  (_gnews("%22Journal+of+Conflict+Resolution%22+%22China%22"), "A"),
    "Int'l Studies Quarterly": (_gnews("%22International+Studies+Quarterly%22+%22China%22"), "A"),
    "J. Strategic Studies":    (_gnews("%22Journal+of+Strategic+Studies%22+%22China%22+OR+%22PLA%22"), "A"),
    "Asian Survey":            (_gnews("%22Asian+Survey%22+%22China%22+OR+%22PRC%22+OR+%22Taiwan%22"), "A"),
    "Pacific Review":          (_gnews("%22Pacific+Review%22+%22China%22"), "A"),
    "Survival IISS":           (_gnews("%22Survival%22+IISS+%22China%22+OR+%22Taiwan%22"), "A"),

    # B tier — China-specialist journals
    "China Quarterly":         (_gnews("%22China+Quarterly%22"), "B"),
    "J. Contemporary China":   (_gnews("%22Journal+of+Contemporary+China%22"), "B"),
    "China Journal":           (_gnews("%22The+China+Journal%22"), "B"),
    "China Information":       (_gnews("%22China+Information%22+journal"), "B"),
    "Asian Security":          (_gnews("%22Asian+Security%22+%22China%22"), "B"),
    "Pacific Affairs":         (_gnews("%22Pacific+Affairs%22+%22China%22"), "B"),
    "Washington Quarterly":    (_gnews("%22Washington+Quarterly%22+%22China%22"), "B"),
}


# ── TIER 4: PRC PRIMARY / PROPAGANDA (48h window) ─────────────────────────────
TIER4_FEEDS = {
    # Direct PRC state media
    "Xinhua English":      "http://www.xinhuanet.com/english/rss/worldrss.xml",
    "People's Daily EN":   _gnews("site:en.people.cn"),
    "Global Times":        "https://www.globaltimes.cn/rss/outbrain.xml",
    "China Daily Front":   _gnews("site:chinadaily.com.cn/front"),
    "CGTN":                _gnews("site:cgtn.com"),

    # PRC government, Chinese-language primary (what Beijing is saying, in its
    # own words). Tagged lang=ZH; the model quotes verbatim with the original.
    "外交部 (MOFA ZH)":            _gnews_zh("site:fmprc.gov.cn"),
    "外交部发言人 (MOFA presser ZH)": _gnews_zh("%E5%A4%96%E4%BA%A4%E9%83%A8%E5%8F%91%E8%A8%80%E4%BA%BA+%E4%BE%8B%E8%A1%8C%E8%AE%B0%E8%80%85%E4%BC%9A"),
    "国务院 (State Council ZH)":   _gnews_zh("site:gov.cn+%E5%9B%BD%E5%8A%A1%E9%99%A2"),
    "国防部 (MND ZH)":             _gnews_zh("site:mod.gov.cn+OR+%E5%9B%BD%E9%98%B2%E9%83%A8%E5%8F%91%E8%A8%80%E4%BA%BA"),
    "国台办 (TAO ZH)":             _gnews_zh("%E5%9B%BD%E5%8F%B0%E5%8A%9E+%E5%8F%91%E8%A8%80%E4%BA%BA"),
    "商务部 (MOFCOM ZH)":          _gnews_zh("site:mofcom.gov.cn+OR+%E5%95%86%E5%8A%A1%E9%83%A8%E5%8F%91%E8%A8%80%E4%BA%BA"),
    "中国人民银行 (PBOC ZH)":      _gnews_zh("%E4%B8%AD%E5%9B%BD%E4%BA%BA%E6%B0%91%E9%93%B6%E8%A1%8C+%E5%85%AC%E5%91%8A+OR+%E5%88%A9%E7%8E%87"),
    "新华社时评 (Xinhua commentary ZH)": _gnews_zh("%E6%96%B0%E5%8D%8E%E6%97%B6%E8%AF%84+OR+%E9%92%9F%E5%A3%B0+OR+%E4%BB%BB%E4%BB%B2%E5%B9%B3"),

    # PRC primary indirect — relayed by wires
    "MOFA Spokesperson":   _gnews("%22Mao+Ning%22+OR+%22Lin+Jian%22+OR+%22Guo+Jiakun%22+spokesperson"),
    "PRC Embassy US":      _gnews("site:us.china-embassy.gov.cn+OR+%22Chinese+Embassy%22+spokesperson+Liu+Pengyu"),
    "MND Spokesperson":    _gnews("%22Ministry+of+National+Defense%22+China+spokesperson+OR+%22Zhang+Xiaogang%22+OR+%22Jiang+Bin%22"),
    "Xi statements":       _gnews("%22Xi+Jinping%22+said+OR+statement+OR+remarks+OR+address"),
    "Wang Yi statements":  _gnews("%22Wang+Yi%22+China+foreign+minister+OR+%22Politburo%22"),
    "Li Qiang statements": _gnews("%22Li+Qiang%22+premier+OR+%22State+Council%22"),
    "Taiwan Affairs Office": _gnews("%22Taiwan+Affairs+Office%22+OR+%22TAO%22+spokesperson+China"),

    # Doctrinal language tracking
    "PD signed commentary": _gnews("%22Zhongsheng%22+OR+%22Renzhongping%22+OR+%22Guojiping%22+People%27s+Daily"),
    "New productive forces": _gnews("%22new+productive+forces%22+OR+%22new+quality+productive+forces%22"),
    "Common prosperity":   _gnews("%22common+prosperity%22+China+OR+%22共同富裕%22"),
}


# ── XI APPEARANCE TRACKER (72h window) ────────────────────────────────────────
XI_TRACKER_FEEDS = {
    "Xi Appearance":       _gnews("%22Xi+Jinping%22+appearance+OR+appeared+OR+attended+OR+inspected+OR+observed"),
    "Xi Activity":         _gnews("%22Xi+Jinping%22+meeting+OR+visit+OR+presided+OR+chaired"),
    "Xi Speech":           _gnews("%22Xi+Jinping%22+speech+OR+address+OR+remarks+OR+statement"),
    "Xi Politburo":        _gnews("%22Xi+Jinping%22+%22Politburo%22+OR+%22Standing+Committee%22+meeting"),
    "Xi (Jamestown)":      _gnews("%22Xi+Jinping%22+site:jamestown.org"),
}


# ── HIDDEN REACH IMAGERY FEEDS (72h window) ───────────────────────────────────
HIDDEN_REACH_FEEDS = {
    "HR LAC ports":        _gnews("%22Chancay%22+OR+%22COSCO%22+ports+China+Latin+America"),
    "HR Cuba SIGINT":      _gnews("%22Bejucal%22+OR+%22Wajay%22+China+Cuba+intelligence+OR+SIGINT"),
    "HR Djibouti":         _gnews("China+%22Djibouti%22+naval+OR+military+OR+base"),
    "HR Ream Cambodia":    _gnews("China+%22Ream%22+Cambodia+naval+OR+base+OR+pier"),
    "HR Khalifa UAE":      _gnews("China+%22Khalifa+Port%22+OR+UAE+military"),
    "HR Bata EG":          _gnews("China+%22Equatorial+Guinea%22+OR+%22Bata%22+naval+OR+base"),
    "HR Hambantota":       _gnews("China+%22Hambantota%22+OR+%22Sri+Lanka%22+naval+OR+submarine+OR+survey"),
    "HR Polar Silk Road":  _gnews("China+%22Arctic%22+OR+%22Polar+Silk+Road%22+%22Murmansk%22+OR+%22Sabetta%22"),
    "HR Shipyards":        _gnews("China+%22Jiangnan%22+OR+%22Hudong-Zhonghua%22+OR+%22Dalian%22+shipyard+naval"),
    "HR Research Vessels": _gnews("China+%22research+vessel%22+OR+%22survey+ship%22+Indian+Ocean+OR+Pacific"),
}


# ── GRAY-ZONE IMAGERY FEEDS (72h window) ──────────────────────────────────────
GRAY_ZONE_FEEDS = {
    "Taiwan Strait":       _gnews("%22Taiwan+Strait%22+%22median+line%22+OR+%22ADIZ%22+PLA+OR+PLAN"),
    "Scarborough Shoal":   _gnews("%22Scarborough+Shoal%22+OR+%22Bajo+de+Masinloc%22+China+OR+Philippines"),
    "Second Thomas Shoal": _gnews("%22Second+Thomas+Shoal%22+OR+%22Ayungin%22+OR+%22Sierra+Madre%22"),
    "Sandy Cay":           _gnews("%22Sandy+Cay%22+OR+%22Tiexian+Reef%22+China+OR+Philippines"),
    "Spratlys":            _gnews("%22Mischief+Reef%22+OR+%22Fiery+Cross%22+OR+%22Subi+Reef%22+China"),
    "Senkaku":             _gnews("%22Senkaku%22+OR+%22Diaoyu%22+coast+guard+OR+CCG"),
    "AMTI":                _gnews("satellite+imagery+site:amti.csis.org"),
    "ChinaPower imagery":  _gnews("satellite+imagery+site:chinapower.csis.org"),
    "PLA Tracker":         _gnews("PLA+aircraft+OR+ships+median+line+ADIZ+Taiwan"),
}


# ── KEYWORD FILTERS ───────────────────────────────────────────────────────────
CHINA_KEYWORDS = re.compile(
    r"\bchina\b|\bprc\b|\bchinese\b|\bbeijing\b|\bxi\s*jinping\b|\btaiwan\b"
    r"|\bcross[\s-]?strait\b|\bccp\b|\bpla\b|\bpla[an]\b|\bsouth\s*china\s*sea\b"
    r"|\bsenkaku\b|\bdiaoyu\b|\bhong\s*kong\b|\btibet\b|\bxinjiang\b|\buyghur\b"
    r"|\bhuawei\b|\bsmic\b|\bbyd\b|\bcatl\b|\balibaba\b|\btencent\b|\bbytedance\b"
    r"|\bsemiconductor\b.*\b(china|chinese|prc)\b|\bentity\s*list\b|\bcfius\b"
    r"|\b1260h\b|\bsection\s*301\b|\bfentanyl\b.*\b(china|chinese)\b"
    r"|中国|台湾|北京|习近平|共产党|解放军|南海|台海",
    re.IGNORECASE,
)

# Filter out lifestyle/celebrity content (parallel to Korea's K-pop block)
_LIFESTYLE_FILTER = re.compile(
    r"\b(celebrity|gossip|lifestyle|fashion\s*week|movie\s*review|album\s*review"
    r"|red\s*carpet|paparazzi|reality\s*tv|netflix\s*series)\b",
    re.IGNORECASE,
)


# ── PRESTIGE JOURNALIST FLAGGING ──────────────────────────────────────────────
# China / Taiwan / Hong Kong correspondents and beat reporters whose bylines
# raise an item's priority. Matched against the fetched article text (where a
# "By <name>" line usually survives), so a wrong or rotated name simply never
# fires; it cannot introduce an error. Review twice a year.
PRESTIGE_JOURNALISTS = {
    # WSJ
    "Lingling Wei", "Stella Yifan Xie", "Rebecca Feng", "Brian Spegele", "Liza Lin",
    "Jing Yang", "Raffaele Huang", "Clarence Leong", "Yoko Kubota", "Josh Chin",
    "Chun Han Wong", "Wenxin Fan", "Jonathan Cheng", "Liyan Qi", "Jason Douglas",
    "Joyu Wang", "Austin Ramzy", "Elaine Yu", "Dan Strumpf",
    # NYT
    "Keith Bradsher", "Vivian Wang", "David Pierson", "Chris Buckley", "Amy Chang Chien",
    "Alexandra Stevenson", "Daisuke Wakabayashi", "Meaghan Tobin", "Claire Fu",
    "Berry Wang", "Li Yuan", "Ana Swanson", "Edward Wong", "Tiffany May", "Olivia Wang",
    "Zixu Wang", "Joy Dong", "Siyi Zhao", "John Liu", "Amy Qin", "Tripp Mickle",
    # Washington Post
    "Lily Kuo", "Christian Shepherd", "Katrina Northrop", "Vic Chiang", "Eva Dou",
    "Ellen Nakashima", "Cate Cadell", "Pei-Lin Wu", "Shibani Mahtani",
    # Financial Times
    "Joe Leahy", "Cheng Leng", "Ryan McMorrow", "Edward White", "Wenjie Ding", "Sun Yu",
    "Demetri Sevastopulo", "Kathrin Hille", "Thomas Hale", "Eleanor Olcott",
    "William Langley", "Nian Liu", "Zijing Wu", "Arjun Neil Alim", "Chan Ho-him",
    "Gloria Li", "James Kynge", "Kana Inagaki", "Tim Bradshaw", "Andy Lin",
    # Reuters
    "Brenda Goh", "Laurie Chen", "Ryan Woo", "Casey Hall", "Yew Lun Tian", "Ethan Wang",
    "Joe Cash", "Kevin Yao", "Ellen Zhang", "Liz Lee", "Antoni Slodkowski", "Greg Torode",
    "James Pomfret", "Farah Master", "Ben Blanchard", "Yimou Lee", "Michael Martina",
    "David Brunnstrom", "Trevor Hunnicutt", "Karen Freifeld", "Alexandra Alper",
    "Fanny Potkin", "Che Pan", "Eduardo Baptista", "Xiuhao Chen", "Jessie Pang",
    "Clare Jim", "Summer Zhen", "Kane Wu", "Selena Li", "Andrew Hayley",
    # Bloomberg
    "Tom Hancock", "Lucille Liu", "Cindy Wang", "Jenni Marsh", "Sarah Zheng",
    "Philip Glamann", "Jing Li", "Rebecca Choong Wilkins", "Jenny Leonard", "Josh Xiao",
    "Colum Murphy", "Yuan Gao", "Debby Wu", "Mackenzie Hawkins", "Ian Marlow",
    "Peter Martin", "James Mayger", "Josh Wingrove", "Alan Wong", "Katia Dmitrieva",
    "Fran Wang", "Annie Lee", "Chris Anstey", "Shawn Donnan",
    # AP / AFP
    "Ken Moritsugu", "Huizhong Wu", "Simina Mistreanu", "Didi Tang", "Dake Kang",
    "Emily Wang Fujiyama", "Christopher Bodeen", "Johnson Lai", "Kanis Leung",
    "Jim Gomez", "Mari Yamaguchi", "Sam McNeil", "Peter Catterall", "Matthew Walsh",
    # BBC / Guardian / Economist / CNN / CNBC / NPR / Politico / Axios
    "Stephen McDonell", "Laura Bicker", "Tessa Wong", "Kelly Ng", "Fan Wang",
    "Rupert Wingfield-Hayes", "Helen Davidson", "Amy Hawkins", "Chi Hui Lin",
    "Gady Epstein", "Alice Su", "David Rennie", "Nectar Gan", "Simone McCarthy",
    "Steven Jiang", "Joyce Jiang", "Will Ripley", "Ivan Watson", "Evelyn Cheng",
    "Emily Feng", "John Ruwitch", "Phelim Kine", "Bethany Allen",
    # Nikkei / Japan Times / Kyodo / SCMP / Caixin / Straits Times
    "Cissy Zhou", "Tsukasa Hadano", "Katsuji Nakazawa", "Finbarr Bermingham",
    "Dewey Sim", "Amber Wang", "Kinling Lo", "Laura Zhou", "Shi Jiangtao", "Kandy Wong",
    "Minnie Chan", "Lawrence Chung", "Danson Cheong", "Aw Cheng Wei", "Tan Dawn Wei",
    # Specialists / newsletters
    "Bill Bishop", "Kaiser Kuo", "Jordan Schneider", "Zichen Wang",
    "Thomas des Garets Geddes", "Andrew Polk", "Trey McArver", "David Barboza",
    "Dexter Roberts", "Isaac Stone Fish", "Cindy Yu", "Sophia Yan",
    # Taiwan-focused
    "Chris Horton", "Fabian Hamacher", "Ann Wang", "Thompson Chau", "Ralph Jennings",
}


# ── PRESTIGE OUTLETS (item-level flag; the prompt's mandatory-inclusion rule
# keys on this flag, and the validator names any flagged story that was
# collected but never used) ───────────────────────────────────────────────────
PRESTIGE_OUTLET_SOURCES = {
    "WSJ China", "NYT China", "NYT Asia (direct)", "WaPo China", "FT China",
    "Reuters China", "AP China", "AFP China", "Bloomberg China", "Economist China",
    "CNN China", "CNBC China", "Sinocism",
}


# ── EXPERT WATCH-LIST ─────────────────────────────────────────────────────────
# Analysts whose bylines or quotes the digest should surface by name: the
# people the readership already reads. An article that quotes or is written by
# one of them is tagged expert_flag and ranked up; the prompt names them in
# Expert Analysts and Social Statements. Matched by name only; a mismatch is
# harmless. Review twice a year.
EXPERT_WATCHLIST = {
    # CSIS
    "Scott Kennedy", "Bonny Lin", "Jude Blanchette", "Victor Cha", "Gregory Poling",
    "Matthew Funaiole", "Brian Hart", "Ilaria Mazzocco", "Henrietta Levin", "Bonnie Glaser",
    # US think tanks and government alumni
    "Ryan Hass", "Patricia Kim", "Jonathan Czin", "Cheng Li", "Rush Doshi", "Evan Medeiros",
    "Susan Shirk", "Elizabeth Economy", "Oriana Skylar Mastro", "M. Taylor Fravel",
    "Jessica Chen Weiss", "Yun Sun", "Andrew Nathan", "Minxin Pei", "David Shambaugh",
    "Thomas Christensen", "Ely Ratner", "Matt Pottinger", "Kurt Campbell", "Daniel Rosen",
    "Adam Segal", "Ian Johnson", "Zack Cooper", "Dan Wang", "Kevin Rudd", "Graham Allison",
    "Michael Beckley", "Hal Brands", "Elbridge Colby", "Rick Waters", "Zongyuan Zoe Liu",
    "Yasheng Huang", "Barry Naughton", "Nicholas Lardy", "Arthur Kroeber", "Logan Wright",
    "Michael Pettis", "Victor Shih", "Yuen Yuen Ang", "Joseph Torigian", "Lyle Goldstein",
    "Isaac Kardon", "Thomas Shugart", "Lonnie Henley", "Joel Wuthnow", "Phillip Saunders",
    "Oriana Mastro", "Sheena Chestnut Greitens", "Jacob Stokes", "Lisa Curtis", "Emily Kilcrease",
    "Gregory Allen", "Chris Miller", "Paul Triolo", "Kevin Xu", "Jordan Schneider",
    "Emily Weinstein", "Matt Sheehan", "Kaiser Kuo", "Bill Bishop", "Dexter Roberts",
    "Andrew Polk", "Trey McArver", "Chris Johnson", "Danny Russel", "Wendy Cutler",
    "Craig Singleton", "Jonathan Ward", "Michael Sobolik", "Derek Scissors", "Zack Cooper",
    "Mira Rapp-Hooper", "Ryan Fedasiuk", "Elsa Kania", "Lingling Wei", "Jeremy Wallace",
    "Neil Thomas", "Lizzi Lee", "Kevin Slaten", "Brad Setser", "Gerard DiPippo",
    "Jeffrey Ding", "Julian Gewirtz", "Melanie Hart", "Andrew Erickson", "Toshi Yoshihara",
    "Michael Swaine", "Amy Celico", "Ali Wyne", "Thomas Wright", "Charles Edel", "Zack Cooper",
    # Taiwan, Japan, Australia, Europe, India
    "Lai I-chung", "Wen-Ti Sung", "Lev Nachman", "Kharis Templeman", "Chong-Pin Lin",
    "Su Tzu-yun", "Ryo Sahashi", "Akio Takahara", "Bethany Allen", "Michael Shoebridge",
    "Peter Jennings", "Rory Medcalf", "Richard McGregor", "Mikko Huotari", "Helena Legarda",
    "Nis Grünberg", "Jacob Gunter", "Noah Barkin", "Alicia Garcia-Herrero", "Andrew Small",
    "Reinhard Bütikofer", "Steve Tsang", "Kerry Brown", "George Magnus", "Charles Parton",
    "Tanvi Madan", "C. Raja Mohan", "Manoj Kewalramani", "Harsh Pant",
    # Chinese scholars and former officials frequently quoted in English and ZH press
    "Wang Jisi", "Jia Qingguo", "Yan Xuetong", "Shi Yinhong", "Zhu Feng", "Wu Xinbo",
    "Da Wei", "Cui Tiankai", "Fu Ying", "Ruan Zongze", "Zhao Minghao", "Wang Wen",
    "Hu Xijin", "Jin Canrong", "Zheng Yongnian", "Wang Huiyao", "Henry Huiyao Wang",
    "Zhou Bo", "Shen Dingli", "Xie Tao", "Liu Yawei", "Tao Wenzhao", "Wang Yiwei",
    "Huang Jing", "Yu Jie", "Sun Yun", "Zhang Weiwei", "Li Cheng", "Wang Dong",
    "Shi Yuzhi", "Ni Feng", "Yuan Zheng", "Lu Xiang", "Diao Daming", "Teng Jianqun",
    "王缉思", "贾庆国", "阎学通", "时殷弘", "朱锋", "吴心伯", "达巍", "崔天凯", "傅莹",
    "阮宗泽", "赵明昊", "王文", "胡锡进", "金灿荣", "郑永年", "王辉耀", "周波", "沈丁立",
    "王义桅", "张维为", "刁大明", "倪峰", "袁征", "吕祥", "滕建群",
}


# ── INFRASTRUCTURE ────────────────────────────────────────────────────────────
REQUEST_TIMEOUT = 8
HEADERS = {"User-Agent": "CSISChinaDigest/1.0"}
MAX_WORKERS = 25
FEED_HEALTH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feed_health.json")
DEAD_FEED_RUNS = 5          # consecutive empty runs before a feed is reported dead

_source_health: dict[str, dict] = {}
MAJOR_FEEDS = {"Reuters China", "AP China", "WSJ China", "FT China",
               "Bloomberg China", "SCMP", "NYT China", "Xinhua English"}


# Google News occasionally returns the outlet's homepage meta description as the
# summary ("The latest news and analysis from ...") instead of the story blurb.
# Passed through, that text misleads the model about what the article says.
_BOILERPLATE_RE = re.compile(
    r"^(the latest|breaking news|get the latest|read the latest|news, analysis|"
    r"stay informed|subscribe|sign up|your (daily|trusted) source|all the latest|"
    r"comprehensive up-to-date|we use cookies|find out more)",
    re.IGNORECASE,
)


def _clean_summary(summary: str, title: str = "") -> str:
    s = (summary or "").strip()
    if not s:
        return ""
    if _BOILERPLATE_RE.search(s):
        return ""
    # A summary that merely repeats the title carries no information.
    if title and s.lower().rstrip(".") == title.lower().rstrip("."):
        return ""
    return s


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _parse_feed(url: str) -> list:
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers=HEADERS)
            if resp.status_code in (401, 403):
                print(f"  ⚠ Feed blocked ({resp.status_code}): {url[:80]}")
                return []
            resp.raise_for_status()
            return feedparser.parse(resp.content).entries
        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            print(f"  ⚠ Feed error (after 3 tries): {e}")
            return []
        except Exception as e:
            print(f"  ⚠ Feed error: {e}")
            return []
    return []


def _real_url_from_gnews_entry(entry, gnews_link: str, raw_summary: str) -> str:
    """Extract the real article URL from a Google News RSS entry.

    Tries three methods in order:
    1. feedparser's parsed links list (rel=alternate with non-Google href)
    2. First non-Google href in summary HTML (handles both quote styles + &amp;)
    3. Falls back to the original Google News redirect URL
    """
    # Method 1 — feedparser alternate links
    for lk in (getattr(entry, "links", None) or []):
        href = lk.get("href", "")
        if href and href.startswith("http") and "news.google.com" not in href:
            return href

    # Method 2 — first non-Google href in summary HTML
    if raw_summary:
        m = re.search(r"""href=["'](https?://(?!news\.google\.com)[^"'<>\s]+)""", raw_summary)
        if m:
            return m.group(1).replace("&amp;", "&").replace("&#38;", "&")

    return gnews_link  # fallback — Google News URL (better than empty)


def _entry_to_article(entry, source: str, lang: str = "EN",
                      extra: dict | None = None) -> dict:
    title = entry.get("title", "").strip()
    raw_link = entry.get("link", "").strip()
    raw_summary = entry.get("summary", entry.get("description", ""))

    # For Google News redirect URLs, try to extract the real article URL
    link = (_real_url_from_gnews_entry(entry, raw_link, raw_summary)
            if "news.google.com" in raw_link else raw_link)

    summary = re.sub(r"<[^>]+>", " ", raw_summary)
    summary = re.sub(r"\s+", " ", summary).strip()
    # Google News search entries put "<title> - <source>" in the title and the
    # same string again in the summary; strip the outlet suffix from the title.
    if "news.google.com" in raw_link:
        title = re.sub(r"\s+-\s+[^-]{2,60}$", "", title).strip() or title
    summary = _clean_summary(summary, title)

    pub_date = None
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            pub_date = datetime(*parsed[:6], tzinfo=timezone.utc).isoformat()
            break

    tags = []
    for tag in getattr(entry, "tags", []) or []:
        term = tag.get("term", "").strip()
        if term:
            tags.append(term)

    article = {
        "title": title,
        "url": link,
        "summary": summary[:800],
        "source": source,
        "lang": lang,
        "pub_date": pub_date,
    }
    if source in PRESTIGE_OUTLET_SOURCES:
        article["prestige_outlet"] = True
    if tags:
        article["tags"] = tags
    if extra:
        article.update(extra)
    return article


def _is_recent(entry, hours: int = 48, strict: bool = False) -> bool:
    """True if the entry was published inside the window.

    strict=True rejects entries with no parseable date. Used for the analysis
    and academic tiers, where the Korea brief found that undated think-tank
    pages (an old AEI essay, a 2021 THAAD paper) were surfacing as today's
    commentary: a missing date fools a date filter but not a reader.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            return datetime(*parsed[:6], tzinfo=timezone.utc) >= cutoff
    return not strict


def _is_china_related(entry) -> bool:
    text = f"{entry.get('title', '')} {entry.get('summary', entry.get('description', ''))}"
    return bool(CHINA_KEYWORDS.search(text))


def _is_lifestyle(entry) -> bool:
    text = f"{entry.get('title', '')} {entry.get('summary', entry.get('description', ''))}"
    return bool(_LIFESTYLE_FILTER.search(text))


def _flag_journalist(article: dict) -> dict:
    text = f"{article['title']} {article['summary']}".lower()
    for name in PRESTIGE_JOURNALISTS:
        if name.lower() in text:
            article["flagged_journalist"] = name
            break
    return article


def _flag_expert(article: dict) -> dict:
    """Tag articles written by or quoting a watch-list expert (see EXPERT_WATCHLIST)."""
    text = f"{article.get('title', '')} {article.get('summary', '')}"
    low = text.lower()
    hits = []
    for name in EXPERT_WATCHLIST:
        needle = name if not name.isascii() else name.lower()
        hay = text if not name.isascii() else low
        if needle in hay:
            hits.append(name)
            if len(hits) >= 3:
                break
    if hits:
        article["expert_flag"] = hits
    return article


def flag_experts(articles: list) -> list:
    for a in articles:
        _flag_expert(a)
    return articles


def _title_key(title: str) -> str:
    """Normalised headline for cross-feed dedup (the same wire story arrives via
    several Google News queries under different source labels)."""
    t = re.sub(r"[^a-z0-9一-鿿 ]+", " ", (title or "").lower())
    return re.sub(r"\s+", " ", t).strip()[:120]


def _dedup(articles: list) -> list:
    seen_urls: set = set()
    seen_titles: set = set()
    out = []
    for a in articles:
        url = a.get("url") or ""
        tk = _title_key(a.get("title", ""))
        if not url or url in seen_urls:
            continue
        if tk and len(tk) > 25 and tk in seen_titles:
            continue
        seen_urls.add(url)
        if tk:
            seen_titles.add(tk)
        out.append(a)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# PARALLEL FEED FETCHER
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_feeds_parallel(feed_dict: dict, is_tiered: bool = False) -> dict:
    """Fetch all feeds in parallel. Returns {source: (entries, extra_info)}.
    Records per-source health in module-level _source_health."""
    results = {}

    def _fetch_one(source, url_or_tuple):
        if is_tiered:
            url, tier_val = url_or_tuple
        else:
            url = url_or_tuple
            tier_val = None
        entries = _parse_feed(url)
        used_fallback = False
        if not entries and source in _FALLBACK:
            fb_entries = _parse_feed(_FALLBACK[source])
            if fb_entries:
                entries, used_fallback = fb_entries, True
        return source, entries, tier_val, used_fallback

    items = list(feed_dict.items())
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_one, src, val): src for src, val in items}
        for future in as_completed(futures):
            src = futures[future]
            try:
                source, entries, tier_val, used_fallback = future.result()
                results[source] = (entries, tier_val)
                _source_health[source] = {
                    "articles": len(entries),
                    "success": len(entries) > 0,
                    "used_fallback": used_fallback,
                    "error_msg": None,
                }
            except Exception as e:
                print(f"  ⚠ Thread error: {e}")
                _source_health[src] = {
                    "articles": 0,
                    "success": False,
                    "error_msg": str(e),
                }

    return results


# ─────────────────────────────────────────────────────────────────────────────
# TIER COLLECTORS
# ─────────────────────────────────────────────────────────────────────────────

# Chinese-language sources are tagged lang="ZH"; the model translates titles.
_CHINESE_LANG_SOURCES: set[str] = {s for s in list(TIER1_FEEDS) + list(TIER4_FEEDS) + list(TIER2_FEEDS)
                                   if "ZH)" in s}


def _cap_zh(articles: list) -> list:
    """Keep at most ZH_PER_SOURCE_CAP newest items per Chinese-language feed."""
    counts: dict[str, int] = {}
    out = []
    for a in sorted(articles, key=lambda x: x.get("pub_date") or "", reverse=True):
        if a.get("lang") == "ZH":
            src = a.get("source", "")
            counts[src] = counts.get(src, 0) + 1
            if counts[src] > ZH_PER_SOURCE_CAP:
                continue
        out.append(a)
    return out


def _collect_tier1() -> list:
    articles = []
    results = _fetch_feeds_parallel(TIER1_FEEDS)
    for source, (entries, _) in results.items():
        lang = "ZH" if source in _CHINESE_LANG_SOURCES else "EN"
        for entry in entries:
            if not _is_recent(entry, hours=24):
                continue
            # PRC-language state media is China-related by construction; the
            # English keyword gate would drop most of it.
            if lang != "ZH" and not _is_china_related(entry):
                continue
            if _is_lifestyle(entry):
                continue
            article = _entry_to_article(entry, source, lang=lang)
            article = _flag_journalist(article)
            article = _flag_expert(article)
            articles.append(article)
    return _cap_zh(_dedup(articles))


def _collect_tier2() -> list:
    articles = []
    results = _fetch_feeds_parallel(TIER2_FEEDS, is_tiered=True)
    for source, (entries, prestige) in results.items():
        for entry in entries:
            if not _is_recent(entry, hours=36, strict=True):
                continue
            if not _is_china_related(entry):
                continue
            lang = "ZH" if "(ZH)" in source else "EN"
            article = _entry_to_article(entry, source, lang=lang, extra={
                "prestige_tier": prestige,
                "china_primary": prestige == "A",
                "china_based": "(ZH)" in source or source in ("中美聚焦 China-US Focus", "CGTN Think Tank"),
            })
            article = _flag_expert(article)
            articles.append(article)
    return _cap_zh(_dedup(articles))


def _collect_tier3() -> list:
    articles = []
    results = _fetch_feeds_parallel(TIER3_FEEDS, is_tiered=True)
    for source, (entries, tier) in results.items():
        for entry in entries:
            if not _is_recent(entry, hours=72, strict=True):
                continue
            if not _is_china_related(entry):
                continue
            text = f"{entry.get('title', '')} {entry.get('summary', entry.get('description', ''))}".lower()
            academic_signals = ("journal", "paper", "study", "research", "analysis",
                                "findings", "abstract", "doi", "vol.", "issue",
                                source.lower())
            if not any(s in text for s in academic_signals):
                continue
            article = _entry_to_article(entry, source, extra={"journal_tier": tier})
            articles.append(article)
    return _dedup(articles)


def _collect_tier4() -> list:
    """PRC primary / propaganda — Xinhua, People's Daily, MOFA presser, Xi/Wang statements."""
    articles = []
    results = _fetch_feeds_parallel(TIER4_FEEDS)
    for source, (entries, _) in results.items():
        lang = "ZH" if source in _CHINESE_LANG_SOURCES else "EN"
        for entry in entries:
            if not _is_recent(entry, hours=48):
                continue
            article = _entry_to_article(entry, source, lang=lang)
            if lang == "ZH":
                article["government_primary"] = True
            articles.append(article)
    return _cap_zh(_dedup(articles))


def _collect_xi_tracker() -> list:
    """Collect recent Xi Jinping appearance/activity reports."""
    articles = []
    results = _fetch_feeds_parallel(XI_TRACKER_FEEDS)
    for source, (entries, _) in results.items():
        for entry in entries:
            if not _is_recent(entry, hours=72):
                continue
            article = _entry_to_article(entry, source, lang="EN")
            articles.append(article)
    return _dedup(articles)


def _collect_hidden_reach() -> list:
    """Collect Hidden Reach-relevant articles (overseas ports, dual-use facilities)."""
    articles = []
    results = _fetch_feeds_parallel(HIDDEN_REACH_FEEDS)
    for source, (entries, _) in results.items():
        for entry in entries:
            if not _is_recent(entry, hours=72):
                continue
            article = _entry_to_article(entry, source, lang="EN")
            articles.append(article)
    return _dedup(articles)


def _collect_gray_zone() -> list:
    """Collect Gray-Zone imagery / incursion articles (Taiwan Strait, SCS, Senkaku)."""
    articles = []
    results = _fetch_feeds_parallel(GRAY_ZONE_FEEDS)
    for source, (entries, _) in results.items():
        for entry in entries:
            if not _is_recent(entry, hours=72):
                continue
            article = _entry_to_article(entry, source, lang="EN")
            articles.append(article)
    return _dedup(articles)


# ─────────────────────────────────────────────────────────────────────────────
# PROPAGANDA SUMMARY (Xinhua / People's Daily)
# ─────────────────────────────────────────────────────────────────────────────

_DIRECT_PROP_SOURCES = {"Xinhua English", "People's Daily EN", "Global Times",
                        "China Daily", "China Daily Front", "CGTN"}

_PROP_TITLE_PATTERNS = re.compile(
    r"Xinhua|People's Daily|Global Times|Foreign Ministry spokesperson|"
    r"Mao Ning|Lin Jian|Wang Wenbin|Xi Jinping said|Wang Yi said|"
    r"Beijing\s+(said|says|reported|reports|announced|claims)",
    re.IGNORECASE,
)


def _build_xinhua_summary(tier4_articles: list) -> dict:
    """Structured summary of today's PRC propaganda output for the digest prompt."""
    all_titles = set()
    categories = {}
    sources = {}
    direct_count = 0
    indirect_count = 0

    for art in tier4_articles:
        title = art.get("title", "").strip()
        if title:
            all_titles.add(title.lower())
        src = art.get("source", "Unknown")
        sources[src] = sources.get(src, 0) + 1
        if src in _DIRECT_PROP_SOURCES:
            direct_count += 1
        else:
            indirect_count += 1
        for tag in art.get("tags", []):
            categories[tag] = categories.get(tag, 0) + 1
        if src not in _DIRECT_PROP_SOURCES:
            text = f"{title} {art.get('summary', '')}".lower()
            if _PROP_TITLE_PATTERNS.search(text):
                categories["PRC-cited"] = categories.get("PRC-cited", 0) + 1

    headlines = []
    for art in tier4_articles[:50]:
        title = art.get("title", "")
        if title:
            src = art.get("source", "")
            if src not in _DIRECT_PROP_SOURCES and src:
                tag_str = f"via {src}"
            else:
                tag_str = src
            headlines.append(f"[{tag_str}] {title}")

    return {
        "total_articles": len(all_titles),
        "direct_count": direct_count,
        "indirect_count": indirect_count,
        "categories": dict(sorted(categories.items(), key=lambda x: -x[1])),
        "sources": sources,
        "headlines": headlines[:50],
    }


# ─────────────────────────────────────────────────────────────────────────────
# MARKET DATA
# ─────────────────────────────────────────────────────────────────────────────

def _collect_markets() -> dict:
    """Fetch China market strip with Yahoo primary + Stooq fallback.

    Symbols:
      - SSE Composite (Shanghai)
      - Hang Seng (Hong Kong)
      - USD/CNY onshore
      - USD/CNH offshore
      - 10Y CGB yield
      - Brent crude
      - PBOC LPR (1Y and 5Y)
      - China 5Y CDS
      - GDP estimate
      - Macro indicators (CPI, PPI, PMI, retail)
    """
    YAHOO_SYMBOLS = {
        "sse_composite": "000001.SS",
        "hang_seng":     "^HSI",
        "usd_cny":       "CNY=X",
        "usd_cnh":       "CNH=X",
        "brent":         "BZ=F",
    }
    STOOQ_SYMBOLS = {
        "sse_composite": "^shc",
        "hang_seng":     "^hsi",
        "usd_cny":       "usdcny",
        "usd_cnh":       "usdcnh",
        "brent":         "cb.f",
    }
    _SANITY_RANGES = {
        "sse_composite": (1500, 6500),
        "hang_seng":     (10000, 35000),
        "usd_cny":       (5.5, 9.0),
        "usd_cnh":       (5.5, 9.0),
        "brent":         (40, 200),
    }

    def _format_value(key, price):
        if key in ("sse_composite", "hang_seng"):
            return f"{price:,.2f}"
        return f"{price:.4f}" if "usd_" in key else f"{price:.2f}"

    def _validate(key, price, mkt_time):
        lo, hi = _SANITY_RANGES.get(key, (0, float("inf")))
        if not price or price < lo or price > hi:
            return False, f"price {price} outside sanity range ({lo}-{hi})"
        if mkt_time:
            age_days = (datetime.now(timezone.utc) - mkt_time).days
            if age_days > 5:
                return False, f"data is {age_days} days old"
        return True, ""

    def _fetch_yahoo(key):
        symbol = YAHOO_SYMBOLS[key]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        }
        for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
            try:
                url = f"https://{host}/v8/finance/chart/{symbol}?range=5d&interval=1d"
                resp = requests.get(url, timeout=10, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                meta = data["chart"]["result"][0]["meta"]
                price = meta.get("regularMarketPrice", 0)
                prev_close = meta.get("chartPreviousClose",
                                      meta.get("previousClose", price))
                mkt_ts = meta.get("regularMarketTime", 0)
                mkt_time = (datetime.fromtimestamp(mkt_ts, tz=timezone.utc)
                            if mkt_ts else None)
                ok, reason = _validate(key, price, mkt_time)
                if not ok:
                    print(f"  ⚠ {key}: Yahoo {host} {reason}")
                    continue
                change_pct = (((price - prev_close) / prev_close * 100)
                              if prev_close else 0)
                return {
                    "value": _format_value(key, price),
                    "change_pct": round(change_pct, 2),
                    "as_of": mkt_time.strftime("%b %d") if mkt_time else "",
                }
            except (requests.RequestException, KeyError, ValueError, TypeError) as e:
                print(f"  ⚠ {key}: Yahoo {host} error: {e}")
                continue
        return None

    def _fetch_stooq(key):
        import csv as _csv
        import io as _io
        symbol = STOOQ_SYMBOLS[key]
        try:
            url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
            resp = requests.get(url, timeout=10,
                                headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            text = resp.text.strip()
            if not text or "no data" in text.lower():
                return None
            reader = _csv.DictReader(_io.StringIO(text))
            rows = [r for r in reader if r.get("Close")]
            if len(rows) < 2:
                return None
            latest = rows[-1]
            prev = rows[-2]
            price = float(latest["Close"])
            prev_close = float(prev["Close"])
            try:
                latest_dt = datetime.strptime(
                    latest["Date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except (ValueError, KeyError):
                latest_dt = None
            ok, reason = _validate(key, price, latest_dt)
            if not ok:
                print(f"  ⚠ {key}: Stooq {reason}")
                return None
            change_pct = (((price - prev_close) / prev_close * 100)
                          if prev_close else 0)
            return {
                "value": _format_value(key, price),
                "change_pct": round(change_pct, 2),
                "as_of": latest_dt.strftime("%b %d") if latest_dt else "",
            }
        except (requests.RequestException, KeyError, ValueError, TypeError) as e:
            print(f"  ⚠ {key}: Stooq error: {e}")
            return None

    def _fetch_symbol(key):
        result = _fetch_yahoo(key)
        if result:
            return key, result
        print(f"  ↻ {key}: Yahoo failed — falling back to Stooq")
        result = _fetch_stooq(key)
        if result:
            return key, result
        return key, {"value": "—", "change_pct": 0, "as_of": ""}

    result = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        symbol_futures = {pool.submit(_fetch_symbol, k): k
                          for k in YAHOO_SYMBOLS.keys()}
        cgb_f = pool.submit(_fetch_10y_cgb)
        lpr_f = pool.submit(_fetch_pboc_lpr)
        cds_f = pool.submit(_fetch_china_cds)
        gdp_f = pool.submit(_fetch_china_gdp)
        macro_f = pool.submit(_fetch_china_macro)

        for future in as_completed(symbol_futures):
            k, v = future.result()
            result[k] = v

        result["cgb_10y"]      = cgb_f.result()
        result["pboc_lpr"]     = lpr_f.result()
        result["china_cds"]    = cds_f.result()
        result["gdp_yoy"] = gdp_f.result()

        macro = macro_f.result()
        if macro:
            result["china_macro"] = macro

    return result


# Market figures that could not be fetched are reported as unavailable. The
# previous fallbacks (10Y CGB 1.75%, LPR 3.0/3.5, CDS 70 bps, GDP 4.5% Q1 2026)
# were hard-coded numbers injected into the prompt as "pre-collected data" and
# rendered in the market strip without an as-of date. On the August 17 run all
# three used the fallback, so the strip would have shown invented figures. The
# Australia brief's rule applies: a blank beats a fabricated number.
_UNAVAILABLE = {"value": "—", "change_pct": 0, "as_of": "", "unavailable": True}


def _fetch_10y_cgb() -> dict:
    """Fetch China 10-year government bond yield."""
    try:
        url = "https://www.worldgovernmentbonds.com/country/china/"
        resp = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        if resp.ok:
            match = re.search(
                r'10\s*[Yy]ears?.*?(\d+\.\d{2,3})\s*%',
                resp.text,
                re.DOTALL
            )
            if match:
                return {"value": f"{float(match.group(1)):.2f}%",
                        "as_of": datetime.now(timezone.utc).strftime("%b %d")}
    except Exception as e:
        print(f"  ⚠ 10Y CGB fetch error: {e}")
    print("  ⚠ 10Y CGB: not collected (shown as unavailable, never a stale number)")
    return _UNAVAILABLE.copy()


def _fetch_pboc_lpr() -> dict:
    """Fetch PBOC Loan Prime Rate (1Y and 5Y). Fixed monthly on the 20th."""
    try:
        url = _gnews("%22Loan+Prime+Rate%22+OR+%22LPR%22+China+%22kept+unchanged%22+OR+%22cut%22")
        entries = _parse_feed(url)
        for entry in entries[:5]:
            text = f"{entry.get('title', '')} {entry.get('summary', '')}"
            ms = re.findall(r"(\d\.\d{2})\s*(?:%|percent)", text)
            if len(ms) >= 2:
                return {"lpr_1y": f"{ms[0]}%", "lpr_5y": f"{ms[1]}%",
                        "as_of": datetime.now(timezone.utc).strftime("%b %d")}
    except Exception as e:
        print(f"  ⚠ PBOC LPR fetch error: {e}")
    print("  ⚠ PBOC LPR: not collected (shown as unavailable, never a stale number)")
    return {"lpr_1y": "—", "lpr_5y": "—", "as_of": "", "unavailable": True}


def _fetch_china_cds() -> dict:
    """Fetch China 5-year sovereign CDS spread (bps)."""
    try:
        url = "https://www.worldgovernmentbonds.com/cds-historical-data/china/5-years/"
        resp = requests.get(url, timeout=12, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        if resp.ok:
            matches = re.findall(
                r'<td[^>]*>\s*(\d{1,2}\s+\w+\s+\d{4})\s*</td>\s*<td[^>]*>\s*([\d.]+)\s*</td>',
                resp.text
            )
            if len(matches) >= 2:
                latest_date, latest_val = matches[0]
                _, prev_val = matches[1]
                spread = float(latest_val)
                prev_spread = float(prev_val)
                change = spread - prev_spread
                as_of = ""
                try:
                    as_of = datetime.strptime(latest_date.strip(), "%d %B %Y").strftime("%b %d")
                except ValueError:
                    pass
                return {"value": f"{spread:.0f}", "change_bps": round(change, 1), "as_of": as_of}
    except Exception as e:
        print(f"  ⚠ China CDS fetch error: {e}")
    print("  ⚠ China 5Y CDS: not collected (shown as unavailable, never a stale number)")
    return {"value": "—", "change_bps": 0, "as_of": "", "unavailable": True}


def _fetch_china_gdp() -> dict:
    """Fetch latest China GDP growth (quarterly year-on-year)."""
    try:
        url = _gnews("China+GDP+%22year-on-year%22+OR+%22year+on+year%22+%22Q%22")
        entries = _parse_feed(url)
        for entry in entries[:5]:
            text = f"{entry.get('title', '')} {entry.get('summary', '')}"
            m = re.search(r"(\d\.\d)\s*(?:%|percent).*?(?:year-on-year|year on year|YoY)", text, re.IGNORECASE)
            if m:
                return {"value": f"{m.group(1)}%", "period": "latest Q",
                        "source": "Reuters/NBS"}
    except Exception:
        pass
    print("  ⚠ China GDP: not collected (shown as unavailable, never a stale number)")
    return {"value": "—", "period": "", "source": "", "unavailable": True}


def _fetch_china_macro() -> dict | None:
    """Fetch additional macro indicators (CPI, PPI, PMI, retail) — best-effort."""
    indicators = {}
    queries = {
        "cpi_yoy":     "China+CPI+%22year-on-year%22+%22consumer+prices%22",
        "ppi_yoy":     "China+PPI+%22year-on-year%22+%22producer+prices%22",
        "pmi_mfg":     "China+%22manufacturing+PMI%22+OR+%22Caixin+manufacturing%22",
        "retail":      "China+%22retail+sales%22+%22year-on-year%22",
    }
    for key, q in queries.items():
        try:
            entries = _parse_feed(_gnews(q))
            for entry in entries[:3]:
                text = f"{entry.get('title', '')} {entry.get('summary', '')}"
                if key in ("cpi_yoy", "ppi_yoy", "retail"):
                    m = re.search(r"(-?\d\.\d)\s*(?:%|percent)", text)
                    if m:
                        v = float(m.group(1))
                        sign = "+" if v >= 0 else "-"
                        indicators[key] = f"{sign}{abs(v):.1f}%"
                        break
                elif key == "pmi_mfg":
                    m = re.search(r"\b(4[0-9]|5[0-9])\.\d\b", text)
                    if m:
                        indicators[key] = m.group(0)
                        break
        except Exception:
            continue
    return indicators if indicators else None


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def collect_all() -> dict:
    """Run the full collection. Returns the payload dict for digest.py."""
    print("\n📡 China Daily Brief — Collector")
    print("=" * 60)

    t0 = time.time()

    print("\n🔍 Tier 1: News (24h window)...")
    tier1 = _collect_tier1()
    print(f"  ✔ {len(tier1)} articles from {len({a['source'] for a in tier1})} sources")

    print("\n🔍 Tier 2: Analysis (36h window)...")
    tier2 = _collect_tier2()
    print(f"  ✔ {len(tier2)} articles from {len({a['source'] for a in tier2})} sources")

    print("\n🔍 Tier 3: Academic (72h window)...")
    tier3 = _collect_tier3()
    print(f"  ✔ {len(tier3)} articles from {len({a['source'] for a in tier3})} sources")

    print("\n🔍 Tier 4: PRC Primary (48h window)...")
    tier4 = _collect_tier4()
    print(f"  ✔ {len(tier4)} articles from {len({a['source'] for a in tier4})} sources")

    print("\n🔍 Xi appearance tracker (72h window)...")
    xi_articles = _collect_xi_tracker()
    print(f"  ✔ {len(xi_articles)} Xi-related articles")

    print("\n🔍 Hidden Reach feeds (72h window)...")
    hr_articles = _collect_hidden_reach()
    print(f"  ✔ {len(hr_articles)} overseas-footprint articles")

    print("\n🔍 Gray-Zone feeds (72h window)...")
    gz_articles = _collect_gray_zone()
    print(f"  ✔ {len(gz_articles)} gray-zone articles")

    print("\n💹 Market data...")
    markets = _collect_markets()
    print(f"  ✔ {sum(1 for v in markets.values() if v)} indicators")

    print("\n📊 Propaganda summary...")
    prop_summary = _build_xinhua_summary(tier4)
    print(f"  ✔ {prop_summary['total_articles']} unique propaganda articles "
          f"({prop_summary['direct_count']} direct, {prop_summary['indirect_count']} indirect)")

    elapsed = time.time() - t0
    print(f"\n⏱ Collection completed in {elapsed:.1f}s")

    feed_report = _update_feed_health(_source_health)

    payload = {
        "tier1": tier1,
        "tier2": tier2,
        "tier3": tier3,
        "tier4": tier4,
        "xi_tracker_articles": xi_articles,
        "hidden_reach_articles": hr_articles,
        "gray_zone_articles": gz_articles,
        "market_indicators": markets,
        "xinhua_summary": prop_summary,
        "source_health": _source_health,
        "feed_report": feed_report,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# FEED HEALTH LEDGER
# ─────────────────────────────────────────────────────────────────────────────

def _update_feed_health(health: dict) -> dict:
    """Persist per-feed consecutive-empty counts and report dead feeds.

    A feed returning zero entries is non-fatal by design, which is also why
    nobody notices when it has been returning zero for a month. This ledger
    (feed_health.json, committed by the workflow) turns silent rot into a
    named list in the run log and the README.
    """
    ledger = {}
    try:
        with open(FEED_HEALTH_FILE, "r", encoding="utf-8") as f:
            ledger = json.load(f)
        if not isinstance(ledger, dict):
            ledger = {}
    except (OSError, json.JSONDecodeError):
        ledger = {}

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dead, fallback_used, major_empty = [], [], []
    for source, info in health.items():
        rec = ledger.get(source) or {"empty_runs": 0, "last_ok": None, "last_count": 0}
        if info.get("success"):
            rec["empty_runs"] = 0
            rec["last_ok"] = today
        else:
            rec["empty_runs"] = int(rec.get("empty_runs", 0)) + 1
        rec["last_count"] = int(info.get("articles", 0))
        rec["last_seen"] = today
        if info.get("used_fallback"):
            rec["fallback"] = today
            fallback_used.append(source)
        ledger[source] = rec
        if rec["empty_runs"] >= DEAD_FEED_RUNS:
            dead.append(f"{source} ({rec['empty_runs']} runs)")
        if source in MAJOR_FEEDS and not info.get("success"):
            major_empty.append(source)

    try:
        with open(FEED_HEALTH_FILE, "w", encoding="utf-8") as f:
            json.dump(ledger, f, ensure_ascii=False, indent=1, sort_keys=True)
    except OSError as e:
        print(f"  ⚠ feed_health.json not written: {e}")

    ok = sum(1 for v in health.values() if v.get("success"))
    print(f"\n📶 Feed health: {ok}/{len(health)} feeds returned entries")
    if major_empty:
        print(f"  ⚠ MAJOR feeds empty this run: {', '.join(sorted(major_empty))}")
    if fallback_used:
        print(f"  ↻ Direct feed empty, Google News fallback used: {', '.join(sorted(fallback_used))}")
    if dead:
        print(f"  ✖ Dead feeds (≥{DEAD_FEED_RUNS} consecutive empty runs): {', '.join(sorted(dead))}")

    return {
        "feeds_total": len(health),
        "feeds_ok": ok,
        "major_empty": sorted(major_empty),
        "fallback_used": sorted(fallback_used),
        "dead": sorted(dead),
    }


if __name__ == "__main__":
    out = collect_all()
    with open("collected.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    total = sum(len(v) for k, v in out.items() if isinstance(v, list))
    print(f"\n💾 Wrote collected.json ({total} articles total)")

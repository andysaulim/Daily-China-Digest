"""Render a representative brief to preview.html for the visual check.

test_render_visual.py measures computed style in a real browser — contrast,
typeface count, horizontal overflow — and none of that is visible by reading
the HTML. It needs a page to measure, and nothing produced one, so the check
existed and never ran.

This builds a digest that exercises every section, so the measurement covers
the whole brief rather than whatever happened to be in the news.

    python3 preview.py && BRIEF_HTML=preview.html python3 test_render_visual.py
"""
import pathlib
import render

DIGEST = {'also_today': [{'body_text': 'Exports softened.',
                 'category': 'trade',
                 'headline': 'Customs reports narrower surplus',
                 'source': 'Caixin',
                 'url': 'https://example.org/6'},
                {'body_text': 'Comment period 30 days.',
                 'category': 'tech',
                 'headline': 'Draft AI labelling rules published',
                 'source': 'Xinhua',
                 'url': 'https://example.org/7'}],
 'calendar_watch': [{'confirmed': True,
                     'date': '2026-09-12',
                     'day': 12,
                     'detail': 'First since the pact.',
                     'event': 'PIF leaders meet',
                     'headline': 'PIF leaders meet',
                     'month': 'Sep',
                     'why_it_matters': 'First since the pact.'}],
 'key_stat': {'context': 'Third straight quarter above target pace.',
              'label': 'Q2 GDP growth, year on year',
              'number': '4.8%',
              'source': 'National Bureau of Statistics'},
 'market_indicators': {'brent': {'change_pct': -1.1, 'value': '72.40'},
                       'hang_seng': {'change_pct': -0.3, 'value': '18,220.10'},
                       'sse_composite': {'change_pct': 1.2, 'value': '3,412.55'},
                       'usd_cny': {'change_pct': 0.02, 'value': '7.1204'}},
 'morning_memo': ['MOFCOM opened an anti-dumping investigation into EU pork.',
                  'The SSE Composite rose *1.2 percent*.',
                  '**Wang Yi** travels to Jakarta on Thursday.'],
 'overnight_items': [{'body_text': 'Effective 1 October.',
                      'category': 'Trade',
                      'headline': 'Rare-earth export licences tightened',
                      'source': 'Reuters',
                      'url': 'https://example.org/3'},
                     {'body_text': 'Mature nodes lead.',
                      'category': 'Tech',
                      'headline': 'SMIC reports higher utilisation',
                      'source': 'SCMP',
                      'url': 'https://example.org/4'},
                     {'body_text': 'Fourteen aircraft tracked.',
                      'category': 'Cross-Strait',
                      'headline': 'PLA sorties cross the median line',
                      'source': 'Focus Taiwan',
                      'url': 'https://example.org/5'}],
 'pdf_url': 'https://example.org/digest_2026-09-09.pdf',
 're_line': 'MOFCOM opens EU pork probe · SSE rallies · Politburo meets Friday',
 'top_stories': [{'body': 'Filed by the domestic industry association, the probe '
                          'covers *2.4 billion euros* of trade.',
                  'headline': 'MOFCOM opens anti-dumping probe into EU pork',
                  'source': 'Caixin',
                  'url': 'https://example.org/1'},
                 {'body': 'The agenda is expected to cover the five-year plan.',
                  'headline': 'Politburo to meet Friday',
                  'source': 'Xinhua',
                  'url': 'https://example.org/2'}],
 'web_url': 'https://andysaulim.github.io/Daily-China-Digest/latest.html'}

if __name__ == "__main__":
    html = render.render_html(dict(DIGEST))
    pathlib.Path("preview.html").write_text(html, encoding="utf-8")
    print(f"preview.html written ({len(html):,} chars)")

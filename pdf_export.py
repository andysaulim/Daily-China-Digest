"""
Print-ready PDF of the day's issue, best effort.

Renders public/<date>.html with headless Chromium through Playwright, the
way the Korea and Japan briefs do, because the issue is email HTML (nested
presentational tables, inline styles) which pure-Python renderers lay out
badly. Degrades to no PDF when Playwright or the browser is absent, so the
brief always sends; the header's "Print / PDF" link then 404s until the next
successful export, which the run log reports.

    python pdf_export.py public/2026-09-04.html
"""
import sys
from pathlib import Path


def export_pdf(html_path: Path, pdf_path: Path | None = None, timeout_ms: int = 60000) -> Path | None:
    html_path = Path(html_path)
    pdf_path = Path(pdf_path) if pdf_path else html_path.with_suffix(".pdf")
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:                                   # noqa: BLE001
        print(f"   ⚠ PDF export skipped (playwright not installed: {e})")
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 800, "height": 1200})
            page.goto(html_path.resolve().as_uri(), wait_until="load", timeout=timeout_ms)
            page.emulate_media(media="print")
            page.pdf(path=str(pdf_path), format="Letter", print_background=True,
                     margin={"top": "12mm", "bottom": "14mm", "left": "10mm", "right": "10mm"},
                     display_header_footer=True,
                     header_template="<div></div>",
                     footer_template=(
                         "<div style='font-size:8px;color:#888;width:100%;text-align:center;"
                         "font-family:Arial,sans-serif;'>China Daily Brief · CSIS Korea Chair · "
                         "page <span class='pageNumber'></span> of <span class='totalPages'></span></div>"))
            browser.close()
        print(f"   ✓ PDF written: {pdf_path.name} ({pdf_path.stat().st_size:,} bytes)")
        return pdf_path
    except Exception as e:                                   # noqa: BLE001
        print(f"   ⚠ PDF export failed (non-fatal): {str(e)[:160]}")
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    out = export_pdf(Path(sys.argv[1]))
    sys.exit(0 if out else 1)

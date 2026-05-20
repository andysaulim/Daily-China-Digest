"""
China Daily Brief — Email Sender
Gmail SMTP delivery with retry logic. Table-safe HTML pass-through.
"""
import os
import smtplib
import ssl
import time
from email.message import EmailMessage
from datetime import datetime
from zoneinfo import ZoneInfo


def send_digest(html: str, subject: str | None = None,
                recipients: list[str] | None = None,
                max_retries: int = 3) -> bool:
    """Send the rendered digest via Gmail SMTP.

    Args:
        html: Fully rendered HTML email body.
        subject: Subject line override. Defaults to dated 'China Digest — <date>'.
        recipients: List of recipient emails. Defaults to DIGEST_TO env var.
        max_retries: SMTP send retries on transient error.

    Returns:
        True on successful send, False otherwise.
    """
    gmail_user = os.environ.get("GMAIL_USER", "").strip()
    gmail_pass = os.environ.get("GMAIL_APP_PASS", "").strip()

    if not gmail_user or not gmail_pass:
        print("⚠ Missing GMAIL_USER or GMAIL_APP_PASS — skipping send")
        return False

    if recipients is None:
        to_str = os.environ.get("DIGEST_TO", "").strip()
        if not to_str:
            print("⚠ Missing DIGEST_TO env var — skipping send")
            return False
        recipients = [r.strip() for r in to_str.split(",") if r.strip()]

    if subject is None:
        date_str = datetime.now(ZoneInfo("America/New_York")).strftime("%a %b %-d %Y")
        subject = f"China Daily Brief — {date_str}"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = ", ".join(recipients)
    msg["Reply-To"] = gmail_user
    # Plain-text fallback (most clients prefer HTML when available)
    msg.set_content("This email requires an HTML-capable client to render properly.")
    msg.add_alternative(html, subtype="html")

    context = ssl.create_default_context()

    for attempt in range(max_retries):
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=30) as smtp:
                smtp.login(gmail_user, gmail_pass)
                smtp.send_message(msg)
            print(f"✅ Sent to {len(recipients)} recipient(s)")
            return True
        except (smtplib.SMTPException, ConnectionError, OSError) as e:
            if attempt < max_retries - 1:
                wait = 5 * (attempt + 1)
                print(f"⚠ SMTP error (attempt {attempt + 1}/{max_retries}): {e} — retrying in {wait}s")
                time.sleep(wait)
            else:
                print(f"❌ SMTP failed after {max_retries} attempts: {e}")
                return False

    return False

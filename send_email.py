"""
China Daily Brief — Email Sender
Gmail SMTP delivery with retry logic. Table-safe HTML pass-through.

Recipients travel in the SMTP envelope only (BCC): the visible To: header is
the sender, so no recipient sees the distribution list. The pattern is the
Japan brief's; the previous version wrote every address into To:.
"""
import os
import smtplib
import ssl
import time
from email.message import EmailMessage
from datetime import datetime
from zoneinfo import ZoneInfo


def _recipients_from_env() -> list[str]:
    to_str = os.environ.get("DIGEST_TO", "").strip()
    seen, out = set(), []
    for r in to_str.replace(";", ",").split(","):
        r = r.strip()
        if r and r.lower() not in seen:
            seen.add(r.lower())
            out.append(r)
    return out


def send_digest(html: str, subject: str | None = None,
                recipients: list[str] | None = None,
                max_retries: int = 3, plain_text: str | None = None) -> bool:
    """Send the rendered digest via Gmail SMTP. Returns True on success."""
    gmail_user = os.environ.get("GMAIL_USER", "").strip()
    # App passwords are shown as "xxxx xxxx xxxx xxxx"; a pasted secret often
    # keeps the spaces. Strip all whitespace, not just the ends.
    gmail_pass = "".join(os.environ.get("GMAIL_APP_PASS", "").split())
    sender = os.environ.get("GMAIL_FROM", "").strip() or gmail_user

    if not gmail_user or not gmail_pass:
        print("⚠ Missing GMAIL_USER or GMAIL_APP_PASS — skipping send")
        return False

    if recipients is None:
        recipients = _recipients_from_env()
    if not recipients:
        print("⚠ Missing DIGEST_TO env var — skipping send")
        return False

    if subject is None:
        date_str = datetime.now(ZoneInfo("America/New_York")).strftime("%a %b %-d %Y")
        subject = f"China Daily Brief — {date_str}"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = sender                     # visible header; real list is BCC
    msg["Reply-To"] = gmail_user
    msg.set_content(plain_text or "This email requires an HTML-capable client to render properly.")
    msg.add_alternative(html, subtype="html")

    context = ssl.create_default_context()

    for attempt in range(max_retries):
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=30) as smtp:
                smtp.login(gmail_user, gmail_pass)
                smtp.send_message(msg, from_addr=sender, to_addrs=recipients)
            print(f"✅ Sent to {len(recipients)} recipient(s) (BCC)")
            return True
        except smtplib.SMTPAuthenticationError as e:
            # Not transient: a rotated app password will not fix itself.
            print(f"❌ SMTP authentication failed: {e}")
            return False
        except (smtplib.SMTPException, ConnectionError, OSError) as e:
            if attempt < max_retries - 1:
                wait = 5 * (attempt + 1)
                print(f"⚠ SMTP error (attempt {attempt + 1}/{max_retries}): {e} — retrying in {wait}s")
                time.sleep(wait)
            else:
                print(f"❌ SMTP failed after {max_retries} attempts: {e}")
                return False

    return False

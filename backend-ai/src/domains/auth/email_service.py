"""Email delivery for OTP codes.

In development (no SMTP configured), OTPs are logged to stdout.
In production, OTPs are sent via SMTP.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config import get_settings

logger = logging.getLogger(__name__)


def send_otp_email(to_email: str, otp_code: str, purpose: str) -> bool:
    """Send OTP email. Returns True on success, False on failure."""
    settings = get_settings()

    if not settings.smtp_host or not settings.smtp_user:
        logger.warning(
            "[DEV MODE] OTP for %s: %s (purpose=%s)",
            to_email,
            otp_code,
            purpose,
        )
        return True

    subject = "Lakshya — Verify your email" if purpose == "signup" else "Lakshya — Login code"
    action_word = "verify your account" if purpose == "signup" else "log in"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f4f6f9; padding: 40px;">
      <div style="max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 12px; padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.06);">
        <h2 style="color: #1a1a2e; margin-bottom: 8px;">Lakshya</h2>
        <p style="color: #555; font-size: 15px;">Use the code below to {action_word}:</p>
        <div style="background: #f0f2f5; border-radius: 8px; padding: 20px; text-align: center; margin: 24px 0;">
          <span style="font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #1a1a2e;">{otp_code}</span>
        </div>
        <p style="color: #888; font-size: 13px;">This code expires in {settings.otp_expiry_minutes} minutes. If you didn't request this, ignore this email.</p>
      </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from, [to_email], msg.as_string())
        logger.info("OTP email sent to %s (purpose=%s)", to_email, purpose)
        return True
    except Exception:
        logger.exception("Failed to send OTP email to %s", to_email)
        return False

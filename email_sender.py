"""Email sender client — dispatches outreach via Gmail SMTP."""

import smtplib
import uuid
import logging
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import Config

logger = logging.getLogger("EmailSender")


def _html_wrap(body: str) -> str:
    paragraphs = "".join(
        f"<p style='margin:0 0 14px 0;'>{line}</p>"
        for line in body.split("\n") if line.strip()
    )
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:Arial,sans-serif;font-size:15px;color:#222;
             max-width:540px;margin:0 auto;padding:24px;line-height:1.7;">
  {paragraphs}
</body>
</html>"""


def send_email_sync(to_email: str, subject: str, body: str,
                    business_name: str = "") -> bool:
    if not all([Config.SMTP_USER, Config.SMTP_PASSWORD]):
        logger.error("SMTP config missing — check GMAIL_USER and GMAIL_APP_PASSWORD in .env")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Alex Carter <{Config.SMTP_USER}>"
    msg["To"] = to_email
    msg["Reply-To"] = Config.SMTP_USER

    domain = Config.SMTP_USER.split("@")[-1]
    msg["Message-ID"] = f"<{uuid.uuid4()}@{domain}>"
    msg["X-Mailer"] = "SMMA-Bot-v2"

    msg.attach(MIMEText(body.strip(), "plain", "utf-8"))
    msg.attach(MIMEText(_html_wrap(body), "html", "utf-8"))

    try:
        server = smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=15)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
        server.sendmail(Config.SMTP_USER, to_email, msg.as_string())
        server.quit()
        logger.info(f"Email sent → {to_email} | Subject: {subject}")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("Gmail auth failed — use an App Password, not your real password")
        return False
    except Exception as e:
        logger.error(f"Email failed → {to_email}: {e}")
        return False


async def send_email(to_email: str, subject: str, body: str,
                      business_name: str = "") -> bool:
    return await asyncio.to_thread(
        send_email_sync, to_email, subject, body, business_name,
    )


__all__ = ["send_email", "send_email_sync"]

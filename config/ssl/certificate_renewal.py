"""
Certificate Renewal Orchestrator
Checks SSL expiry daily and triggers renewal if within threshold.
Designed to run as a cron job or systemd timer.
"""
import logging
import os
import sys
import json
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/certificate_renewal.log", mode="a"),
    ],
)
logger = logging.getLogger("cert_renewal")

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


def load_config() -> dict:
    config_path = ROOT / "config" / "production" / "ssl_config.json"
    if config_path.exists():
        return json.loads(config_path.read_text())
    return {"domain": os.getenv("DOMAIN", "agentevoz.com"), "ssl": {}}


def send_alert(subject: str, body: str, config: dict) -> None:
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    alert_to  = config.get("monitoring", {}).get("alert_email", "admin@agentevoz.com")

    if not smtp_host or not smtp_user:
        logger.warning("SMTP not configured — skipping email alert")
        return

    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = alert_to
        with smtplib.SMTP(smtp_host, smtp_port) as s:
            s.starttls()
            s.login(smtp_user, smtp_pass)
            s.send_message(msg)
        logger.info(f"Alert sent to {alert_to}")
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")


def run_renewal_check() -> int:
    """
    Returns exit code: 0=OK, 1=renewed, 2=critical/error
    """
    config = load_config()
    domain = config.get("domain", os.getenv("DOMAIN", "agentevoz.com"))
    email  = config.get("email", os.getenv("SSL_EMAIL", "admin@agentevoz.com"))

    try:
        from production.ssl_certificate_manager import SSLCertificateManager
        mgr = SSLCertificateManager(domain, email)
    except ImportError:
        logger.error("SSLCertificateManager not available")
        return 2

    status = mgr.check_expiration()

    if not status.get("exists"):
        logger.warning(f"No certificate found for {domain}")
        send_alert(
            f"[AgenteDeVoz] SSL Certificate Missing — {domain}",
            f"No SSL certificate found for {domain}. Manual intervention required.",
            config,
        )
        return 2

    days = status.get("expires_in_days", 0)
    logger.info(f"Certificate for {domain} expires in {days} days")

    alert_days = config.get("monitoring", {}).get("alert_on_expiry_days", [30, 14, 7])

    if days in alert_days:
        send_alert(
            f"[AgenteDeVoz] SSL Certificate Expiry Warning — {days} days",
            f"SSL certificate for {domain} expires in {days} days.\n"
            f"Expiry date: {status.get('expires_on', '?')}\n"
            f"Auto-renewal will attempt renewal within 30 days.",
            config,
        )

    if status.get("critical"):
        logger.critical(f"CRITICAL: Certificate expires in {days} days — forcing renewal")
        renewed = mgr.renew_certificate(force=True)
        if renewed:
            logger.info("Emergency renewal successful")
            return 1
        else:
            send_alert(
                f"[AgenteDeVoz] CRITICAL: SSL Renewal Failed — {domain}",
                f"Emergency SSL renewal failed for {domain}. {days} days remaining.\n"
                "MANUAL INTERVENTION REQUIRED IMMEDIATELY.",
                config,
            )
            return 2

    if status.get("needs_renewal"):
        logger.info("Certificate within renewal window — attempting renewal")
        renewed = mgr.renew_certificate(force=False)
        if renewed:
            logger.info("Renewal successful")
            return 1
        else:
            logger.error("Renewal failed — will retry tomorrow")
            return 2

    logger.info(f"Certificate valid for {days} more days — no action needed")
    return 0


if __name__ == "__main__":
    # Ensure log directory exists
    Path("logs").mkdir(exist_ok=True)
    exit_code = run_renewal_check()
    sys.exit(exit_code)

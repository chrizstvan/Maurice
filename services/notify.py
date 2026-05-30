"""
telegram_notify.py
Sends alert messages to your Telegram chat.
"""

import requests
import logging

logger = logging.getLogger(__name__)


def send_message(bot_token: str, chat_id: str, text: str) -> bool:
    """Send a Telegram message to one or more chat IDs (comma-separated). Returns True if all succeed."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    ids = [cid.strip() for cid in str(chat_id).split(",") if cid.strip()]
    success = True
    for cid in ids:
        payload = {"chat_id": cid, "text": text, "parse_mode": "HTML"}
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info(f"Telegram message sent to {cid}.")
        except requests.RequestException as e:
            logger.error(f"Failed to send Telegram message to {cid}: {e}")
            success = False
    return success


def format_error_alert(service: str, error: str) -> str:
    return (
        f"⚠️ <b>AGENT ERROR</b>\n"
        f"Service : {service}\n"
        f"Error   : {error}"
    )

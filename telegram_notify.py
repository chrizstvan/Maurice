"""
telegram_notify.py
Sends alert messages to your Telegram chat.
"""

import requests
import logging

logger = logging.getLogger(__name__)


def send_message(bot_token: str, chat_id: str, text: str) -> bool:
    """Send a Telegram message. Returns True on success."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id":    chat_id,
        "text":       text,
        "parse_mode": "HTML",
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Telegram message sent successfully.")
        return True
    except requests.RequestException as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def format_error_alert(service: str, error: str) -> str:
    return (
        f"⚠️ <b>AGENT ERROR</b>\n"
        f"Service : {service}\n"
        f"Error   : {error}"
    )

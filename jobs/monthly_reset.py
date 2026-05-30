#!/usr/bin/env python3
"""
jobs/monthly_reset.py — Create a new monthly budget and pre-load recurring expenses.
Run on the 1st of each month via GitHub Actions.
"""
import os
import sys
import logging
from pathlib import Path

ROOT = Path(__file__).parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from core import config, db  # noqa: F401 — config import loads .env into os.environ
from services.notify import send_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

from datetime import date

MONTHLY_BUDGET_AMOUNT = float(os.environ.get("MONTHLY_BUDGET_AMOUNT", "8000000"))


def main():
    today = date.today()
    name = today.strftime("%B %Y")
    logger.info(f"Creating monthly budget: {name}")

    budget = db.create_monthly_budget_from_template(name=name, total=MONTHLY_BUDGET_AMOUNT)
    recurring = db.get_recurring_expenses()
    recurring_total = sum(r["amount"] for r in recurring)

    msg = (
        f"<b>{name} budget created</b>\n"
        f"Total: IDR {MONTHLY_BUDGET_AMOUNT:,.0f}\n"
        f"Pre-loaded {len(recurring)} recurring expenses — {recurring_total:,.0f} IDR.\n"
        f"Remaining: {MONTHLY_BUDGET_AMOUNT - recurring_total:,.0f} IDR."
    )
    send_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, msg)
    logger.info("Monthly reset complete.")


if __name__ == "__main__":
    main()

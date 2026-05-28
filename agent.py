#!/usr/bin/env python3
"""
agent.py — Main Price Monitor Agent
Run manually or via cron job.

Usage:
    python3 agent.py             # check everything
    python3 agent.py --flights   # check flights only
    python3 agent.py --trains    # check trains only
"""

import json
import logging
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

os.chdir(Path(__file__).parent)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/agent.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

import config
import db
from checkers import REGISTRY
from telegram_notify import send_message


def load_last_prices() -> dict:
    try:
        with open(config.DATA_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_last_prices(data: dict):
    Path(config.DATA_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(config.DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def notify(text: str):
    send_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, text)


def record_price(route_label: str, price: float, currency: str, details: dict):
    try:
        db.record(route_label, price, currency, details)
    except Exception as e:
        logger.warning(f"Failed to record price to DB: {e}")


def main():
    parser = argparse.ArgumentParser(description="Price Monitor Agent")
    for checker_type in REGISTRY:
        parser.add_argument(
            f"--{checker_type}",
            action="store_true",
            help=f"Check {checker_type} only",
        )
    args = parser.parse_args()

    requested = [t for t in REGISTRY if getattr(args, t, False)]
    types_to_run = requested if requested else list(REGISTRY.keys())

    logger.info("=" * 50)
    logger.info(f"Agent started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    last_prices = load_last_prices()

    for checker_type in types_to_run:
        routes = config.CHECKER_ROUTES.get(checker_type, [])
        if not routes:
            logger.info(f"No routes configured for {checker_type}, skipping.")
            continue
        checker = REGISTRY[checker_type](routes=routes, config=config)
        checker.run(last_prices, notify_fn=notify, record_fn=record_price)

    save_last_prices(last_prices)

    logger.info("Agent finished.")
    logger.info("=" * 50 + "\n")


if __name__ == "__main__":
    main()

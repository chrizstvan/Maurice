#!/usr/bin/env python3
"""
monitor/agent.py — Main Price Monitor Agent
Run manually or via cron job.

Usage:
    python3 monitor/agent.py             # check everything
    python3 monitor/agent.py --flights   # check flights only
    python3 monitor/agent.py --trains    # check trains only
"""

import json
import logging
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/agent.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

from core import config
from core import db
from core import llm
from monitor.checkers import REGISTRY
from services.notify import send_message


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


def notify(text: str, route: dict = None):
    """Send alert to all route subscribers, falling back to global TELEGRAM_CHAT_ID."""
    subscribers = route.get("subscribers") if route else None
    targets = subscribers if subscribers else [config.TELEGRAM_CHAT_ID]
    for chat_id in targets:
        send_message(config.TELEGRAM_BOT_TOKEN, chat_id, text)


def record_price(route_label: str, price: float, currency: str, details: dict):
    try:
        db.record(route_label, price, currency, details)
    except Exception as e:
        logger.warning(f"Failed to record price to DB: {e}")


def get_price_history(route_label: str) -> list:
    try:
        return db.get_recent_history(route_label, limit=10)
    except Exception as e:
        logger.warning(f"Failed to fetch price history for {route_label}: {e}")
        return []


def reason_price(route: dict, result: dict, history: list) -> str:
    return llm.reason_price(route, result, history)


def decide_route(route: dict, history: list) -> bool:
    last_check_time = history[0].get("checked_at") if history else None
    try:
        decision = llm.decide_check(route, history, last_check_time)
        if not decision.get("check_now", True):
            logger.info(
                f"Skipping {route['label']} — {decision.get('reason')} "
                f"(wait {decision.get('suggested_wait_hours', '?')}h)"
            )
            return False
        logger.info(f"Checking {route['label']} — {decision.get('reason')}")
        return True
    except Exception as e:
        logger.warning(f"decide_check failed for {route['label']}: {e} — proceeding")
        return True


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

    # Expire past routes before loading
    try:
        expired = db.deactivate_expired_routes()
        if expired:
            labels = ", ".join(r.get("label", str(r.get("id"))) for r in expired)
            logger.info(f"Auto-expired {len(expired)} route(s): {labels}")
    except Exception as e:
        logger.warning(f"Could not expire old routes: {e}")

    # Load routes from DB; fall back to config if DB is unavailable or empty
    try:
        all_routes = db.get_watched_routes()
        if not any(all_routes.values()):
            raise ValueError("no routes in DB")
        logger.info("Routes loaded from Supabase.")
    except Exception as e:
        logger.info(f"Using config routes ({e}).")
        all_routes = config.CHECKER_ROUTES

    for checker_type in types_to_run:
        routes = all_routes.get(checker_type, [])
        if not routes:
            logger.info(f"No routes configured for {checker_type}, skipping.")
            continue
        checker = REGISTRY[checker_type](routes=routes, config=config)
        checker.run(
            last_prices,
            notify_fn=notify,
            record_fn=record_price,
            get_history_fn=get_price_history,
            reason_fn=reason_price,
            decide_fn=decide_route,
        )

    save_last_prices(last_prices)

    logger.info("Agent finished.")
    logger.info("=" * 50 + "\n")


if __name__ == "__main__":
    main()

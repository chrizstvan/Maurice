#!/usr/bin/env python3
"""
jobs/weekly_report.py — Send a weekly price summary to all route subscribers.
Run every Monday via GitHub Actions.
"""
import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from core import config, db, llm
from services.notify import send_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

_TYPE_EMOJI = {"flights": "✈️", "trains": "🚂", "hotels": "🏨"}


def _trend(prices: list[float]) -> str:
    if len(prices) < 3:
        return "→ Insufficient data"
    recent = prices[:3]
    older = prices[-3:]
    avg_recent = sum(recent) / len(recent)
    avg_older = sum(older) / len(older)
    diff_pct = (avg_recent - avg_older) / avg_older * 100
    if diff_pct < -5:
        return f"↘ Falling ({abs(diff_pct):.0f}% down)"
    elif diff_pct > 5:
        return f"↗ Rising ({diff_pct:.0f}% up)"
    return "→ Stable"


def main():
    now = datetime.now()
    week_start = (now - timedelta(days=7)).strftime("%d %b")
    week_end = now.strftime("%d %b %Y")

    logger.info(f"Generating weekly report for {week_start}–{week_end}")

    # Load active routes
    try:
        all_routes = db.get_watched_routes()
    except Exception as e:
        logger.error(f"Could not load routes: {e}")
        return
    
    routes_flat = [r for routes in all_routes.values() for r in routes]
    if not routes_flat:
        logger.info("No active routes — nothing to report.")
        return

    route_sections = []
    routes_summary = []

    for route_type, routes in all_routes.items():
        for route in routes:
            label = route["label"]
            currency = route.get("currency", "IDR")
            target = route["max_price"]
            emoji = _TYPE_EMOJI.get(route_type, "🔍")

            history = db.get_week_history(label)
            if not history:
                route_sections.append(
                    f"{emoji} <b>{label}</b>\n"
                    f"  No data this week."
                )
                continue

            prices = [float(h["price"]) for h in history]
            low = min(prices)
            high = max(prices)
            current = prices[0]
            checks = len(prices)
            hit_count = sum(1 for p in prices if p <= target)
            trend = _trend(prices)

            low_date = history[prices.index(low)]["checked_at"][:10]
            high_date = history[prices.index(high)]["checked_at"][:10]

            hit_str = f"✓ Hit {hit_count}x this week" if hit_count else "✗ Not hit"

            route_sections.append(
                f"{emoji} <b>{label}</b>\n"
                f"  Checks : {checks}\n"
                f"  Low    : {currency} {low:,.0f}  ({low_date})\n"
                f"  High   : {currency} {high:,.0f}  ({high_date})\n"
                f"  Current: {currency} {current:,.0f}\n"
                f"  Trend  : {trend}\n"
                f"  Target : {currency} {target:,.0f} — {hit_str}"
            )

            routes_summary.append({
                "label": label,
                "low": low,
                "high": high,
                "current": current,
                "target": target,
                "hit_count": hit_count,
                "checks": checks,
                "trend": trend,
            })

    # LLM insight
    insight = ""
    if routes_summary:
        try:
            insight = llm.reason_weekly_report(routes_summary)
        except Exception as e:
            logger.warning(f"LLM insight failed: {e}")

    # Build message
    header = f"📊 <b>Weekly Price Report — {week_start}–{week_end}</b>\n"
    body = "\n\n".join(route_sections)
    footer = f"\n\n💡 <b>Insight</b>\n{insight}" if insight else ""
    message = header + "\n" + body + footer

    # Send to all subscribers; fall back to global TELEGRAM_CHAT_ID
    try:
        recipients = db.get_all_subscribers()
    except Exception as e:
        logger.warning(f"Could not fetch subscribers: {e}")
        recipients = []

    if not recipients:
        recipients = [config.TELEGRAM_CHAT_ID]

    for chat_id in recipients:
        send_message(config.TELEGRAM_BOT_TOKEN, chat_id, message)
        logger.info(f"Report sent to {chat_id}")

    logger.info("Weekly report complete.")


if __name__ == "__main__":
    main()

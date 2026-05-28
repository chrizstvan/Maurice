#!/usr/bin/env python3
"""
scheduler.py — Smart randomized scheduler for agent.py

Picks random run times within safe (low-traffic) hours.
If a scheduled time lands in a busy window, it automatically
postpones to the next safe slot.

Set up via cron to run every 30 minutes:
    */30 * * * * cd ~/price-agent && python3 scheduler.py >> logs/agent.log 2>&1
"""

import json
import random
import subprocess
import sys
import os
import logging
from datetime import datetime, timedelta
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
logger = logging.getLogger("scheduler")

# ── Time windows ─────────────────────────────────────────────

# Hours (0-23) to avoid — high internet traffic
BUSY_HOURS = set(range(7, 10)) | set(range(19, 24))  # 07-09, 19-23

# How often to run: pick a random gap in this range (in hours)
MIN_GAP_HOURS = 8
MAX_GAP_HOURS = 16

SCHEDULE_FILE = "data/next_run.json"


# ── Helpers ───────────────────────────────────────────────────

def is_safe(hour: int) -> bool:
    return hour not in BUSY_HOURS


def load_next_run() -> datetime | None:
    try:
        data = json.loads(Path(SCHEDULE_FILE).read_text())
        return datetime.fromisoformat(data["next_run"])
    except (FileNotFoundError, KeyError, ValueError):
        return None


def save_next_run(dt: datetime):
    Path(SCHEDULE_FILE).parent.mkdir(parents=True, exist_ok=True)
    Path(SCHEDULE_FILE).write_text(json.dumps({"next_run": dt.isoformat()}, indent=2))


def next_safe_slot(after: datetime) -> datetime:
    """Step forward hour by hour from `after` until we land in a safe hour."""
    candidate = after.replace(minute=random.randint(0, 59), second=0, microsecond=0)
    for _ in range(48):
        if is_safe(candidate.hour):
            return candidate
        candidate += timedelta(hours=1)
        candidate = candidate.replace(minute=random.randint(0, 59), second=0, microsecond=0)
    # Fallback: 02:00 tomorrow
    return (after + timedelta(days=1)).replace(
        hour=2, minute=random.randint(0, 59), second=0, microsecond=0
    )


def pick_next_run(after: datetime) -> datetime:
    """
    Pick a random run time 8-16 hours after `after`, landing in a safe hour.
    Tries random candidates first; falls back to the next safe slot if needed.
    """
    for _ in range(50):
        gap = random.uniform(MIN_GAP_HOURS, MAX_GAP_HOURS)
        candidate = after + timedelta(hours=gap)
        candidate = candidate.replace(minute=random.randint(0, 59), second=0, microsecond=0)
        if is_safe(candidate.hour):
            return candidate
    # Fallback: find nearest safe slot at least MIN_GAP_HOURS away
    return next_safe_slot(after + timedelta(hours=MIN_GAP_HOURS))


# ── Main ──────────────────────────────────────────────────────

def main():
    now = datetime.now()
    next_run = load_next_run()

    if next_run is None:
        # First ever run — schedule within the current safe window, or the next one
        if is_safe(now.hour):
            delay = random.randint(5, 55)
            next_run = now + timedelta(minutes=delay)
            next_run = next_run.replace(second=0, microsecond=0)
        else:
            next_run = next_safe_slot(now + timedelta(hours=1))
        save_next_run(next_run)
        logger.info(f"First run scheduled for {next_run.strftime('%Y-%m-%d %H:%M')}")
        return

    if now < next_run:
        logger.info(f"Next run at {next_run.strftime('%Y-%m-%d %H:%M')} — waiting.")
        return

    # Time is up — check if we're still in a safe window
    if not is_safe(now.hour):
        postponed = next_safe_slot(now + timedelta(hours=1))
        save_next_run(postponed)
        logger.info(
            f"Busy hour ({now.hour:02d}:xx) — postponed to {postponed.strftime('%Y-%m-%d %H:%M')}"
        )
        return

    # Safe window — run the agent
    logger.info(
        f"Running agent (scheduled {next_run.strftime('%H:%M')}, "
        f"now {now.strftime('%H:%M')})"
    )
    result = subprocess.run([sys.executable, "agent.py"])

    if result.returncode != 0:
        logger.warning("agent.py exited with non-zero status — check logs above.")

    # Schedule next run
    nxt = pick_next_run(now)
    save_next_run(nxt)
    logger.info(f"Next run scheduled for {nxt.strftime('%Y-%m-%d %H:%M')}")


if __name__ == "__main__":
    main()

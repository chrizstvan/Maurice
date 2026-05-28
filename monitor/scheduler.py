#!/usr/bin/env python3
"""
monitor/scheduler.py — GitHub Actions entrypoint for price checks.
Called by .github/workflows/price-check.yml on a cron schedule.
Runs monitor/agent.py if the current time window is safe (non-peak hours).
"""
import sys
import subprocess
import logging
from pathlib import Path
import os

os.chdir(Path(__file__).parent.parent)

# Log to stdout only — GitHub Actions captures stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

from core import llm


def main():
    if not llm.should_run_now():
        logging.info("Skipping — current hour is a busy window.")
        sys.exit(0)
    logging.info("Running price check agent...")
    result = subprocess.run([sys.executable, "monitor/agent.py"])
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()

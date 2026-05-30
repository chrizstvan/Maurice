#!/usr/bin/env python3
"""
check.py — Verify Maurice is configured correctly before first run.
Run from project root: python check.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

OK   = "  ✓"
FAIL = "  ✗"
WARN = "  !"

errors = 0


def ok(msg):   print(f"{OK} {msg}")
def fail(msg): print(f"{FAIL} {msg}"); global errors; errors += 1
def warn(msg): print(f"{WARN} {msg}")


# ── 1. Imports ────────────────────────────────────────────────────────────────
print("\n[ Imports ]")
try:
    from core import config
    ok("core.config")
except Exception as e:
    fail(f"core.config — {e}")

try:
    from core import llm
    ok("core.llm")
except Exception as e:
    fail(f"core.llm — {e}")

try:
    from core import db
    ok("core.db")
except Exception as e:
    fail(f"core.db — {e}")

try:
    from monitor.checkers import REGISTRY
    ok(f"monitor.checkers — {list(REGISTRY.keys())}")
except Exception as e:
    fail(f"monitor.checkers — {e}")

# ── 2. Environment variables ──────────────────────────────────────────────────
print("\n[ Environment variables ]")

required = {
    "TELEGRAM_BOT_TOKEN": config.TELEGRAM_BOT_TOKEN,
    "TELEGRAM_CHAT_ID":   config.TELEGRAM_CHAT_ID,
    "SERPAPI_KEY":        config.SERPAPI_KEY,
    "LLM_PROVIDER":       config.LLM_PROVIDER,
}
for key, val in required.items():
    if val:
        ok(f"{key} is set")
    else:
        fail(f"{key} is missing")

provider = config.LLM_PROVIDER
llm_key_map = {
    "anthropic": ("ANTHROPIC_API_KEY", config.ANTHROPIC_API_KEY),
    "openai":    ("OPENAI_API_KEY",    config.OPENAI_API_KEY),
    "gemini":    ("GEMINI_API_KEY",    config.GEMINI_API_KEY),
}
if provider in llm_key_map:
    key_name, key_val = llm_key_map[provider]
    if key_val:
        ok(f"{key_name} is set (provider: {provider})")
    else:
        fail(f"{key_name} is missing for provider '{provider}'")
else:
    fail(f"Unknown LLM_PROVIDER: '{provider}' — must be anthropic / openai / gemini")

if config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY:
    ok("SUPABASE_URL + SUPABASE_SERVICE_KEY are set")
else:
    warn("Supabase not configured — price history and bot features will be disabled")

# ── 3. Telegram ───────────────────────────────────────────────────────────────
print("\n[ Telegram ]")
try:
    import requests
    resp = requests.get(
        f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getMe",
        timeout=10,
    )
    data = resp.json()
    if data.get("ok"):
        ok(f"Bot token valid — @{data['result']['username']}")
    else:
        fail(f"Bot token rejected — {data.get('description')}")
except Exception as e:
    fail(f"Telegram check failed — {e}")

# ── 4. Supabase ───────────────────────────────────────────────────────────────
print("\n[ Supabase ]")
if config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY:
    try:
        from supabase import create_client
        client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
        client.table("price_history").select("id").limit(1).execute()
        ok("Supabase connection OK + price_history table exists")
    except Exception as e:
        fail(f"Supabase — {e}")
else:
    warn("Skipped (not configured)")

# ── 5. LLM ────────────────────────────────────────────────────────────────────
print("\n[ LLM ]")
try:
    result = llm.categorize_expense("45k food lunch")
    if "amount" in result and result["amount"] == 45000:
        ok(f"LLM call OK — {result}")
    else:
        warn(f"LLM responded but output looks unexpected — {result}")
except Exception as e:
    fail(f"LLM call failed — {e}")

# ── 6. Routes ─────────────────────────────────────────────────────────────────
print("\n[ Routes ]")
from datetime import datetime
for rtype, routes in config.CHECKER_ROUTES.items():
    for r in routes:
        try:
            travel = datetime.strptime(r["date"], "%Y-%m-%d")
            days = (travel - datetime.now()).days
            if days < 0:
                warn(f"{r['label']} — travel date {r['date']} is in the past")
            else:
                ok(f"{r['label']} — {days} days away")
        except Exception as e:
            warn(f"{rtype} route — {e}")

# ── Summary ───────────────────────────────────────────────────────────────────
print()
if errors == 0:
    print("All checks passed — you're good to run python monitor/agent.py")
else:
    print(f"{errors} check(s) failed — fix the issues above before running the agent")
print()

# ============================================================
#  PRICE AGENT — CONFIG
#  Secrets are loaded from .env (never hardcode keys here!)
# ============================================================

import os
from pathlib import Path

# Load .env file manually (no python-dotenv needed)
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

# --- SerpAPI (Google Flights) ---
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")

# ============================================================
#  ROUTES TO MONITOR
#  Each key matches a checker type in checkers/REGISTRY.
#  To add a new transport type, add its key + routes here.
# ============================================================
CHECKER_ROUTES = {
    "flights": [
        {
            "from":      "CGK",
            "to":        "DPS",
            "date":      "2026-08-16",
            "max_price": 1_400_000,
            "currency":  "IDR",
            "label":     "Jakarta → Bali",
        },
    ],
    # seat_class: "EKS" (Eksekutif) | "BIS" (Bisnis) | "EKO" (Ekonomi)
    "trains": [
        {
            "from":       "GMR",
            "to":         "YK",
            "date":       "2025-08-15",
            "seat_class": "EKS",
            "max_price":  350_000,
            "label":      "Gambir → Yogya (Eksekutif)",
        },
    ],
}

# --- Supabase ---
SUPABASE_URL         = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# --- LLM ---
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")  # anthropic | openai | gemini
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY    = os.environ.get("OPENAI_API_KEY", "")
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY", "")

# ============================================================
#  GENERAL SETTINGS
# ============================================================
LOG_FILE  = "logs/agent.log"
DATA_FILE = "data/last_prices.json"

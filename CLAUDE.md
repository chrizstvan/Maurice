# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the project

```bash
# Install dependencies
pip install -r requirements.txt

# Run price check manually
python agent.py                # all routes
python agent.py --flights      # flights only
python agent.py --trains       # trains only

# Run the Telegram budget bot (local, uses polling)
python bot.py

# Run monthly budget reset manually
python monthly_reset.py

# GitHub Actions entrypoint (skips if busy hours)
python llm_scheduler.py
```

Secrets are loaded automatically from `.env` via `config.py` — no `python-dotenv` needed. Copy `.env.example` to `.env` and fill in values.

## Architecture

Two independent processes share `db.py`, `llm.py`, and Supabase:

**Price Monitor** — runs on GitHub Actions every 2 hours via `.github/workflows/price-check.yml`. Entry point is `llm_scheduler.py` → `agent.py` → `checkers/`. Writes price results to Supabase `price_history` via `db.record()`.

**Budget Bot** — runs always-on on Render via `bot.py`. Handles Telegram messages through `handlers/`. Reads/writes budgets and expenses via `db.py`. Calls `llm.py` for receipt parsing and budget insights.

## Key design patterns

**Adding a new checker type** (e.g. buses): create `checkers/buses.py` extending `BaseChecker`, register it in `checkers/__init__.py` REGISTRY, add routes in `config.py` CHECKER_ROUTES. `agent.py` gains a `--buses` flag automatically. Never change `price_key()` return values — doing so silently loses price history.

**`BaseChecker.run()`** accepts an optional `record_fn(route_label, price, currency, details)` callback — `agent.py` passes `db.record` wrapped in a try/except so DB failures never abort a price check.

**LLM provider** is selected via `LLM_PROVIDER` env var (`anthropic` / `openai` / `gemini`). All calls go through `llm.py` — never call provider SDKs directly from other files. `categorize_expense()` uses cheaper/faster models (Haiku, gpt-4o-mini, gemini-flash); `read_receipt()` and `reason_budget()` use full models.  `_strip_code_fences()` must be called before `json.loads()` since some providers wrap output in ` ```json ``` `.

**All DB calls** go through `db.py`. `_client()` raises `RuntimeError` if `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` are unset. To swap out Supabase, only `db.py` needs changing.

**Expense confirmation flow** in the bot uses `context.user_data["pending_expense"]` to store a parsed expense between messages. `text_handler.py` checks for this key first before parsing new input — so "yes"/"no" replies confirm pending entries from both `receipt_handler` and `text_handler`.

## Supabase schema

Run `supabase_schema.sql` in the Supabase SQL editor to create all tables. Tables:
- `price_history` — written by price monitor; read by `/report` on trip budgets for cross-feature context
- `budgets` — `type` is `'trip'` or `'monthly'`; only one budget has `active=true` at a time
- `expenses` — `source` is `'receipt'`, `'manual'`, or `'recurring'`
- `recurring_expenses` — pre-loaded into new monthly budgets by `monthly_reset.py`
- `budget_categories` — optional per-category caps (not yet enforced in code)

## Config

All env vars are read in `config.py`. Required vars:

| Var | Used by |
|-----|---------|
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Both processes |
| `SERPAPI_KEY` | `checkers/flights.py` |
| `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` | `db.py` |
| `LLM_PROVIDER` | `llm.py` |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` | `llm.py` (one required) |
| `MONTHLY_BUDGET_AMOUNT` | `monthly_reset.py` |

`llm.py` reads API keys directly from `os.environ` (not from `config`) to avoid circular imports.

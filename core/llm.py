"""
llm.py — LLM provider abstraction.
Switch provider via LLM_PROVIDER env var: anthropic | openai | gemini
"""

import base64
import json
import os
import re

from core.prompts import DECIDE_CHECK_SYSTEM

# Busy hours: 7-9 AM and 7 PM-midnight (local time)
BUSY_HOURS = set(range(7, 10)) | set(range(19, 24))


def should_run_now() -> bool:
    """Return True if current hour is NOT in BUSY_HOURS."""
    from datetime import datetime
    return datetime.now().hour not in BUSY_HOURS


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences before JSON parsing."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _provider() -> str:
    return os.environ.get("LLM_PROVIDER", "anthropic").lower()


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

def _anthropic_vision(image_bytes: bytes, prompt: str, model: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    message = client.messages.create(
        model=model,
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    return message.content[0].text


def _anthropic_text(prompt: str, model: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

def _openai_vision(image_bytes: bytes, prompt: str, model: str) -> str:
    import openai
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    response = client.chat.completions.create(
        model=model,
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    return response.choices[0].message.content


def _openai_text(prompt: str, model: str) -> str:
    import openai
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

def _gemini_vision(image_bytes: bytes, prompt: str, model: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    import PIL.Image
    import io
    img = PIL.Image.open(io.BytesIO(image_bytes))
    gmodel = genai.GenerativeModel(model)
    response = gmodel.generate_content([prompt, img])
    return response.text


def _gemini_text(prompt: str, model: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    gmodel = genai.GenerativeModel(model)
    response = gmodel.generate_content(prompt)
    return response.text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_receipt(image_bytes: bytes) -> dict:
    """Vision call — extract expense info from receipt image.

    Returns: {amount, currency, merchant, category_guess}
    """
    prompt = (
        "Extract the total amount, merchant name, currency, and guess the expense category "
        "from this receipt image. Categories: food/transport/accommodation/activities/shopping/"
        "utilities/other. Respond ONLY with valid JSON like: "
        '{"amount": 45000, "currency": "IDR", "merchant": "Warung Makan", "category_guess": "food"}'
    )
    provider = _provider()
    if provider == "anthropic":
        raw = _anthropic_vision(image_bytes, prompt, "claude-opus-4-7")
    elif provider == "openai":
        raw = _openai_vision(image_bytes, prompt, "gpt-4o")
    elif provider == "gemini":
        raw = _gemini_vision(image_bytes, prompt, "gemini-1.5-pro")
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}")
    return json.loads(_strip_code_fences(raw))


def reason_budget(context: dict) -> str:
    """Text call — return 2-4 sentence friendly budget insight.

    context keys: budget, expenses (optional), price_history (optional), days_remaining,
                  total_spent, remaining, by_category.
    """
    prompt = (
        "You are a helpful personal finance assistant. Given the following budget context, "
        "provide a concise, friendly insight (2-4 sentences). Mention budget pace, any category "
        "overspending, and if price_history is provided for a trip, mention relevant price movements.\n\n"
        f"Context:\n{json.dumps(context, indent=2, default=str)}"
    )
    provider = _provider()
    if provider == "anthropic":
        return _anthropic_text(prompt, "claude-opus-4-7")
    elif provider == "openai":
        return _openai_text(prompt, "gpt-4o")
    elif provider == "gemini":
        return _gemini_text(prompt, "gemini-1.5-pro")
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}")


def reason_price(route: dict, current_result: dict, history: list) -> str:
    """LLM reasoning for a price alert — returns a Telegram-ready HTML message.

    route: from config (label, date, max_price, currency, from, to)
    current_result: from checker.fetch() (price + provider-specific fields)
    history: from db.get_recent_history() — previous price records, newest first
    """
    currency = route.get("currency", "IDR")
    price = current_result["price"]
    hit_target = price <= route["max_price"]

    if history:
        prices = [float(h["price"]) for h in history]
        avg = sum(prices) / len(prices)
        low = min(prices)
        high = max(prices)
        history_lines = "\n".join(
            f"  {h['checked_at'][:16]}: {currency} {float(h['price']):,.0f}"
            for h in history[:10]
        )
        history_summary = (
            f"History ({len(history)} checks): avg {currency} {avg:,.0f}, "
            f"low {currency} {low:,.0f}, high {currency} {high:,.0f}\n"
            f"Recent checks:\n{history_lines}"
        )
    else:
        history_summary = "No previous price history available — this is the first check."

    details = {k: v for k, v in current_result.items() if k != "price"}
    prompt = (
        "You are a sharp travel price analyst sending a Telegram alert. "
        "Write a concise message (3–5 sentences) that a traveler will actually find useful.\n\n"
        f"Route      : {route['label']}\n"
        f"Travel date: {route['date']}\n"
        f"Current    : {currency} {price:,}\n"
        f"Target     : {currency} {route['max_price']:,}\n"
        f"Hit target : {'YES' if hit_target else 'NO — price dropped but still above target'}\n"
        f"Details    : {details}\n\n"
        f"{history_summary}\n\n"
        "Cover: is this price good vs. history, is the trend up or down, and give a clear "
        "booking recommendation. Use Telegram HTML formatting (<b> for key numbers). "
        "Open with a relevant emoji and the route name."
    )

    provider = _provider()
    if provider == "anthropic":
        return _anthropic_text(prompt, "claude-opus-4-7")
    elif provider == "openai":
        return _openai_text(prompt, "gpt-4o")
    elif provider == "gemini":
        return _gemini_text(prompt, "gemini-1.5-pro")
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}")


def decide_check(route: dict, history: list, last_check_time: str = None) -> dict:
    """Ask Haiku whether now is a good time to check prices for this route.

    Returns: {check_now: bool, confidence: float, reason: str, suggested_wait_hours: int}
    Falls back to check_now=True on any error so checks are never silently skipped.
    """
    from datetime import datetime

    fallback = {
        "check_now": True,
        "confidence": 0.0,
        "reason": "LLM unavailable — defaulting to check",
        "suggested_wait_hours": 0,
    }

    try:
        now = datetime.now()
        travel_date = route.get("date", "")
        days_until = None
        if travel_date:
            try:
                days_until = (datetime.strptime(travel_date, "%Y-%m-%d") - now).days
            except ValueError:
                pass

        if history:
            history_lines = "\n".join(
                f"  {h['checked_at'][:16]} | {route.get('currency', 'IDR')} {float(h['price']):,.0f}"
                for h in history[:10]
            )
            last_price = float(history[0]["price"])
            history_block = (
                f"Last known price: {route.get('currency', 'IDR')} {last_price:,.0f}\n"
                f"Last check time: {last_check_time or history[0].get('checked_at', 'unknown')}\n"
                f"Price history ({len(history)} records, newest first):\n{history_lines}"
            )
        else:
            history_block = "No price history yet. Use general knowledge only."

        days_str = f"{days_until} days" if days_until is not None else "unknown"

        system = DECIDE_CHECK_SYSTEM

        user = (
            f"Route     : {route.get('label', 'unknown')}\n"
            f"Type      : {route.get('type', 'unknown')}\n"
            f"Travel date: {travel_date} ({days_str} away)\n"
            f"Current datetime: {now.strftime('%Y-%m-%d %H:%M')} (local)\n"
            f"Day of week: {now.strftime('%A')}\n\n"
            f"{history_block}\n\n"
            "Should we check prices right now?"
        )

        provider = _provider()
        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            raw = message.content[0].text
        elif provider == "openai":
            import openai
            client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=256,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            raw = response.choices[0].message.content
        elif provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=os.environ["GEMINI_API_KEY"])
            gmodel = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system)
            response = gmodel.generate_content(user)
            raw = response.text
        else:
            return fallback

        result = json.loads(_strip_code_fences(raw))
        result.setdefault("check_now", True)
        result.setdefault("confidence", 0.5)
        result.setdefault("reason", "")
        result.setdefault("suggested_wait_hours", 0)
        return result

    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"decide_check failed: {e} — defaulting to check")
        return fallback


def categorize_expense(text: str) -> dict:
    """Parse Indonesian shorthand expense text.

    Understands: k=thousand, jt=million (IDR).
    Returns: {amount, currency, category, description}
    """
    prompt = (
        "Parse this expense description into structured JSON. "
        "Understand Indonesian shorthand: 'k' means thousand (e.g. 45k = 45000), "
        "'jt' means million (e.g. 2jt = 2000000). Currency defaults to IDR unless specified. "
        "Categories: food/transport/accommodation/activities/shopping/utilities/other. "
        "Respond ONLY with valid JSON like: "
        '{"amount": 45000, "currency": "IDR", "category": "food", "description": "lunch at warung"}\n\n'
        f"Expense: {text}"
    )
    provider = _provider()
    if provider == "anthropic":
        raw = _anthropic_text(prompt, "claude-haiku-4-5-20251001")
    elif provider == "openai":
        raw = _openai_text(prompt, "gpt-4o-mini")
    elif provider == "gemini":
        raw = _gemini_text(prompt, "gemini-1.5-flash")
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}")
    return json.loads(_strip_code_fences(raw))

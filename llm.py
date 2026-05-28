"""
llm.py — LLM provider abstraction.
Switch provider via LLM_PROVIDER env var: anthropic | openai | gemini
"""

import base64
import json
import os
import re

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

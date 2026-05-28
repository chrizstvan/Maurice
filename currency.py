"""Exchange rate conversion with 1-hour cache."""
import time
import httpx

_cache: dict = {}  # {(from, to): (rate, timestamp)}
_TTL = 3600


def convert(amount: float, from_cur: str, to_cur: str) -> float:
    """Convert amount from from_cur to to_cur using Frankfurter API with 1h cache."""
    if from_cur == to_cur:
        return amount

    key = (from_cur.upper(), to_cur.upper())
    cached = _cache.get(key)
    if cached is not None:
        rate, ts = cached
        if time.time() - ts < _TTL:
            return amount * rate

    url = f"https://api.frankfurter.app/latest?from={from_cur.upper()}&to={to_cur.upper()}"
    response = httpx.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()
    rate = data["rates"][to_cur.upper()]

    _cache[key] = (rate, time.time())
    return amount * rate

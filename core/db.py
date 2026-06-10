"""
db.py — Supabase abstraction layer.
All database calls go through this module.
"""

import os
from datetime import date, datetime, timezone
from typing import Optional

from supabase import create_client, Client


def _client() -> Client:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise RuntimeError(
            "Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY env vars."
        )
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Price history
# ---------------------------------------------------------------------------

def record(route_label: str, price: float, currency: str, details: dict) -> dict:
    """Insert a price record into price_history."""
    client = _client()
    row = {
        "route_label": route_label,
        "price": price,
        "currency": currency,
        "details": details,
    }
    result = client.table("price_history").insert(row).execute()
    return result.data[0] if result.data else {}


def get_recent_history(route_label: str, limit: int = 10) -> list:
    """Return the most recent price records for a route."""
    client = _client()
    result = (
        client.table("price_history")
        .select("*")
        .eq("route_label", route_label)
        .order("checked_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def get_last_price(route_label: str) -> Optional[float]:
    """Return the most recent price for a route, or None."""
    rows = get_recent_history(route_label, limit=1)
    if rows:
        return float(rows[0]["price"])
    return None


def get_week_history(route_label: str) -> list:
    """Return all price records for a route from the last 7 days, newest first."""
    from datetime import datetime, timedelta
    client = _client()
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    result = (
        client.table("price_history")
        .select("*")
        .eq("route_label", route_label)
        .gte("checked_at", since)
        .order("checked_at", desc=True)
        .execute()
    )
    return result.data or []


def get_all_subscribers() -> list[str]:
    """Return all unique chat_ids subscribed to any active route."""
    client = _client()
    active = (
        client.table("watched_routes").select("id").eq("active", True).execute()
    )
    route_ids = [r["id"] for r in (active.data or [])]
    if not route_ids:
        return []
    result = (
        client.table("route_subscribers")
        .select("chat_id")
        .in_("route_id", route_ids)
        .execute()
    )
    seen = set()
    unique = []
    for r in result.data or []:
        if r["chat_id"] not in seen:
            seen.add(r["chat_id"])
            unique.append(r["chat_id"])
    return unique


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------

def get_active_budget() -> Optional[dict]:
    """Return the most recently created active budget, or None."""
    client = _client()
    result = (
        client.table("budgets")
        .select("*")
        .eq("active", True)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def create_budget(
    name: str,
    type: str,
    start: str,
    end: str,
    total: float,
    currency: str = "IDR",
) -> dict:
    """Create a new budget and return the created row."""
    client = _client()
    row = {
        "name": name,
        "type": type,
        "start_date": start,
        "end_date": end,
        "total_amount": total,
        "currency": currency,
        "active": True,
    }
    result = client.table("budgets").insert(row).execute()
    return result.data[0] if result.data else {}


def add_expense(
    budget_id: int,
    category: str,
    amount: float,
    currency: str,
    description: str,
    expense_date: str,
    source: str,
) -> dict:
    """Insert an expense row and return it."""
    client = _client()
    row = {
        "budget_id": budget_id,
        "category": category,
        "amount": amount,
        "currency": currency,
        "description": description,
        "expense_date": expense_date,
        "source": source,
    }
    result = client.table("expenses").insert(row).execute()
    return result.data[0] if result.data else {}


def get_budget_summary(budget_id: int) -> dict:
    """Return {budget, total_spent, remaining, by_category}."""
    client = _client()

    budget_result = client.table("budgets").select("*").eq("id", budget_id).limit(1).execute()
    budget = budget_result.data[0] if budget_result.data else {}

    expenses_result = (
        client.table("expenses").select("*").eq("budget_id", budget_id).execute()
    )
    expenses = expenses_result.data or []

    by_category: dict = {}
    for e in expenses:
        cat = e.get("category", "other")
        by_category[cat] = by_category.get(cat, 0) + float(e.get("amount", 0))

    total_spent = sum(by_category.values())
    total_amount = float(budget.get("total_amount", 0))
    remaining = total_amount - total_spent

    return {
        "budget": budget,
        "total_spent": total_spent,
        "remaining": remaining,
        "by_category": by_category,
    }


def get_month_expenses(year: int, month: int) -> list:
    """Return all expenses whose expense_date falls in the given month."""
    client = _client()
    start = f"{year:04d}-{month:02d}-01"
    # Last day: use next month's first day
    if month == 12:
        end = f"{year + 1:04d}-01-01"
    else:
        end = f"{year:04d}-{month + 1:02d}-01"

    result = (
        client.table("expenses")
        .select("*")
        .gte("expense_date", start)
        .lt("expense_date", end)
        .execute()
    )
    return result.data or []


def get_recurring_expenses() -> list:
    """Return all active recurring expenses."""
    client = _client()
    result = (
        client.table("recurring_expenses").select("*").eq("active", True).execute()
    )
    return result.data or []


def create_monthly_budget_from_template(
    name: str, total: float, currency: str = "IDR"
) -> dict:
    """Create a budget for the current month and pre-load all active recurring expenses."""
    today = date.today()
    start = today.replace(day=1).isoformat()
    # End = last day of month (first day of next month minus 1)
    if today.month == 12:
        end = date(today.year + 1, 1, 1)
    else:
        end = date(today.year, today.month + 1, 1)
    # Store end as last day of month
    import datetime as dt
    end_date = (end - dt.timedelta(days=1)).isoformat()

    budget = create_budget(
        name=name,
        type="monthly",
        start=start,
        end=end_date,
        total=total,
        currency=currency,
    )

    recurring = get_recurring_expenses()
    for r in recurring:
        add_expense(
            budget_id=budget["id"],
            category=r.get("category", "other"),
            amount=float(r.get("amount", 0)),
            currency=r.get("currency", currency),
            description=r.get("name", ""),
            expense_date=start,  # first of month
            source="recurring",
        )

    return budget


# ---------------------------------------------------------------------------
# Watched routes
# ---------------------------------------------------------------------------

def deactivate_expired_routes() -> list:
    """Set active=False for all routes whose travel date has passed. Returns deactivated rows."""
    client = _client()
    today = date.today().isoformat()
    result = (
        client.table("watched_routes")
        .update({"active": False})
        .eq("active", True)
        .lt("travel_date", today)
        .execute()
    )
    return result.data or []


def get_watched_routes() -> dict:
    """Return active routes grouped by type, with subscribers list attached to each route."""
    client = _client()
    result = (
        client.table("watched_routes")
        .select("*, route_subscribers(chat_id)")
        .eq("active", True)
        .order("created_at")
        .execute()
    )
    grouped: dict = {}
    for row in result.data or []:
        route_type = row["type"]
        subscribers = [s["chat_id"] for s in (row.get("route_subscribers") or [])]
        entry = {
            "id":          row["id"],
            "from":        row["from_code"],
            "to":          row["to_code"],
            "date":        str(row["travel_date"]),
            "max_price":   float(row["max_price"]),
            "currency":    row["currency"],
            "label":       row["label"],
            "subscribers": subscribers,
        }
        if row.get("seat_class"):
            entry["seat_class"] = row["seat_class"]
        if row.get("params"):
            entry.update(row["params"])
        grouped.setdefault(route_type, []).append(entry)
    return grouped


def add_watched_route(
    route_type: str,
    from_code: str,
    to_code: str,
    label: str,
    travel_date: str,
    max_price: float,
    currency: str = "IDR",
    seat_class: str = None,
    params: dict = None,
    chat_id: str = None,
) -> tuple[dict, bool]:
    """Add a route and subscribe chat_id to it.

    Deduplicates: if an identical active route already exists, reuses it.
    Returns (route_row, created) where created=False means route already existed.
    """
    client = _client()

    # Check for existing identical active route
    query = (
        client.table("watched_routes")
        .select("*")
        .eq("type", route_type)
        .eq("from_code", from_code)
        .eq("to_code", to_code)
        .eq("travel_date", travel_date)
        .eq("active", True)
    )
    if seat_class:
        query = query.eq("seat_class", seat_class.upper())
    existing = query.limit(1).execute()

    if existing.data:
        route_row = existing.data[0]
        created = False
    else:
        row = {
            "type":        route_type,
            "from_code":   from_code,
            "to_code":     to_code,
            "label":       label,
            "travel_date": travel_date,
            "max_price":   max_price,
            "currency":    currency,
            "active":      True,
        }
        if seat_class:
            row["seat_class"] = seat_class.upper()
        if params:
            row["params"] = params
        result = client.table("watched_routes").insert(row).execute()
        route_row = result.data[0] if result.data else {}
        created = True

    if chat_id and route_row.get("id"):
        client.table("route_subscribers").upsert(
            {"route_id": route_row["id"], "chat_id": str(chat_id)},
            on_conflict="route_id,chat_id",
        ).execute()

    return route_row, created


def remove_watched_route(route_id: int, chat_id: str = None) -> Optional[dict]:
    """Unsubscribe chat_id from a route. Deactivates the route if no subscribers remain."""
    client = _client()

    route_result = (
        client.table("watched_routes").select("*").eq("id", route_id).limit(1).execute()
    )
    if not route_result.data:
        return None
    route_row = route_result.data[0]

    if chat_id:
        client.table("route_subscribers").delete().eq("route_id", route_id).eq("chat_id", str(chat_id)).execute()

    remaining = (
        client.table("route_subscribers").select("id").eq("route_id", route_id).execute()
    )
    if not remaining.data:
        client.table("watched_routes").update({"active": False}).eq("id", route_id).execute()

    return route_row


def list_watched_routes(chat_id: str = None) -> list:
    """Return active watched routes. If chat_id given, return only that user's subscriptions."""
    client = _client()
    if chat_id:
        subs = (
            client.table("route_subscribers")
            .select("route_id")
            .eq("chat_id", str(chat_id))
            .execute()
        )
        route_ids = [s["route_id"] for s in (subs.data or [])]
        if not route_ids:
            return []
        result = (
            client.table("watched_routes")
            .select("*")
            .eq("active", True)
            .in_("id", route_ids)
            .order("created_at")
            .execute()
        )
    else:
        result = (
            client.table("watched_routes")
            .select("*")
            .eq("active", True)
            .order("created_at")
            .execute()
        )
    return result.data or []


def get_route_subscribers(route_id: int) -> list[str]:
    """Return list of chat_ids subscribed to a route."""
    client = _client()
    result = (
        client.table("route_subscribers")
        .select("chat_id")
        .eq("route_id", route_id)
        .execute()
    )
    return [r["chat_id"] for r in (result.data or [])]


def get_price_context_for_trip(destination: str, travel_date: str) -> list:
    """Return recent price history records matching the destination."""
    client = _client()
    result = (
        client.table("price_history")
        .select("*")
        .ilike("route_label", f"%{destination}%")
        .order("checked_at", desc=True)
        .limit(10)
        .execute()
    )
    return result.data or []

"""
db.py — Supabase abstraction layer.
All database calls go through this module.
"""

import os
from datetime import date, datetime
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

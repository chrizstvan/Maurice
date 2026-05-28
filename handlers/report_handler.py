"""Report command — show budget summary with LLM insight."""
import db
import llm
from datetime import date
from telegram import Update
from telegram.ext import ContextTypes


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget = db.get_active_budget()
    if not budget:
        await update.message.reply_text("No active budget. Use /budget to create one.")
        return

    summary = db.get_budget_summary(budget["id"])
    days_remaining = (date.fromisoformat(budget["end_date"]) - date.today()).days

    llm_context = {
        "budget": budget,
        "total_spent": summary["total_spent"],
        "remaining": summary["remaining"],
        "by_category": summary["by_category"],
        "days_remaining": max(days_remaining, 0),
    }

    # For trip budgets, add price context
    if budget.get("type") == "trip":
        destination = budget["name"].split()[-1]  # rough heuristic
        price_ctx = db.get_price_context_for_trip(destination, budget["end_date"])
        if price_ctx:
            llm_context["price_history"] = price_ctx

    lines = [
        f"<b>{budget['name']}</b>",
        f"Budget: {budget['currency']} {budget['total_amount']:,.0f}",
        f"Spent:  {budget['currency']} {summary['total_spent']:,.0f}",
        f"Left:   {budget['currency']} {summary['remaining']:,.0f}",
        "",
        "<b>By category:</b>",
    ]
    for cat, amt in sorted(summary["by_category"].items(), key=lambda x: -x[1]):
        lines.append(f"  {cat.title()}: {amt:,.0f}")

    lines += ["", "<b>Insight:</b>", llm.reason_budget(llm_context)]
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

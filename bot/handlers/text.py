"""Text message handler — parse expense input or handle confirmations."""
from core import db, llm
from datetime import date
from telegram import Update
from telegram.ext import ContextTypes


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()

    # Handle confirmation of pending expense
    pending = context.user_data.get("pending_expense")
    if pending and text in ("yes", "y", "ya", "ok"):
        expense = db.add_expense(
            budget_id=pending["budget_id"],
            category=pending["category"],
            amount=pending["amount"],
            currency=pending["currency"],
            description=pending["description"],
            expense_date=date.today().isoformat(),
            source=pending["source"],
        )
        context.user_data.pop("pending_expense", None)

        summary = db.get_budget_summary(pending["budget_id"])
        budget = summary["budget"]
        remaining = summary["remaining"]
        days_remaining = (
            __import__("datetime").date.fromisoformat(budget["end_date"]) - date.today()
        ).days

        insight = llm.reason_budget({
            "budget": budget,
            "total_spent": summary["total_spent"],
            "remaining": remaining,
            "by_category": summary["by_category"],
            "days_remaining": days_remaining,
        })
        await update.message.reply_text(
            f"Added {pending['currency']} {pending['amount']:,.0f} ({pending['category']}).\n\n{insight}"
        )
        return

    if pending and text in ("no", "n", "cancel"):
        context.user_data.pop("pending_expense", None)
        await update.message.reply_text("Cancelled.")
        return

    # Parse as new expense
    budget = db.get_active_budget()
    if not budget:
        await update.message.reply_text("No active budget. Use /budget to create one first.")
        return

    try:
        parsed = llm.categorize_expense(update.message.text)
    except Exception as e:
        await update.message.reply_text(f"Could not parse expense: {e}")
        return

    context.user_data["pending_expense"] = {
        "budget_id": budget["id"],
        "budget_name": budget["name"],
        "category": parsed.get("category", "other"),
        "amount": parsed.get("amount", 0),
        "currency": parsed.get("currency", "IDR"),
        "description": parsed.get("description", update.message.text),
        "source": "manual",
    }

    summary = db.get_budget_summary(budget["id"])
    cat_spent = summary["by_category"].get(parsed.get("category", "other"), 0)

    msg = (
        f"{parsed.get('category', 'other').title()} — "
        f"{parsed.get('currency', 'IDR')} {parsed.get('amount', 0):,.0f}\n"
        f"<i>{parsed.get('description', '')}</i>\n"
        f"Add to \"{budget['name']}\"? "
        f"(Category total so far: {cat_spent:,.0f})\n\n"
        "Reply <b>yes</b> to confirm or <b>no</b> to cancel."
    )
    await update.message.reply_text(msg, parse_mode="HTML")

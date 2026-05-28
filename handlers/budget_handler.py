"""Budget and trip command handlers."""
import db
import llm
from datetime import date
from telegram import Update
from telegram.ext import ContextTypes


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "Hi! I'm Maurice, your finance assistant.\n\n"
        "Commands:\n"
        "/budget — view or create a budget\n"
        "/report — budget summary with insights\n"
        "/newtrip &lt;name&gt; &lt;amount&gt; &lt;start&gt; &lt;end&gt; — create trip budget\n"
        "/trip — active trip summary\n"
        "/month — current month summary\n"
        "/setbudget &lt;amount&gt; — set monthly budget\n"
        "/recurring — list recurring expenses\n\n"
        "Send a photo of a receipt or type an expense like <i>45k food lunch</i>."
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def budget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget = db.get_active_budget()
    if not budget:
        await update.message.reply_text(
            "No active budget.\n"
            "Create a monthly budget: /setbudget 5000000\n"
            "Create a trip budget: /newtrip BaliAug 3000000 2026-08-15 2026-08-20"
        )
        return
    summary = db.get_budget_summary(budget["id"])
    days_remaining = (date.fromisoformat(budget["end_date"]) - date.today()).days
    pct = (summary["total_spent"] / budget["total_amount"] * 100) if budget["total_amount"] else 0
    msg = (
        f"<b>{budget['name']}</b> ({budget['type']})\n"
        f"{budget['start_date']} → {budget['end_date']} ({max(days_remaining, 0)} days left)\n"
        f"Spent: {summary['total_spent']:,.0f} / {budget['total_amount']:,.0f} {budget['currency']} ({pct:.0f}%)\n"
        f"Remaining: {summary['remaining']:,.0f} {budget['currency']}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def newtrip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Usage: /newtrip BaliAug 3000000 2026-08-15 2026-08-20
    args = context.args
    if not args or len(args) < 4:
        await update.message.reply_text(
            "Usage: /newtrip &lt;name&gt; &lt;budget&gt; &lt;start YYYY-MM-DD&gt; &lt;end YYYY-MM-DD&gt;",
            parse_mode="HTML",
        )
        return
    name, total_str, start, end = args[0], args[1], args[2], args[3]
    try:
        total = float(total_str.replace("_", ""))
    except ValueError:
        await update.message.reply_text("Invalid budget amount.")
        return
    budget = db.create_budget(name=name, type="trip", start=start, end=end, total=total)
    await update.message.reply_text(
        f"Trip budget <b>{name}</b> created.\n"
        f"{start} → {end} | IDR {total:,.0f}",
        parse_mode="HTML",
    )


async def trip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget = db.get_active_budget()
    if not budget or budget.get("type") != "trip":
        await update.message.reply_text("No active trip budget. Use /newtrip to create one.")
        return
    summary = db.get_budget_summary(budget["id"])
    days_remaining = (date.fromisoformat(budget["end_date"]) - date.today()).days
    destination = budget["name"]
    price_ctx = db.get_price_context_for_trip(destination, budget["end_date"])

    llm_context = {
        "budget": budget,
        "total_spent": summary["total_spent"],
        "remaining": summary["remaining"],
        "by_category": summary["by_category"],
        "days_remaining": max(days_remaining, 0),
    }
    if price_ctx:
        llm_context["price_history"] = price_ctx

    insight = llm.reason_budget(llm_context)
    msg = (
        f"<b>Trip: {budget['name']}</b>\n"
        f"{budget['start_date']} → {budget['end_date']} ({max(days_remaining, 0)} days left)\n"
        f"Spent: {summary['total_spent']:,.0f} / {budget['total_amount']:,.0f} {budget['currency']}\n"
        f"Remaining: {summary['remaining']:,.0f}\n\n"
        f"{insight}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def month_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = date.today()
    expenses = db.get_month_expenses(today.year, today.month)
    total = sum(e["amount"] for e in expenses)
    by_cat: dict = {}
    for e in expenses:
        by_cat[e["category"]] = by_cat.get(e["category"], 0) + e["amount"]
    lines = [
        f"<b>{today.strftime('%B %Y')}</b>",
        f"Total spent: {total:,.0f} IDR",
        "",
        "<b>By category:</b>",
    ]
    for cat, amt in sorted(by_cat.items(), key=lambda x: -x[1]):
        lines.append(f"  {cat.title()}: {amt:,.0f}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def setbudget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /setbudget &lt;amount&gt;  e.g. /setbudget 8000000", parse_mode="HTML")
        return
    try:
        total = float(args[0].replace("_", ""))
    except ValueError:
        await update.message.reply_text("Invalid amount.")
        return
    today = date.today()
    name = today.strftime("%B %Y")
    budget = db.create_monthly_budget_from_template(name=name, total=total)
    recurring = db.get_recurring_expenses()
    recurring_total = sum(r["amount"] for r in recurring)
    await update.message.reply_text(
        f"<b>{name}</b> budget created.\n"
        f"Total: IDR {total:,.0f}\n"
        f"Pre-loaded {len(recurring)} recurring expenses totalling {recurring_total:,.0f}.",
        parse_mode="HTML",
    )


async def recurring_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    items = db.get_recurring_expenses()
    if not items:
        await update.message.reply_text("No recurring expenses configured. Add them in Supabase.")
        return
    lines = ["<b>Recurring expenses:</b>"]
    for item in items:
        lines.append(
            f"  {item['name']} — {item['currency']} {item['amount']:,.0f} ({item['category']})"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

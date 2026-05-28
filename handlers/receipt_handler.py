"""Receipt photo handler — extract expense from photo, confirm with user, save."""
import db
import llm
from datetime import date
from telegram import Update
from telegram.ext import ContextTypes


async def receipt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Download largest photo
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    image_bytes = bytes(await file.download_as_bytearray())

    await update.message.reply_text("Reading receipt...")

    try:
        receipt = llm.read_receipt(image_bytes)
    except Exception as e:
        await update.message.reply_text(f"Could not read receipt: {e}")
        return

    budget = db.get_active_budget()
    if not budget:
        await update.message.reply_text("No active budget. Use /budget to create one.")
        return

    summary = db.get_budget_summary(budget["id"])
    cat_spent = summary["by_category"].get(receipt.get("category_guess", "other"), 0)

    # Store pending for confirmation
    context.user_data["pending_expense"] = {
        "budget_id": budget["id"],
        "budget_name": budget["name"],
        "category": receipt.get("category_guess", "other"),
        "amount": receipt.get("amount", 0),
        "currency": receipt.get("currency", "IDR"),
        "description": receipt.get("merchant", ""),
        "source": "receipt",
    }

    msg = (
        f"I see: <b>{receipt.get('merchant', 'Unknown')}</b> — "
        f"{receipt.get('currency', 'IDR')} {receipt.get('amount', 0):,.0f} "
        f"({receipt.get('category_guess', 'other').title()})\n"
        f"Add to \"{budget['name']}\"? "
        f"You've spent {cat_spent:,.0f} in {receipt.get('category_guess', 'other')} so far.\n\n"
        "Reply <b>yes</b> to confirm or <b>no</b> to cancel."
    )
    await update.message.reply_text(msg, parse_mode="HTML")

#!/usr/bin/env python3
"""bot.py — Always-on Telegram budget bot. Deploy on Render."""
import os
from pathlib import Path

os.chdir(Path(__file__).parent)

import config
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from handlers.receipt_handler import receipt_handler
from handlers.text_handler import text_handler
from handlers.report_handler import report_command
from handlers.budget_handler import (
    budget_command,
    newtrip_command,
    trip_command,
    month_command,
    setbudget_command,
    recurring_command,
    start_command,
)


def main():
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, receipt_handler))
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("budget", budget_command))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("newtrip", newtrip_command))
    app.add_handler(CommandHandler("trip", trip_command))
    app.add_handler(CommandHandler("month", month_command))
    app.add_handler(CommandHandler("setbudget", setbudget_command))
    app.add_handler(CommandHandler("recurring", recurring_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.run_polling()


if __name__ == "__main__":
    main()

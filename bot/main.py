#!/usr/bin/env python3
"""bot/main.py — Always-on Telegram budget bot. Deploy on Render."""
import os
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from core import config
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from bot.handlers.receipt import receipt_handler
from bot.handlers.text import text_handler
from bot.handlers.report import report_command
from bot.handlers.routes import addroute_command, routes_command, removeroute_command
from bot.handlers.budget import (
    budget_command, newtrip_command, trip_command, month_command,
    setbudget_command, recurring_command, start_command,
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
    app.add_handler(CommandHandler("addroute", addroute_command))
    app.add_handler(CommandHandler("routes", routes_command))
    app.add_handler(CommandHandler("removeroute", removeroute_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.run_polling()

if __name__ == "__main__":
    main()

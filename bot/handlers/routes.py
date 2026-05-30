"""Route management commands — add, list, and remove watched price routes."""
from core import db
from monitor.checkers import REGISTRY
from telegram import Update
from telegram.ext import ContextTypes

_TYPE_EMOJI = {"flights": "✈️", "trains": "🚂", "hotels": "🏨"}
_SEAT_CLASS_LABELS = {"EKS": "Eksekutif", "BIS": "Bisnis", "EKO": "Ekonomi"}

USAGE = """<b>Route commands</b>

Add a flight:
<code>/addroute flights CGK DPS 2026-08-15 500000</code>

Add a train (seat class: EKS / BIS / EKO):
<code>/addroute trains GMR YK 2026-08-15 350000 EKS</code>

Add a hotel (use _ for spaces in destination):
<code>/addroute hotels Bali 2026-08-15 2026-08-20 500000</code>
<code>/addroute hotels Seminyak_Bali 2026-08-15 2026-08-20 500000 2</code>
(last number = guests, default 2)

List your routes:  /routes
Remove route: /removeroute &lt;id&gt;
"""


async def addroute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text(USAGE, parse_mode="HTML")
        return

    route_type = args[0].lower()
    if route_type not in REGISTRY:
        types = ", ".join(REGISTRY.keys())
        await update.message.reply_text(f"Unknown type <b>{route_type}</b>. Available: {types}", parse_mode="HTML")
        return

    chat_id = str(update.effective_chat.id)

    if route_type == "hotels":
        await _addroute_hotel(update, args, chat_id)
    else:
        await _addroute_transport(update, args, route_type, chat_id)


async def _addroute_transport(update, args: list, route_type: str, chat_id: str):
    # flights / trains: type from_code to_code date max_price [seat_class]
    if len(args) < 5:
        await update.message.reply_text(USAGE, parse_mode="HTML")
        return

    from_code   = args[1].upper()
    to_code     = args[2].upper()
    travel_date = args[3]
    try:
        max_price = float(args[4].replace("_", "").replace(",", ""))
    except ValueError:
        await update.message.reply_text("Invalid price. Use a number, e.g. <code>500000</code>", parse_mode="HTML")
        return

    seat_class = args[5].upper() if len(args) > 5 else None
    if route_type == "trains" and not seat_class:
        await update.message.reply_text(
            "Trains require a seat class: <code>EKS</code>, <code>BIS</code>, or <code>EKO</code>\n"
            "Example: <code>/addroute trains GMR YK 2026-08-15 350000 EKS</code>",
            parse_mode="HTML",
        )
        return

    label = f"{from_code} → {to_code}"
    if seat_class:
        label += f" ({_SEAT_CLASS_LABELS.get(seat_class, seat_class)})"

    try:
        row, created = db.add_watched_route(
            route_type=route_type,
            from_code=from_code,
            to_code=to_code,
            label=label,
            travel_date=travel_date,
            max_price=max_price,
            seat_class=seat_class,
            chat_id=chat_id,
        )
    except Exception as e:
        await update.message.reply_text(f"Failed to save route: {e}")
        return

    emoji = _TYPE_EMOJI.get(route_type, "🔍")
    status = "Watching" if created else "Subscribed to existing watch for"
    await update.message.reply_text(
        f"✓ {status} {emoji} <b>{label}</b>\n"
        f"Date: {travel_date} | Target: IDR {max_price:,.0f}\n"
        f"ID: {row.get('id')} — use /removeroute {row.get('id')} to unsubscribe.",
        parse_mode="HTML",
    )


async def _addroute_hotel(update, args: list, chat_id: str):
    # hotels: type destination check_in check_out max_price [guests]
    if len(args) < 5:
        await update.message.reply_text(
            "Usage: <code>/addroute hotels Bali 2026-08-15 2026-08-20 500000</code>\n"
            "Use _ for spaces: <code>Seminyak_Bali</code>",
            parse_mode="HTML",
        )
        return

    destination = args[1].replace("_", " ")
    check_in    = args[2]
    check_out   = args[3]
    try:
        max_price = float(args[4].replace("_", "").replace(",", ""))
    except ValueError:
        await update.message.reply_text("Invalid price. Use a number, e.g. <code>500000</code>", parse_mode="HTML")
        return

    guests = 2
    if len(args) > 5:
        try:
            guests = int(args[5])
        except ValueError:
            pass

    label = f"Hotels in {destination}"
    try:
        row, created = db.add_watched_route(
            route_type="hotels",
            from_code=destination,
            to_code=destination,
            label=label,
            travel_date=check_in,
            max_price=max_price,
            params={"check_out": check_out, "guests": guests},
            chat_id=chat_id,
        )
    except Exception as e:
        await update.message.reply_text(f"Failed to save route: {e}")
        return

    try:
        from datetime import date
        nights = (date.fromisoformat(check_out) - date.fromisoformat(check_in)).days
    except Exception:
        nights = "?"

    status = "Watching" if created else "Subscribed to existing watch for"
    await update.message.reply_text(
        f"✓ {status} 🏨 <b>{label}</b>\n"
        f"{check_in} → {check_out} ({nights} nights, {guests} guests)\n"
        f"Target: IDR {max_price:,.0f}/night\n"
        f"ID: {row.get('id')} — use /removeroute {row.get('id')} to unsubscribe.",
        parse_mode="HTML",
    )


async def routes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    try:
        routes = db.list_watched_routes(chat_id=chat_id)
    except Exception as e:
        await update.message.reply_text(f"Could not load routes: {e}")
        return

    if not routes:
        await update.message.reply_text(
            "You have no routes being watched.\n\n" + USAGE, parse_mode="HTML"
        )
        return

    lines = ["<b>Your watched routes:</b>"]
    for r in routes:
        emoji = _TYPE_EMOJI.get(r["type"], "🔍")
        if r["type"] == "hotels":
            params = r.get("params") or {}
            check_out = params.get("check_out", "?")
            guests = params.get("guests", 2)
            lines.append(
                f"{r['id']}. {emoji} {r['label']}\n"
                f"    {r['travel_date']} → {check_out} | {guests} guests\n"
                f"    Target: {r['currency']} {float(r['max_price']):,.0f}/night"
            )
        else:
            seat = f" {r['seat_class']}" if r.get("seat_class") else ""
            lines.append(
                f"{r['id']}. {emoji} {r['label']}{seat} — {r['travel_date']}\n"
                f"    Target: {r['currency']} {float(r['max_price']):,.0f}"
            )

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def removeroute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /removeroute &lt;id&gt;\nGet IDs from /routes", parse_mode="HTML")
        return

    try:
        route_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID must be a number.")
        return

    chat_id = str(update.effective_chat.id)
    try:
        row = db.remove_watched_route(route_id, chat_id=chat_id)
    except Exception as e:
        await update.message.reply_text(f"Failed to remove route: {e}")
        return

    if not row:
        await update.message.reply_text(f"No active route with ID {route_id}.")
        return

    await update.message.reply_text(
        f"✓ Unsubscribed from <b>{row.get('label', route_id)}</b>.\n"
        f"(Route stays active for other subscribers if any remain.)",
        parse_mode="HTML",
    )

"""
checkers/trains.py
Checks KAI train prices using the kai-python unofficial API wrapper.
Install: pip install kai-python
"""

import logging
from typing import Optional
from .base import BaseChecker

logger = logging.getLogger(__name__)


class TrainsChecker(BaseChecker):
    checker_type = "trains"

    def price_key(self, route: dict) -> str:
        return f"train_{route['from']}_{route['to']}_{route['date']}_{route['seat_class']}"

    def fetch(self, route: dict) -> Optional[dict]:
        try:
            from kai import KAI
        except ImportError:
            logger.error("kai-python not installed. Run: pip install kai-python")
            return None

        try:
            kai = KAI()

            parts = route["date"].split("-")
            kai_date = f"{parts[2]}-{parts[1]}-{parts[0]}"

            trains = kai.get_schedule(
                origin=route["from"],
                destination=route["to"],
                date=kai_date,
            )

            if not trains:
                logger.warning(f"No trains found for {route['from']}→{route['to']} on {route['date']}")
                return None

            seat_class = route["seat_class"]
            candidates = []
            for train in trains:
                for seat in train.get("seats", []):
                    if seat.get("subclass", "").startswith(seat_class) or seat.get("class") == seat_class:
                        price = seat.get("price", 0)
                        avail = seat.get("available", 0)
                        if avail > 0 and price > 0:
                            candidates.append({
                                "price":      price,
                                "train_name": train.get("train_name", "Unknown"),
                                "departure":  train.get("departure_time", ""),
                                "arrival":    train.get("arrival_time", ""),
                                "available":  avail,
                            })

            if not candidates:
                logger.warning(f"No available {seat_class} seats for {route['from']}→{route['to']} on {route['date']}")
                return None

            cheapest = min(candidates, key=lambda x: x["price"])
            logger.info(
                f"Cheapest KAI {route['from']}→{route['to']} [{seat_class}]: "
                f"IDR {cheapest['price']:,} ({cheapest['train_name']})"
            )
            return cheapest

        except Exception as e:
            logger.error(f"KAI check failed for {route['from']}→{route['to']}: {e}")
            return None

    def format_alert(self, route: dict, result: dict) -> str:
        return (
            f"🚂 <b>TRAIN PRICE ALERT (KAI)</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🛤️ Route   : {route['label']}\n"
            f"📅 Date    : {route['date']}\n"
            f"🚄 Train   : {result.get('train_name', 'Unknown')}\n"
            f"💰 Price   : IDR {result['price']:,}\n"
            f"🎯 Target  : IDR {route['max_price']:,}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👉 Book now on KAI Access!"
        )

    def format_price_drop(self, route: dict, old_price: int, new_price: int) -> str:
        return (
            f"📉 <b>Train Price Drop (FYI)</b>\n"
            f"🚂 {route['label']} on {route['date']}\n"
            f"Was: IDR {old_price:,} → Now: IDR {new_price:,}\n"
            f"(Still above your target of IDR {route['max_price']:,})"
        )

"""
checkers/flights.py
Checks flight prices via SerpAPI (Google Flights).
"""

import requests
import logging
from typing import Optional
from .base import BaseChecker

logger = logging.getLogger(__name__)


class FlightsChecker(BaseChecker):
    checker_type = "flights"

    def price_key(self, route: dict) -> str:
        return f"flight_{route['from']}_{route['to']}_{route['date']}"

    def fetch(self, route: dict) -> Optional[dict]:
        url = "https://serpapi.com/search"
        params = {
            "engine":        "google_flights",
            "departure_id":  route["from"],
            "arrival_id":    route["to"],
            "outbound_date": route["date"],
            "currency":      route.get("currency", "IDR"),
            "hl":            "en",
            "type":          "2",
            "api_key":       self.config.SERPAPI_KEY,
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            all_flights = []
            for group in ["best_flights", "other_flights"]:
                for flight in data.get(group, []):
                    price = flight.get("price")
                    if price is not None:
                        legs = flight.get("flights", [])
                        airline = legs[0].get("airline", "Unknown") if legs else ""
                        all_flights.append({"price": price, "airline": airline})

            if not all_flights:
                logger.warning(f"No flights found for {route['from']}→{route['to']} on {route['date']}")
                return None

            cheapest = min(all_flights, key=lambda x: x["price"])
            logger.info(
                f"Cheapest flight {route['from']}→{route['to']}: "
                f"{route.get('currency', 'IDR')} {cheapest['price']:,} ({cheapest['airline']})"
            )
            return cheapest

        except requests.RequestException as e:
            logger.error(f"SerpAPI request failed: {e}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse SerpAPI response: {e}")
            return None

    def format_alert(self, route: dict, result: dict) -> str:
        currency = route.get("currency", "IDR")
        return (
            f"✈️ <b>FLIGHT PRICE ALERT</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🛫 Route   : {route['label']}\n"
            f"📅 Date    : {route['date']}\n"
            f"✈️ Airline  : {result.get('airline', 'Unknown')}\n"
            f"💰 Price   : {currency} {result['price']:,}\n"
            f"🎯 Target  : {currency} {route['max_price']:,}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👉 Book now before it goes up!"
        )

    def format_price_drop(self, route: dict, old_price: int, new_price: int) -> str:
        currency = route.get("currency", "IDR")
        return (
            f"📉 <b>Price Drop (FYI)</b>\n"
            f"✈️ {route['label']} on {route['date']}\n"
            f"Was: {currency} {old_price:,} → Now: {currency} {new_price:,}\n"
            f"(Still above your target of {currency} {route['max_price']:,})"
        )

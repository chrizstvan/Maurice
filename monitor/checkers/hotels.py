"""
checkers/hotels.py
Checks hotel prices via SerpAPI (Google Hotels).
"""

import requests
import logging
from typing import Optional
from .base import BaseChecker

logger = logging.getLogger(__name__)


class HotelsChecker(BaseChecker):
    checker_type = "hotels"

    def price_key(self, route: dict) -> str:
        dest = route["from"].replace(" ", "_")
        check_out = route.get("check_out", "")
        return f"hotel_{dest}_{route['date']}_{check_out}"

    def fetch(self, route: dict) -> Optional[dict]:
        params = {
            "engine":          "google_hotels",
            "q":               f"{route['from']} hotels",
            "check_in_date":   route["date"],
            "check_out_date":  route.get("check_out", ""),
            "adults":          str(route.get("guests", 2)),
            "currency":        route.get("currency", "IDR"),
            "hl":              "en",
            "api_key":         self.config.SERPAPI_KEY,
        }
        try:
            resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            properties = data.get("properties", [])
            if not properties:
                logger.warning(f"No hotels found for {route['from']} on {route['date']}")
                return None

            candidates = []
            for prop in properties:
                rate = prop.get("rate_per_night", {})
                price = rate.get("extracted_lowest")
                if price is not None:
                    candidates.append({
                        "price":   price,
                        "name":    prop.get("name", "Unknown"),
                        "rating":  prop.get("overall_rating"),
                        "reviews": prop.get("reviews"),
                    })

            if not candidates:
                logger.warning(f"No priced hotels found for {route['from']}")
                return None

            cheapest = min(candidates, key=lambda x: x["price"])
            nights = self._nights(route)
            logger.info(
                f"Cheapest hotel in {route['from']}: "
                f"{route.get('currency', 'IDR')} {cheapest['price']:,}/night "
                f"— {cheapest['name']} ({nights} nights)"
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
        nights = self._nights(route)
        total = result["price"] * nights
        rating = f"{result['rating']} ⭐" if result.get("rating") else "N/A"
        reviews = f"{result['reviews']:,}" if result.get("reviews") else "N/A"
        return (
            f"🏨 <b>HOTEL PRICE ALERT</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📍 Destination : {route['label']}\n"
            f"📅 Check-in    : {route['date']}\n"
            f"📅 Check-out   : {route.get('check_out', '—')}\n"
            f"🏩 Hotel       : {result['name']}\n"
            f"⭐ Rating      : {rating} ({reviews} reviews)\n"
            f"💰 Per night   : {currency} {result['price']:,}\n"
            f"💰 Total ({nights}n) : {currency} {total:,}\n"
            f"🎯 Target/night: {currency} {route['max_price']:,}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👉 Book now before it fills up!"
        )

    def format_price_drop(self, route: dict, old_price: int, new_price: int) -> str:
        currency = route.get("currency", "IDR")
        nights = self._nights(route)
        return (
            f"📉 <b>Hotel Price Drop (FYI)</b>\n"
            f"🏨 {route['label']} | {route['date']} → {route.get('check_out', '—')}\n"
            f"Was: {currency} {old_price:,} → Now: {currency} {new_price:,}/night\n"
            f"Total saving: {currency} {(old_price - new_price) * nights:,} over {nights} nights\n"
            f"(Still above your target of {currency} {route['max_price']:,}/night)"
        )

    @staticmethod
    def _nights(route: dict) -> int:
        try:
            from datetime import date
            ci = date.fromisoformat(route["date"])
            co = date.fromisoformat(route["check_out"])
            return max((co - ci).days, 1)
        except Exception:
            return 1

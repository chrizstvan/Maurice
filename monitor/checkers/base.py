"""
checkers/base.py
Abstract base class for all price checkers.

To add a new checker type:
1. Create monitor/checkers/<type>.py with a class extending BaseChecker
2. Add it to the REGISTRY in monitor/checkers/__init__.py
3. Add its routes under the matching key in core/config.py CHECKER_ROUTES

WARNING: Never change price_key() return values — doing so silently loses
price history for all existing routes of that checker type.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class BaseChecker(ABC):
    checker_type: str  # subclasses declare this as a class attribute

    def __init__(self, routes: list, config):
        self.routes = routes
        self.config = config

    @abstractmethod
    def price_key(self, route: dict) -> str:
        """Return a stable, unique key for this route in last_prices.json."""

    @abstractmethod
    def fetch(self, route: dict) -> Optional[dict]:
        """
        Call the external API for one route.
        Must return a dict with at least {"price": int|float}, or None on failure.
        """

    @abstractmethod
    def format_alert(self, route: dict, result: dict) -> str:
        """Return HTML-formatted Telegram message for a price-at-or-below-target hit."""

    def format_price_drop(self, route: dict, old_price: int, new_price: int) -> str:
        return (
            f"📉 <b>Price Drop (FYI)</b>\n"
            f"Route  : {route['label']} on {route['date']}\n"
            f"Was: {old_price:,} → Now: {new_price:,}\n"
            f"(Still above your target of {route['max_price']:,})"
        )

    def run(
        self,
        last_prices: dict,
        notify_fn,
        record_fn=None,
        get_history_fn=None,
        reason_fn=None,
    ) -> None:
        """
        Generic check loop. Iterates routes, fetches prices, compares to target
        and last known price, calls notify_fn when alerting. Mutates last_prices
        in place — caller owns loading and saving.

        Optional callbacks:
          record_fn(route_label, price, currency, details) — persist to DB
          get_history_fn(route_label) -> list — fetch past price records from DB
          reason_fn(route, result, history) -> str — LLM-generated alert message;
              falls back to format_alert / format_price_drop if unavailable or raises
        """
        logger.info(f"=== Checking {self.checker_type.upper()} ===")

        for route in self.routes:
            key = self.price_key(route)
            logger.info(f"Checking {route['label']} on {route['date']}...")

            try:
                result = self.fetch(route)
            except Exception as e:
                logger.error(f"Unexpected error fetching {route['label']}: {e}")
                result = None

            if result is None:
                from services.notify import format_error_alert
                notify_fn(format_error_alert(self.checker_type, f"No data for {route['label']}"))
                continue

            price = result["price"]
            last_price = last_prices.get(key)

            # Fetch history before recording so it contains only past data points
            history = []
            if get_history_fn is not None:
                try:
                    history = get_history_fn(route["label"])
                except Exception as e:
                    logger.warning(f"Could not fetch price history for {route['label']}: {e}")

            should_alert = price <= route["max_price"]
            should_drop_notify = not should_alert and last_price is not None and price < last_price

            if should_alert or should_drop_notify:
                if reason_fn is not None:
                    try:
                        message = reason_fn(route, result, history)
                    except Exception as e:
                        logger.warning(f"LLM reasoning failed, falling back to template: {e}")
                        message = (
                            self.format_alert(route, result)
                            if should_alert
                            else self.format_price_drop(route, last_price, price)
                        )
                else:
                    message = (
                        self.format_alert(route, result)
                        if should_alert
                        else self.format_price_drop(route, last_price, price)
                    )

                if should_alert:
                    logger.info(f"ALERT: {route['label']} is {price:,} (target: {route['max_price']:,})")
                else:
                    logger.info(f"Price dropped: {route['label']} {last_price:,} → {price:,}")

                notify_fn(message)
            else:
                logger.info(f"No alert for {route['label']} — price {price:,}")

            last_prices[key] = price

            if record_fn is not None:
                record_fn(
                    route["label"],
                    price,
                    route.get("currency", "IDR"),
                    result,
                )

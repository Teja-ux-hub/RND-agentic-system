"""Stock metrics helper using yfinance."""

from __future__ import annotations

import logging
import os
from typing import Any

import yaml
import yfinance as yf

LOGGER = logging.getLogger(__name__)


def _resolve_ticker(name_or_ticker: str) -> str | None:
    """Validate a likely ticker or return the raw string if it's already a symbol."""
    if not name_or_ticker:
        return None
    raw = name_or_ticker.strip().upper()
    # If it looks like a ticker (e.g. MSFT, ZOMATO.NS), just return it
    # Tickers are typically 1-10 chars, no spaces, maybe a dot
    if " " not in raw and 1 <= len(raw) <= 12:
        return raw
    return None


def _format_market_cap(value: Any) -> float | str:
    return float(value) if isinstance(value, (int, float)) else "N/A"


def get_metrics(name_or_ticker: str) -> dict:
    """Fetch current price, recent change, and market cap with safe fallbacks."""
    ticker_symbol = _resolve_ticker(name_or_ticker)
    if not ticker_symbol:
        return {
            "Company": name_or_ticker,
            "Ticker": None,
            "CurrentPrice": "N/A",
            "WeekChangePct": "N/A",
            "MarketCap": "N/A",
        }

    try:
        ticker = yf.Ticker(ticker_symbol)
        history = ticker.history(period="7d")
        if history.empty or len(history) < 2:
            history = ticker.history(period="1mo")

        current_price = "N/A"
        week_change = "N/A"
        if not history.empty and len(history) >= 2:
            start_price = float(history["Close"].iloc[0])
            end_price = float(history["Close"].iloc[-1])
            current_price = round(end_price, 2)
            week_change = round(((end_price - start_price) / start_price) * 100, 2)

        info = getattr(ticker, "fast_info", {}) or {}
        market_cap = info.get("market_cap")
        if market_cap is None:
            full_info = getattr(ticker, "info", {}) or {}
            market_cap = full_info.get("marketCap")

        return {
            "Company": name_or_ticker,
            "Ticker": ticker_symbol,
            "is_public": True,
            "CurrentPrice": current_price,
            "WeekChangePct": week_change,
            "MarketCap": _format_market_cap(market_cap),
            "metrics_status": "ok",
            "notes": "",
        }
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("Stock lookup failed for %s (%s): %s", name_or_ticker, ticker_symbol, exc)
        return {
            "Company": name_or_ticker,
            "Ticker": ticker_symbol,
            "is_public": True,
            "CurrentPrice": "N/A",
            "WeekChangePct": "N/A",
            "MarketCap": "N/A",
            "metrics_status": "unavailable_lookup_failed",
            "notes": str(exc),
        }

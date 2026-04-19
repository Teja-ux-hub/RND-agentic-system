"""Collect market metrics for each company."""

from __future__ import annotations

import logging

from graph import AgentState
from tools.stocks import get_metrics

LOGGER = logging.getLogger(__name__)


def run(state: AgentState) -> AgentState:
    """Collect premium financial metrics with market intelligence."""
    print(f"\n{'='*70}")
    print(f"📊 [AGENT] MetricsAgent - Financial Intelligence Gathering")
    print(f"{'='*70}")
    print(f"Analyzing: {state['company_name']} + {len(state.get('competitors', []))} competitors\n")
    
    # Build list of (name, ticker) tuples
    companies = [(state["company_name"], state.get("ticker"))]
    for comp in state.get("competitors", []):
        ticker = state.get("competitor_tickers", {}).get(comp)
        companies.append((comp, ticker))
        
    metrics: list[dict] = []

    for company, ticker in companies:
        if ticker:
            print(f"  Fetching LIVE market data: {company} ({ticker})...")
            result = get_metrics(ticker)
            result["Company"] = company
            result["is_public"] = True
            result["metrics_status"] = "ok"
            result["notes"] = ""
        else:
            print(f"  ⏭️  Skipping {company} (Private company - no public market data)")
            result = {
                "Company": company,
                "Ticker": None,
                "is_public": False,
                "CurrentPrice": "N/A",
                "WeekChangePct": "N/A",
                "MarketCap": "N/A",
                "metrics_status": "unavailable_private_company",
                "notes": "No public market data available.",
            }

        metrics.append(result)

        if result.get("Ticker"):
            price = result.get("CurrentPrice", "N/A")
            change = result.get("WeekChangePct", "N/A")
            market_cap = result.get("MarketCap", "N/A")
            print(f"     💰 Price: ${price} | 7D Change: {change}% | Market Cap: {market_cap}\n")

    updated_state = dict(state)
    updated_state["metrics"] = metrics
    return updated_state

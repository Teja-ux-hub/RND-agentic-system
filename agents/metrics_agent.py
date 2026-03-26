"""Collect market metrics for each company."""

from __future__ import annotations

import logging

from graph import AgentState
from tools.stocks import get_metrics

LOGGER = logging.getLogger(__name__)


def run(state: AgentState) -> AgentState:
    print(f"\n--- [AGENT] MetricsAgent collecting financial data for: {state['company_name']} & its rivals ---")
    
    # Build list of (name, ticker) tuples
    companies = [(state["company_name"], state.get("ticker"))]
    for comp in state.get("competitors", []):
        ticker = state.get("competitor_tickers", {}).get(comp)
        companies.append((comp, ticker))
        
    metrics: list[dict] = []

    for company, ticker in companies:
        if ticker:
            print(f"Fetching real-time market metrics for: {company} (Ticker: {ticker})...")
            result = get_metrics(ticker)
            # Ensure the Company name is correct in the result
            result["Company"] = company
        else:
            print(f"Skipping market metrics for {company} (Private/No Ticker).")
            result = {
                "Company": company,
                "Ticker": None,
                "CurrentPrice": "N/A",
                "WeekChangePct": "N/A",
                "MarketCap": "N/A",
            }
        
        metrics.append(result)
        
        # Display short summary of metrics if available
        if result.get("Ticker"):
            price = result.get("CurrentPrice", "N/A")
            change = result.get("WeekChangePct", "N/A")
            market_cap = result.get("MarketCap", "N/A")
            print(f"  Result: Price={price}, 7D%={change}, Cap={market_cap}")

    updated_state = dict(state)
    updated_state["metrics"] = metrics
    return updated_state

"""CLI entrypoint for the Competitive Intelligence Multi-Agent System."""

from __future__ import annotations

import argparse
import json
import logging
import os
from typing import Any

from dotenv import load_dotenv, find_dotenv

from graph import AgentState, get_app


def build_frontend_summary(state: AgentState) -> dict[str, Any]:
    strongest_moves = []
    for company, moves in state.get("product_moves", {}).items():
        if moves:
            strongest_moves.append(
                {
                    "company": company,
                    "initiative": moves[0].get("name", "Recent initiative"),
                    "impact": moves[0].get("impact", ""),
                }
            )

    return {
        "company": state["company_name"],
        "sector": state.get("sector"),
        "competitors": state.get("competitors", []),
        "key_findings": strongest_moves[:5],
        "metrics_count": len(state.get("metrics", [])),
        "pdf_path": state.get("pdf_path", ""),
        "excel_path": state.get("excel_path", ""),
    }


def main() -> None:
    # Find and load .env file automatically
    env_path = find_dotenv()
    if not env_path:
        print("\n[WARNING] .env file not found! Please ensure you have a .env file with your API keys.")
    else:
        print(f"Loaded environment from: {env_path}")
        load_dotenv(env_path)
    
    # Check for critical API keys
    gemini_key = os.getenv("GEMINI_API_KEY")
    tavily_key = os.getenv("TAVILY_API_KEY")
    
    if not gemini_key:
        print("[CRITICAL] GEMINI_API_KEY is missing! The analysis will use limited fallbacks.")
    if not tavily_key:
        print("[CRITICAL] TAVILY_API_KEY is missing! Web searching will be disabled.")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    company_name = input("Enter the company name to analyze: ").strip()
    if not company_name:
        print("Error: Company name is required.")
        return

    sector = input("Enter the sector (optional): ").strip() or None
    competitors_raw = input("Enter any manual competitors (optional, comma or space-separated): ").strip()
    
    # Handle both commas and spaces
    if "," in competitors_raw:
        competitors = [c.strip() for c in competitors_raw.split(",") if c.strip()]
    else:
        competitors = [c.strip() for c in competitors_raw.split() if c.strip()]

    print(
        f"\nStarting competitive intelligence workflow for {company_name}"
        f"{' in ' + sector if sector else ''}"
    )

    initial_state: AgentState = {
        "company_name": company_name,
        "ticker": None,
        "company_description": "",
        "sector": sector,
        "competitors": competitors,
        "competitor_tickers": {},
        "news_data": {},
        "product_moves": {},
        "market_position": {},
        "public_issues": {},
        "user_sentiment": {},
        "metrics": [],
        "strategy_summary": "",
        "pdf_path": "",
        "excel_path": "",
    }

    try:
        app = get_app()
        final_state = app.invoke(initial_state)

        print("\nWorkflow complete.")
        print("PDF Report:", final_state.get("pdf_path", ""))
        print("Excel Data:", final_state.get("excel_path", ""))
        print("\nKey Summary:")
        print(json.dumps(build_frontend_summary(final_state), indent=2))
    except Exception as e:
        print(f"\n[ERROR] Workflow execution failed: {e}")
        logging.error(f"Workflow execution failed: {e}", exc_info=True)


if __name__ == "__main__":
    main()

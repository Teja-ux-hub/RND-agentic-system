"""CLI entrypoint for the Competitive Intelligence Multi-Agent System.

This is a production-grade competitive analysis platform that generates
professional intelligence reports using AI agents.

Usage:
    python main.py --company "Tesla" --sector "Electric Vehicles"
    
For commercial licensing, contact: sales@competitiveintel.ai
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv, find_dotenv

from graph import AgentState, get_app


def build_frontend_summary(state: AgentState) -> dict[str, Any]:
    """Build a professional summary suitable for client presentations."""
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
        "generated_at": datetime.now().isoformat(),
        "report_quality": "premium" if len(strongest_moves) >= 3 else "standard",
    }

def main() -> None:
    """Main entry point with professional error handling and validation."""
    # Find and load .env file automatically
    env_path = find_dotenv()
    if not env_path:
        print("\n[WARNING] .env file not found! Please ensure you have a .env file with your API keys.")
    else:
        print(f"✓ Loaded environment from: {env_path}")
        load_dotenv(env_path)
    
    # Validate critical API keys
    gemini_key = os.getenv("GEMINI_API_KEY")
    tavily_key = os.getenv("TAVILY_API_KEY")
    
    if not gemini_key:
        print("[CRITICAL] GEMINI_API_KEY is missing! The analysis will use limited fallbacks.")
    else:
        print("✓ Gemini API configured")
        
    if not tavily_key:
        print("[CRITICAL] TAVILY_API_KEY is missing! Web searching will be disabled.")
    else:
        print("✓ Tavily API configured")

    # Configure professional logging
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ],
    )

    parser = argparse.ArgumentParser(
        description="Competitive Intelligence CLI - Professional-grade market analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --company "Microsoft" --sector "Technology"
  python main.py --company "Tesla" --competitors "Rivian,Lucid Motors,Ford"
        """
    )
    parser.add_argument("--company", help="Company name to analyze (required)")
    parser.add_argument("--sector", help="Industry sector")
    parser.add_argument("--competitors", help="Manual competitors (comma-separated)")
    parser.add_argument("--output-dir", default="outputs", help="Output directory for reports")
    args = parser.parse_args()

    company_name = args.company or input("Enter the company name to analyze: ").strip()
    if not company_name:
        print("❌ Error: Company name is required.")
        sys.exit(1)

    sector = args.sector or (input("Enter the sector (optional): ").strip() or None)
    competitors_raw = args.competitors or input("Enter any manual competitors (optional, comma-separated): ").strip()
    
    # Handle both commas and spaces
    if "," in competitors_raw:
        competitors = [c.strip() for c in competitors_raw.split(",") if c.strip()]
    else:
        competitors = [c.strip() for c in competitors_raw.split() if c.strip()]

    print("\n" + "="*70)
    print(f"🚀 COMPETITIVE INTELLIGENCE ANALYSIS")
    print("="*70)
    print(f"Target Company: {company_name}")
    print(f"Sector: {sector or 'Auto-detected'}")
    print(f"Known Competitors: {', '.join(competitors) if competitors else 'Auto-detecting...'}")
    print("="*70 + "\n")

    initial_state: AgentState = {
        "company_name": company_name,
        "sector": sector,
        "ticker": None,
        "company_description": "",
        "company_profile": {},
        "competitors": competitors,
        "competitor_tickers": {},
        "strengths": [],
        "weaknesses": [],
        "market_trends": [],
        "product_moves": {},
        "actions": [],
        "battlecard": {"strengths": [], "weaknesses": [], "win_themes": {}},
        "news_data": {},
        "metrics": [],
        "scoring_matrices": {},
        "strategy_summary": "",
        "pdf_path": "",
        "excel_path": "",
        "reasoning_trace": [],
    }

    try:
        print("⏳ Initializing AI agents...\n")
        app = get_app()
        
        print("📊 Running competitive intelligence workflow...\n")
        final_state = app.invoke(initial_state)

        print("\n" + "="*70)
        print("✅ ANALYSIS COMPLETE")
        print("="*70)
        print("📄 PDF Report:", final_state.get("pdf_path", "Not generated"))
        print("📊 Excel Data:", final_state.get("excel_path", "Not generated"))
        print("\n📈 EXECUTIVE SUMMARY:")
        print(json.dumps(build_frontend_summary(final_state), indent=2, default=str))
        print("="*70)
        print("\n💼 For custom enterprise analyses, contact: sales@competitiveintel.ai")
        print("🔒 This report is confidential and intended for authorized use only.\n")
    except Exception as e:
        print(f"\n❌ [ERROR] Workflow execution failed: {e}")
        logging.error(f"Workflow execution failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

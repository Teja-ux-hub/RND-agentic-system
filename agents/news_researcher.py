"""Research recent news and product moves for each company."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from graph import AgentState
from tools.html_fetch import fetch_clean_text
from tools.web_search import search_company_news_and_products
from agents.utils import get_gemini_llm

LOGGER = logging.getLogger(__name__)


def _build_analysis_prompt(company: str, payload: dict[str, Any]) -> str:
    return (
        "You are a Senior R&D Intelligence Agent. Analyze the provided evidence for the company below.\n"
        f"Target Company: {company}\n\n"
        "Your goal is to determine:\n"
        "1. Status: Is the company Ahead, Behind, or Equal in the market/sector compared to rivals?\n"
        "2. Reasons: 1-3 core reasons for this status (pricing, UX, trust, scale, etc.).\n"
        "3. Deepen: 2-3 concrete moves to go deeper into the market (new segments, features, cities).\n"
        "4. Public Issues: Recent major complaints, scandals, outages, or PR crises.\n"
        "5. Sentiment: Latest feature feedback, app reviews, and how they compare to rivals.\n"
        "6. Initiatives: Key recent product or business moves.\n\n"
        "Return strictly JSON with keys: 'status', 'reasons', 'deepen', 'public_issues', 'sentiment', 'initiatives'.\n"
        "'initiatives' should be a list of objects with: name, type, date, description, impact.\n\n"
        f"Evidence:\n{json.dumps(payload, ensure_ascii=True)}"
    )


def _fallback_initiatives(payload: dict[str, Any]) -> list[dict]:
    moves: list[dict] = []
    for item in payload.get("news", [])[:3]:
        moves.append(
            {
                "name": item.get("title", "Recent initiative")[:80],
                "type": "news",
                "date": item.get("published_at", "Approx. recent"),
                "description": item.get("snippet", "Recent company update discovered.")[:160],
                "impact": "Potential market signal based on recent public coverage.",
            }
        )
    for item in payload.get("product_pages", [])[:2]:
        moves.append(
            {
                "name": item.get("title", "Product update")[:80],
                "type": "feature",
                "date": item.get("published_at", "Approx. recent"),
                "description": item.get("snippet", "Product or platform update.")[:160],
                "impact": "May affect product competitiveness or customer perception.",
            }
        )
    return moves


def _call_gemini_for_analysis(company: str, payload: dict[str, Any]) -> dict[str, Any]:
    llm = get_gemini_llm(model_env_var="GEMINI_MODEL", default_model="gemini-2.0-flash", temperature=0.1)
    default_res = {
        "status": "Equal",
        "reasons": ["Limited public data for definitive ranking."],
        "deepen": ["Expand visible product roadmap.", "Increase market transparency."],
        "public_issues": [],
        "sentiment": "Neutral or mixed sentiment based on limited recent reviews.",
        "initiatives": _fallback_initiatives(payload),
    }
    if not llm:
        return default_res

    try:
        from langchain_core.output_parsers import JsonOutputParser

        parser = JsonOutputParser()
        response = llm.invoke(_build_analysis_prompt(company, payload))
        parsed = parser.parse(response.content)
        return {
            "status": parsed.get("status", "Equal"),
            "reasons": parsed.get("reasons", ["Data-driven assessment pending."]),
            "deepen": parsed.get("deepen", ["Identify untapped segments."]),
            "public_issues": parsed.get("public_issues", []),
            "sentiment": parsed.get("sentiment", "Neutral"),
            "initiatives": parsed.get("initiatives", _fallback_initiatives(payload)),
        }
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("NewsResearcher Gemini analysis failed for %s: %s", company, exc)
        return default_res


def run(state: AgentState) -> AgentState:
    print(f"\n--- [AGENT] NewsResearcher researching recent moves for: {state['company_name']} & its rivals ---")
    companies = [state["company_name"], *state.get("competitors", [])]
    news_data: dict[str, list[dict]] = {}
    product_moves: dict[str, list[dict]] = {}
    market_position: dict[str, str] = {}
    public_issues: dict[str, list[str]] = {}
    user_sentiment: dict[str, str] = {}

    for company in companies:
        print(f"Researching: {company}...")
        search_payload = search_company_news_and_products(company)
        enriched_pages: list[dict] = []
        
        # Limit to top product pages for deeper analysis
        pages_to_fetch = search_payload.get("product_pages", [])[:2]
        if pages_to_fetch:
            print(f"  Fetching content from {len(pages_to_fetch)} product pages...")

        for page in pages_to_fetch:
            clean_text = fetch_clean_text(page.get("url", ""))
            enriched_pages.append({**page, "clean_text": clean_text[:4000]})

        model_input = {
            "news": search_payload.get("news", []),
            "product_pages": enriched_pages or search_payload.get("product_pages", []),
            "market_data": search_payload.get("market_data", []),
            "feedback": search_payload.get("feedback", []),
        }

        news_data[company] = search_payload.get("news", [])
        
        print(f"  Analyzing market position and feedback for {company} using Gemini...")
        analysis = _call_gemini_for_analysis(company, model_input)
        
        product_moves[company] = analysis["initiatives"]
        market_position[company] = f"{analysis['status']}: {', '.join(analysis['reasons'])}. To deepen: {', '.join(analysis['deepen'])}."
        public_issues[company] = analysis["public_issues"]
        user_sentiment[company] = analysis["sentiment"]
        
        print(f"  Found {len(analysis['initiatives'])} key initiatives for {company}.")
        if analysis["public_issues"]:
            print(f"  Detected {len(analysis['public_issues'])} public issues/complaints.")

    updated_state = dict(state)
    updated_state["news_data"] = news_data
    updated_state["product_moves"] = product_moves
    updated_state["market_position"] = market_position
    updated_state["public_issues"] = public_issues
    updated_state["user_sentiment"] = user_sentiment
    return updated_state

"""Find and normalize competitor names."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Iterable

import yaml

from graph import AgentState
from tools.web_search import search_competitors
from agents.utils import get_gemini_llm

LOGGER = logging.getLogger(__name__)


def _load_known_competitors(company_name: str, sector: str | None) -> list[str]:
    config_path = os.getenv("COMPANIES_CONFIG_PATH", os.path.join("config", "companies.yaml"))
    if not os.path.exists(config_path):
        LOGGER.debug("Config path %s not found", config_path)
        return []

    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}

        companies = config.get("companies", {})
        direct = companies.get(company_name.lower(), {}).get("competitors", [])
        if direct:
            return direct

        sector_key = (sector or "").lower()
        return config.get("sectors", {}).get(sector_key, {}).get("competitors", [])
    except Exception as exc:
        LOGGER.error("Failed to load competitors from config: %s", exc)
        return []


def _dedupe_competitors(names: Iterable[str], company_name: str) -> list[str]:
    normalized_company = company_name.strip().lower()
    seen: set[str] = set()
    output: list[str] = []
    for name in names:
        clean = name.strip()
        if not clean or clean.lower() == normalized_company:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(clean)
        if len(output) >= 5:
            break
    return output


def _extract_names_heuristically(company_name: str, candidates: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    bad_keywords = {"competitors", "rivals", "market", "top", "best", "versus", " vs "}
    for candidate in candidates:
        if not candidate:
            continue
        # If the candidate looks like a generic search result title, skip it
        lower_cand = candidate.lower()
        if any(kw in lower_cand for kw in bad_keywords) and len(candidate.split()) > 3:
            continue

        name = (
            candidate.replace(" vs ", "|")
            .replace(" and ", "|")
            .replace(",", "|")
            .replace(":", "|")
            .split("|")[0]
            .strip()
        )
        if len(name) >= 2:
            cleaned.append(name)
    return _dedupe_competitors(cleaned, company_name)


def _call_gemini_for_competitors(
    company_name: str,
    sector: str | None,
    raw_results: list[dict],
    manual_competitors: list[str],
) -> dict[str, Any]:
    llm = get_gemini_llm(model_env_var="GEMINI_MODEL", default_model="gemini-2.0-flash", temperature=0.1)
    if not llm:
        heuristic = [item.get("title", "") for item in raw_results]
        return {
            "competitors": _extract_names_heuristically(company_name, heuristic + manual_competitors),
            "ticker": None,
            "description": f"An analysis of {company_name} in the {sector or 'unknown'} sector.",
        }

    try:
        from langchain_core.output_parsers import JsonOutputParser
        from langchain_core.prompts import ChatPromptTemplate

        parser = JsonOutputParser()
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Identify the top 3-5 competitors, find the stock tickers for BOTH the primary company and its competitors, "
                    "and provide a 1-sentence description. If a company is private, return null for the ticker. "
                    "For Indian companies, ensure tickers include '.NS' (e.g., 'ZOMATO.NS'). "
                    "Return strictly JSON format.",
                ),
                (
                    "human",
                    "Research {company_name} in the {sector} industry.\n"
                    "Context: {context}\n"
                    "User suggestions: {manual_competitors}\n"
                    "Format: {{\n"
                    "  'primary_ticker': 'TICKER_OR_NULL',\n"
                    "  'competitors': [\n"
                    "    {{'name': 'Name1', 'ticker': 'TICK1_OR_NULL'}},\n"
                    "    {{'name': 'Name2', 'ticker': 'TICK2_OR_NULL'}}\n"
                    "  ],\n"
                    "  'description': 'One sentence about the primary company.'\n"
                    "}}"
                ),
            ]
        )
        chain = prompt | llm | parser
        response = chain.invoke({
            "company_name": company_name,
            "sector": sector or "relevant",
            "context": json.dumps(raw_results, ensure_ascii=True),
            "manual_competitors": manual_competitors
        })
        
        # Process and deduplicate competitors
        comp_data = response.get("competitors", [])
        deduped_names = _dedupe_competitors([c["name"] for c in comp_data], company_name)
        
        # Build competitor ticker map
        comp_tickers = {c["name"]: c.get("ticker") for c in comp_data if c["name"] in deduped_names}
        
        return {
            "competitors": deduped_names,
            "competitor_tickers": comp_tickers,
            "ticker": response.get("primary_ticker"),
            "description": response.get("description", ""),
        }
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("CompetitorFinder fallback due to Gemini error: %s", exc)
        heuristic = [item.get("title", "") for item in raw_results]
        names = _extract_names_heuristically(company_name, heuristic + manual_competitors)
        return {
            "competitors": names,
            "competitor_tickers": {name: None for name in names},
            "ticker": None,
            "description": f"An analysis of {company_name} in the {sector or 'unknown'} sector.",
        }


def run(state: AgentState) -> AgentState:
    print(f"\n--- [AGENT] CompetitorFinder identifying rivals for: {state['company_name']} ---")
    
    # Search the web in real-time
    print(f"Searching for real-time market data on {state['company_name']}...")
    raw_search = search_competitors(state["company_name"], state.get("sector"))
    
    # Let Gemini analyze and extract everything
    print("Asking Gemini to extract competitors and stock tickers from real-time search results...")
    result = _call_gemini_for_competitors(
        state["company_name"], state.get("sector"), raw_search, state.get("competitors", [])
    )

    print(f"Primary Ticker: {result.get('ticker') or 'N/A'}")
    print(f"Rivals Identified: {', '.join(result['competitors'])}")
    
    # Log tickers for rivals
    ticker_list = [f"{n}({t or 'Private'})" for n, t in result["competitor_tickers"].items()]
    print(f"Rival Tickers: {', '.join(ticker_list)}")
    print(f"Overview: {result['description']}")

    updated_state = dict(state)
    updated_state["competitors"] = result["competitors"]
    updated_state["ticker"] = result["ticker"]
    updated_state["competitor_tickers"] = result["competitor_tickers"]
    updated_state["company_description"] = result["description"]
    return updated_state

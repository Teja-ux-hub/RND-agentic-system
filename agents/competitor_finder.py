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
    llm = get_gemini_llm(model_env_var="GEMINI_MODEL", default_model="gemini-2.5-flash", temperature=0.1)
    if not llm:
        heuristic = [item.get("title", "") for item in raw_results]
        names = _extract_names_heuristically(company_name, heuristic + manual_competitors)
        return {
            "competitors": names,
            "competitor_meta": [{"name": n, "ticker": None, "competitor_type": "direct", "priority": "medium", "reason": ""} for n in names],
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
                    "You are identifying the most relevant competitors for competitive intelligence tracking.\n"
                    "Your job is to identify 3-5 high-relevance competitors for the target company and return strictly valid JSON.\n\n"
                    "Rules:\n"
                    "1. Prefer direct competitors over generic market peers.\n"
                    "2. Include substitutes or adjacent competitors only if they materially compete on product, pricing, audience, or positioning.\n"
                    "3. Find stock tickers for both the primary company and competitors when available.\n"
                    "4. If a company is private, return null for ticker.\n"
                    "5. For Indian listed companies, use the '.NS' suffix when appropriate.\n"
                    "6. For each competitor, include a short reason explaining why it is relevant.\n"
                    "7. Add a competitor_type field using one of: direct, adjacent, substitute.\n"
                    "8. Add a priority field using one of: high, medium, low.\n"
                    "9. Keep descriptions concise and factual.\n"
                    "10. Return strictly JSON only.\n\n"
                    "You are part of a competitive intelligence workflow. "
                    "Prioritize specific, verifiable, recent business evidence. "
                    "Avoid generic strategy language. Prefer concrete facts over vague summaries. "
                    "Do not invent metrics, product names, dates, pricing, or partnerships.",
                ),
                (
                    "human",
                    "Research {company_name} in the {sector} industry.\n"
                    "Context:\n{context}\n"
                    "User suggestions:\n{manual_competitors}\n\n"
                    "Return JSON in exactly this shape:\n"
                    "{{\n"
                    "  \"primary_company\": \"{company_name}\",\n"
                    "  \"primary_ticker\": \"TICKER_OR_NULL\",\n"
                    "  \"description\": \"One sentence about the primary company.\",\n"
                    "  \"competitors\": [\n"
                    "    {{\"name\": \"Name1\", \"ticker\": \"TICK1_OR_NULL\", \"competitor_type\": \"direct\", \"priority\": \"high\", \"reason\": \"Why this competitor is strategically relevant\"}}\n"
                    "  ]\n"
                    "}}"
                ),
            ]
        )
        chain = prompt | llm | parser
        invoke_payload = {
            "company_name": company_name,
            "sector": sector or "relevant",
            "context": json.dumps(raw_results, ensure_ascii=True),
            "manual_competitors": manual_competitors
        }
        LOGGER.debug("LLM Input (CompetitorFinder):\n%s", json.dumps(invoke_payload, indent=2))
        response = chain.invoke(invoke_payload)
        LOGGER.debug("LLM Output (CompetitorFinder):\n%s", json.dumps(response, indent=2))
        
        # Process and deduplicate competitors
        comp_data = response.get("competitors", [])
        deduped_names = _dedupe_competitors([c["name"] for c in comp_data], company_name)

        # Build competitor ticker map
        comp_tickers = {c["name"]: c.get("ticker") for c in comp_data if c["name"] in deduped_names}

        # Build enriched competitor metadata
        comp_meta = [
            {
                "name": c["name"],
                "ticker": c.get("ticker"),
                "competitor_type": c.get("competitor_type", "direct"),
                "priority": c.get("priority", "medium"),
                "reason": c.get("reason", ""),
            }
            for c in comp_data if c["name"] in deduped_names
        ]

        return {
            "competitors": deduped_names,
            "competitor_tickers": comp_tickers,
            "competitor_meta": comp_meta,
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
            "competitor_meta": [{"name": n, "ticker": None, "competitor_type": "direct", "priority": "medium", "reason": ""} for n in names],
            "ticker": None,
            "description": f"An analysis of {company_name} in the {sector or 'unknown'} sector.",
        }


def run(state: AgentState) -> AgentState:
    """Run competitor identification with premium data enrichment."""
    print(f"\n{'='*70}")
    print(f"🎯 [AGENT] CompetitorFinder - Identifying market rivals")
    print(f"{'='*70}")
    print(f"Target: {state['company_name']}")
    
    # Search the web in real-time
    print(f"\n📡 Searching global databases for real-time market intelligence on {state['company_name']}...")
    raw_search = search_competitors(state["company_name"], state.get("sector"))
    
    # Let Gemini analyze and extract everything
    print("🤖 AI-powered entity extraction: Analyzing competitors and stock tickers from live data...")
    result = _call_gemini_for_competitors(
        state["company_name"], state.get("sector"), raw_search, state.get("competitors", [])
    )

    print(f"\n✅ COMPETITOR ANALYSIS COMPLETE")
    print(f"{'='*70}")
    print(f"📌 Primary Company Ticker: {result.get('ticker') or 'Private/N/A'}")
    print(f"🏢 Rivals Identified: {len(result['competitors'])} companies")
    for idx, rival in enumerate(result['competitors'], 1):
        ticker = result["competitor_tickers"].get(rival)
        if ticker:
            print(f"   {idx}. {rival} (Public: {ticker})")
        else:
            print(f"   {idx}. {rival} (Private)")
    print(f"📋 Market Overview: {result['description'][:200]}...")
    print(f"{'='*70}\n")

    updated_state = dict(state)
    updated_state["competitors"] = result["competitors"]
    updated_state["ticker"] = result["ticker"]
    updated_state["competitor_tickers"] = result["competitor_tickers"]
    updated_state["competitor_meta"] = result.get("competitor_meta", [])
    updated_state["company_description"] = result["description"]
    return updated_state

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


from pydantic import BaseModel, Field


class Evidence(BaseModel):
    source: str = Field(description="The URL of the evidence")
    snippet: str = Field(description="A relevant snippet of text from the source")


class NewsResearcherOutput(BaseModel):
    company_profile: dict[str, str] = Field(description="Segment, target customer, pricing tier, geo focus")
    evidence: list[Evidence] = Field(description="A list of evidence snippets from various sources")


def _call_gemini_for_evidence(company: str, payload: dict[str, Any]) -> dict[str, Any]:
    llm = get_gemini_llm(model_env_var="GEMINI_MODEL", default_model="gemini-2.0-flash", temperature=0.1)
    
    if not llm:
        return {
            "company_profile": {"error": "LLM not available"},
            "evidence": [],
        }

    try:
        from langchain_core.prompts import ChatPromptTemplate

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a world-class evidence gathering agent. Your goal is to find raw, unbiased evidence to support a competitive analysis."),
            ("human", "Gather evidence for {company_name} based on the following data:\n{evidence}")
        ])
        
        print(f"  > Calling Gemini for evidence synthesis ({company})...")
        structured_llm = llm.with_structured_output(NewsResearcherOutput)
        chain = prompt | structured_llm
        
        response = chain.invoke({"company_name": company, "evidence": json.dumps(payload, ensure_ascii=True)})
        
        return {
            "company_profile": response.company_profile,
            "evidence": [e.model_dump() for e in response.evidence],
        }
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("NewsResearcher evidence gathering failed for %s: %s", company, exc)
        return {
            "company_profile": {"error": str(exc)},
            "evidence": [],
        }


def run(state: AgentState) -> AgentState:
    """Gather premium intelligence from news, products, and market signals."""
    print(f"\n{'='*70}")
    print(f"📰 [AGENT] NewsResearcher - Market Intelligence Collection")
    print(f"{'='*70}")
    companies = [state["company_name"], *state.get("competitors", [])]
    all_evidence: dict[str, list[dict]] = {}

    for company in companies:
        print(f"\n🔍 Deep-dive research: {company}...")
        search_payload = search_company_news_and_products(company)
        enriched_pages: list[dict] = []
        
        pages_to_fetch = search_payload.get("product_pages", [])[:2]
        if pages_to_fetch:
            print(f"  📄 Analyzing {len(pages_to_fetch)} product/feature pages...")

        for page in pages_to_fetch:
            clean_text = fetch_clean_text(page.get("url", ""))
            enriched_pages.append({**page, "clean_text": clean_text[:6000]})

        model_input = {
            "news": [
                {**item, "snippet": item.get("snippet", "")[:1000]}
                for item in search_payload.get("news", [])[:3]
            ],
            "product_pages": [
                {**item, "clean_text": item.get("clean_text", "")[:3000]}
                for item in enriched_pages or search_payload.get("product_pages", [])[:2]
            ],
            "market_data": [
                {**item, "snippet": item.get("snippet", "")[:1000]}
                for item in search_payload.get("market_data", [])[:2]
            ],
            "feedback": [
                {**item, "snippet": item.get("snippet", "")[:1000]}
                for item in search_payload.get("feedback", [])[:3]
            ],
        }

        LOGGER.debug("LLM Input (NewsResearcher - %s):\n%s", company, json.dumps(model_input, indent=2))
        evidence_result = _call_gemini_for_evidence(company, model_input)
        LOGGER.debug("LLM Output (NewsResearcher - %s):\n%s", company, json.dumps(evidence_result, indent=2))
        print(f"  ✅ Evidence gathered: {len(evidence_result['evidence'])} data points collected")
        all_evidence[company] = evidence_result["evidence"]

    updated_state = dict(state)
    updated_state["news_data"] = all_evidence
    return updated_state

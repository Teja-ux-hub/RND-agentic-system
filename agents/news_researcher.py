"""Research recent news and product moves for each company."""

from __future__ import annotations

import json
import logging
from typing import Any

from graph import AgentState, NewsItem
from tools.web_search import search_company_news_and_products
from agents.utils import get_gemini_llm

LOGGER = logging.getLogger(__name__)


def run(state: AgentState) -> AgentState:
    """Gather premium intelligence from news, products, and market signals."""
    print(f"\n{'='*70}")
    print(f"📰 [AGENT] NewsResearcher - Market Intelligence Collection")
    print(f"{'='*70}")
    
    # Include target company and all competitors
    companies = [state["company_name"]] + state.get("competitors", [])
    all_news: dict[str, list[NewsItem]] = {}

    for company in companies:
        print(f"\n🔍 Researching: {company}...")
        
        # Limit to top 5 high-quality results per competitor
        search_results = search_company_news_and_products(company)
        
        # Extract and format news items
        news_items = []
        raw_news = search_results.get("news", [])[:5]  # Strict limit to top 5
        
        for item in raw_news:
            news_item: NewsItem = {
                "title": item.get("title", "No Title"),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", "")[:1000],
                "source": item.get("source", "Unknown"),
                "published_at": item.get("published_at", "")
            }
            news_items.append(news_item)
            
        print(f"  ✅ Collected {len(news_items)} news items for {company}")
        all_news[company] = news_items

    updated_state = dict(state)
    updated_state["news_data"] = all_news
    
    # Reasoning trace for auditability
    if "reasoning_trace" not in updated_state:
        updated_state["reasoning_trace"] = []
    updated_state["reasoning_trace"].append(f"NewsResearcher: Collected news for {len(companies)} companies.")
    
    return updated_state

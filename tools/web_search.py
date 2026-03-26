"""Tavily-based web search helpers with graceful fallbacks."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta

LOGGER = logging.getLogger(__name__)


def _fallback_search_results(company: str, sector: str | None = None) -> list[dict]:
    sector_label = sector or "its sector"
    return [
        {
            "title": f"{company} competitors in {sector_label}",
            "url": "",
            "content": f"{company} competes with several established brands in {sector_label}.",
            "score": 0.0,
        }
    ]


def search_competitors(company: str, sector: str | None = None) -> list[dict]:
    api_key = os.getenv("TAVILY_API_KEY")
    query_template = os.getenv("COMPETITOR_SEARCH_QUERY", "Top competitors of {company} {sector_hint} company rivals market competitors")
    sector_hint = f"in {sector}" if sector else ""
    query = query_template.format(company=company, sector_hint=sector_hint)
    if not api_key:
        LOGGER.warning("TAVILY_API_KEY missing; using fallback competitor search results")
        return _fallback_search_results(company, sector)

    try:
        from tavily import TavilyClient

        max_results = int(os.getenv("TAVILY_MAX_RESULTS", "5"))
        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            topic="news",
            max_results=max_results,
            include_raw_content=False,
        )
        return response.get("results", [])
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("Tavily competitor search failed: %s", exc)
        return _fallback_search_results(company, sector)


def search_company_news_and_products(company: str) -> dict[str, list[dict]]:
    api_key = os.getenv("TAVILY_API_KEY")
    news_days = int(os.getenv("TAVILY_NEWS_DAYS", "30"))
    cutoff = (datetime.utcnow() - timedelta(days=news_days)).strftime("%Y-%m-%d")
    fallback = {
        "news": [
            {
                "title": f"{company} recent update",
                "url": "",
                "snippet": f"Fallback public update for {company}; configure Tavily for richer news.",
                "source": "fallback",
                "published_at": cutoff,
            }
        ],
        "product_pages": [
            {
                "title": f"{company} product updates",
                "url": "",
                "snippet": f"Fallback product page placeholder for {company}.",
                "source": "fallback",
                "published_at": cutoff,
            }
        ],
    }

    if not api_key:
        LOGGER.warning("TAVILY_API_KEY missing; using fallback news/product results for %s", company)
        return fallback

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        max_results = int(os.getenv("TAVILY_MAX_RESULTS", "5"))

        news_query_template = os.getenv(
            "NEWS_SEARCH_QUERY",
            "{company} recent news last month product launch partnership pricing update",
        )
        product_query_template = os.getenv(
            "PRODUCT_SEARCH_QUERY",
            "{company} blog changelog what's new product updates features",
        )
        market_query_template = os.getenv(
            "MARKET_SEARCH_QUERY",
            "{company} market share growth vs competitors ranking",
        )
        feedback_query_template = os.getenv(
            "FEEDBACK_SEARCH_QUERY",
            "{company} user reviews complaints latest update app store reddit",
        )

        news_response = client.search(
            query=news_query_template.format(company=company),
            topic="news",
            days=news_days,
            max_results=max_results + 1,
        )
        product_response = client.search(
            query=product_query_template.format(company=company),
            topic="general",
            max_results=max_results,
        )
        market_response = client.search(
            query=market_query_template.format(company=company),
            topic="general",
            max_results=max_results,
        )
        feedback_response = client.search(
            query=feedback_query_template.format(company=company),
            topic="general",
            max_results=max_results,
        )

        def _format_results(results):
            return [
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", ""),
                    "source": item.get("url", "").split("/")[2] if item.get("url") else "unknown",
                    "published_at": item.get("published_date", cutoff),
                }
                for item in results
            ]

        return {
            "news": _format_results(news_response.get("results", [])) or fallback["news"],
            "product_pages": _format_results(product_response.get("results", [])) or fallback["product_pages"],
            "market_data": _format_results(market_response.get("results", [])),
            "feedback": _format_results(feedback_response.get("results", [])),
        }
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("Tavily search failed for %s: %s", company, exc)
        return fallback

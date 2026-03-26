"""LangGraph workflow definition and shared state model."""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph


class NewsItem(TypedDict):
    title: str
    url: str
    snippet: str
    source: str
    published_at: str


class ProductMove(TypedDict):
    name: str
    type: str
    date: str
    description: str
    impact: str


class MetricRow(TypedDict):
    Company: str
    Ticker: str | None
    CurrentPrice: float | str
    WeekChangePct: float | str
    MarketCap: float | str


class AgentState(TypedDict):
    company_name: str
    ticker: str | None
    company_description: str
    sector: str | None
    competitors: list[str]
    competitor_tickers: dict[str, str | None]
    news_data: dict[str, list[NewsItem]]
    product_moves: dict[str, list[ProductMove]]
    market_position: dict[str, str]  # Ahead/Behind/Equal and why
    public_issues: dict[str, list[str]]  # Complaints, scandals, outages
    user_sentiment: dict[str, str]  # Latest feature feedback
    metrics: list[MetricRow]
    strategy_summary: str
    pdf_path: str
    excel_path: str


def get_app():
    """Build and compile the LangGraph application."""
    from agents import competitor_finder, metrics_agent, news_researcher, strategy_agent

    graph = StateGraph(AgentState)
    graph.add_node("find_competitors", competitor_finder.run)
    graph.add_node("research_news", news_researcher.run)
    graph.add_node("get_metrics", metrics_agent.run)
    graph.add_node("write_strategy", strategy_agent.run)
    graph.set_entry_point("find_competitors")
    graph.add_edge("find_competitors", "research_news")
    graph.add_edge("research_news", "get_metrics")
    graph.add_edge("get_metrics", "write_strategy")
    graph.add_edge("write_strategy", END)
    return graph.compile()

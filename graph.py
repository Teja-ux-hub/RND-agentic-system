"""LangGraph workflow definition and shared state model."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field

from langgraph.graph import END, StateGraph


class NewsItem(TypedDict):
    title: str
    url: str
    snippet: str
    source: str
    published_at: str


class CompetitorMeta(TypedDict):
    name: str
    ticker: str | None
    competitor_type: str   # direct | adjacent | substitute
    priority: str          # high | medium | low
    reason: str


class CompetitorEvent(BaseModel):
    competitor: str = Field(description="The competitor involved in the event")
    event_type: str = Field(description="Type of event: launch, pricing_change, packaging_change, promotion, partnership, expansion, acquisition, positioning_change, review_signal, customer_experience_signal, hiring_signal, market_claim")
    priority: str = Field(default="medium", description="high, medium, or low")
    description: str = Field(description="Brief description of the event")
    evidence_type: str = Field(default="news", description="news, blog, pricing_page, review, website_copy, market_report")
    source_url: str = Field(description="URL of the news source")
    event_date: str | None = Field(default=None, description="Date of the event if available")
    old_value: str | None = Field(default=None, description="Previous value for pricing/packaging changes")
    new_value: str | None = Field(default=None, description="New value for pricing/packaging changes")
    sentiment_signal: str | None = Field(default=None, description="positive, negative, or mixed for review signals")
    positioning_angle: str | None = Field(default=None, description="Claimed differentiator for positioning changes")


class EventImpact(BaseModel):
    event_description: str = Field(description="The event being analyzed")
    competitor: str = Field(description="The competitor involved")
    user_impact: str = Field(description="Estimated impact on users/customers")
    revenue_impact: str = Field(description="Estimated impact on revenue")
    market_position_impact: str = Field(default="", description="Impact on market position")
    pricing_pressure: str = Field(default="", description="Impact on pricing pressure")
    marketing_message_risk: str = Field(default="", description="Risk to current marketing messaging")
    urgency: str = Field(default="medium", description="high, medium, or low")
    alert_priority: str = Field(default="weekly_digest", description="instant, daily_digest, weekly_digest, or none")
    confidence_score: float = Field(description="Confidence in the estimation (0.0-1.0)")
    rationale: str = Field(default="", description="Brief reasoning behind the estimates")


class StrategicDecision(BaseModel):
    category: str = Field(description="product, pricing, sales_enablement, marketing_content, brand_positioning, or monitoring_alert")
    action: str = Field(description="Specific recommended action")
    reason: str = Field(description="Strategic reasoning linked to a specific event")
    linked_competitor: str = Field(default="", description="The competitor this action responds to")
    linked_event: str = Field(default="", description="The specific event driving this action")
    evidence: str = Field(description="Supporting evidence/data point")
    expected_outcome: str = Field(description="Expected business outcome")
    urgency: str = Field(default="medium", description="high, medium, or low")
    confidence: float = Field(description="Confidence in the recommendation (0.0-1.0)")


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


class ScoringMatrix(BaseModel):
    price_competitiveness: int = Field(description="1-10 score (10 is best)")
    feature_parity: int = Field(description="1-10 score (10 is best)")
    market_momentum: int = Field(description="1-10 score (10 is best)")
    brand_strength: int = Field(description="1-10 score (10 is best)")
    overall_score: int = Field(description="1-10 score (10 is best)")


class Strength(BaseModel):
    description: str = Field(description="Detailed description of the strength")
    impact: str = Field(description="Impact on win-rate, churn, or market position")
    evidence_links: list[str] = Field(description="URLs to evidence backing this claim")
    related_competitor: str | None = Field(default=None, description="The competitor this strength provides an advantage against")
    related_event: str | None = Field(default=None, description="The specific market event validating this strength")


class Weakness(BaseModel):
    description: str = Field(description="Detailed description of the weakness")
    impact: str = Field(description="Impact on win-rate, churn, or market position")
    evidence_links: list[str] = Field(description="URLs to evidence backing this claim")
    related_competitor: str | None = Field(default=None, description="The competitor exploiting this weakness")
    related_event: str | None = Field(default=None, description="The specific market event highlighting this weakness")


class Recommendation(BaseModel):
    timeframe: str = Field(description="Now, 6 months, or 12-24 months")
    action_title: str = Field(description="The specific action to take")
    why_now: str = Field(description="The risk or opportunity driving this action")
    expected_metric: str = Field(description="The metric this action is expected to affect (e.g., churn, MRR, win-rate)")


class Battlecard(BaseModel):
    strengths: list[str] = Field(description="Top 3 strengths to use in sales calls")
    weaknesses: list[str] = Field(description="Top 3 weaknesses to be aware of")
    win_themes: dict[str, str] = Field(description="How to win against each main competitor")


class AgentState(TypedDict):
    company_name: str
    ticker: str | None
    company_description: str
    company_profile: dict[str, str]
    sector: str | None
    competitors: list[str]
    competitor_meta: list[CompetitorMeta]        # enriched competitor metadata
    competitor_tickers: dict[str, str | None]
    strengths: list[Strength]
    weaknesses: list[Weakness]
    market_trends: list[str]
    product_moves: dict[str, list[ProductMove]]
    actions: list[Recommendation]
    battlecard: Battlecard
    news_data: dict[str, list[NewsItem]]
    extracted_events: list[CompetitorEvent]
    impact_estimates: list[EventImpact]
    strategic_decisions: list[StrategicDecision]
    metrics: list[MetricRow]
    scoring_matrices: dict[str, ScoringMatrix]
    synthesis_output: dict                       # full structured synthesis sections
    alert_summary: dict                          # grouped by instant/daily/weekly
    strategy_summary: str
    pdf_path: str
    excel_path: str
    reasoning_trace: list[str]


def get_app():
    """Build and compile the LangGraph application."""
    from agents import (
        competitor_finder, 
        metrics_agent, 
        news_researcher, 
        evidence_extractor,
        impact_estimator,
        synthesis_agent, 
        decision_agent,
        strategy_agent
    )

    graph = StateGraph(AgentState)
    graph.add_node("find_competitors", competitor_finder.run)
    graph.add_node("research_news", news_researcher.run)
    graph.add_node("extract_evidence", evidence_extractor.run)
    graph.add_node("get_metrics", metrics_agent.run)
    graph.add_node("estimate_impact", impact_estimator.run)
    graph.add_node("synthesize_insights", synthesis_agent.run)
    graph.add_node("generate_decisions", decision_agent.run)
    graph.add_node("write_strategy", strategy_agent.run)

    graph.set_entry_point("find_competitors")
    graph.add_edge("find_competitors", "research_news")
    graph.add_edge("research_news", "extract_evidence")
    graph.add_edge("extract_evidence", "get_metrics")
    graph.add_edge("get_metrics", "estimate_impact")
    graph.add_edge("estimate_impact", "synthesize_insights")
    graph.add_edge("synthesize_insights", "generate_decisions")
    graph.add_edge("generate_decisions", "write_strategy")
    graph.add_edge("write_strategy", END)
    return graph.compile()

"""Estimate business impact of extracted market events."""

from __future__ import annotations

import json
import logging
from typing import Any, List

from graph import AgentState, EventImpact, CompetitorEvent
from agents.utils import get_gemini_llm
from pydantic import BaseModel, Field

LOGGER = logging.getLogger(__name__)

class ImpactEstimatorOutput(BaseModel):
    impact_estimates: List[EventImpact] = Field(description="A list of estimated event impacts")

def run(state: AgentState) -> AgentState:
    """Estimate impact on users, revenue, and assign confidence scores."""
    print(f"\n{'='*70}")
    print(f"📊 [AGENT] ImpactEstimatorAgent - Strategic Impact Analysis")
    print(f"{'='*70}")
    
    llm = get_gemini_llm(model_env_var="GEMINI_MODEL", default_model="gemini-2.5-flash", temperature=0.1)
    if not llm:
        print("  ⚠️ LLM not available. Skipping impact estimation.")
        return state

    extracted_events = state.get("extracted_events", [])
    if not extracted_events:
        print("  ⚠️ No events extracted. Skipping impact analysis.")
        return state
        
    all_impact_estimates: List[EventImpact] = []
    
    print(f"\n  Analyzing {len(extracted_events)} strategic events...")
    
    # Prepare context for Gemini
    context = "\n".join([
        f"Competitor: {event.competitor}\nEvent Type: {event.event_type}\nDescription: {event.description}\n---"
        for event in extracted_events
    ])
    
    prompt = f"""You are a business strategist estimating the likely impact of competitive market events.
You are part of a competitive intelligence workflow. Prioritize specific, verifiable, recent business evidence.
Avoid generic strategy language. Do not invent hard numbers unless explicitly supported by the event.
If evidence is weak, lower confidence. Always favor outputs useful for weekly reporting and alerts.

Analyze each event and estimate the likely impact on:
1. users (churn, user growth, customer satisfaction)
2. revenue (MRR growth, market share capture, pricing power)
3. market_position (brand perception, category leadership)
4. pricing_pressure (does this force a pricing response?)
5. marketing_message_risk (does this undermine current messaging?)
6. alert_priority (instant, daily_digest, weekly_digest, or none)

Rules:
- Base reasoning only on the event provided.
- Do not invent hard numbers unless explicitly supported.
- If evidence is weak, lower confidence.
- Alert priority must be one of: instant, daily_digest, weekly_digest, none.
- Urgency must be one of: high, medium, low.
- Keep outputs concise and operational.

Trigger instant alert when: competitor pricing changes, major launch or packaging change, major partnership or acquisition, major negative review surge, major homepage positioning shift.
Trigger daily_digest when: multiple medium-importance events, review pattern shifts, several product updates.
Trigger weekly_digest when: low-signal items, general market news.

Market Events:
{context}

For each event return an EventImpact object with:
- event_description
- competitor
- user_impact
- revenue_impact
- market_position_impact
- pricing_pressure
- marketing_message_risk
- urgency
- alert_priority
- confidence_score
- rationale
"""
    
    try:
        structured_llm = llm.with_structured_output(ImpactEstimatorOutput)
        response = structured_llm.invoke(prompt)
        
        all_impact_estimates = response.impact_estimates
        print(f"  ✅ Impact estimations completed for {len(all_impact_estimates)} events.")
        
    except Exception as exc:
        LOGGER.error(f"ImpactEstimatorAgent failed: {exc}")
        return state

    updated_state = dict(state)
    updated_state["impact_estimates"] = all_impact_estimates

    # Build alert summary grouped by priority
    alert_summary: dict[str, list[dict]] = {"instant": [], "daily_digest": [], "weekly_digest": []}
    for est in all_impact_estimates:
        priority = getattr(est, "alert_priority", "weekly_digest")
        if priority in alert_summary:
            alert_summary[priority].append({
                "competitor": est.competitor,
                "event": est.event_description,
                "urgency": getattr(est, "urgency", "medium"),
                "rationale": getattr(est, "rationale", ""),
            })
    updated_state["alert_summary"] = alert_summary

    if "reasoning_trace" not in updated_state:
        updated_state["reasoning_trace"] = []
    updated_state["reasoning_trace"].append(f"ImpactEstimator: Analyzed impact for {len(all_impact_estimates)} events. Instant alerts: {len(alert_summary['instant'])}.")
    
    return updated_state

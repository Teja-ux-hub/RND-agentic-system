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
    
    prompt = f"""
    You are a business strategist. Analyze the strategic impact of the following market events on:
    1. Users (e.g., churn, user growth, customer satisfaction)
    2. Revenue (e.g., potential MRR growth, market share capture, pricing power)
    
    Provide a confidence score (0.0 to 1.0) for each estimation based on the specificity of the event.
    
    Market Events:
    {context}
    
    For each event, return an EventImpact object.
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
    
    if "reasoning_trace" not in updated_state:
        updated_state["reasoning_trace"] = []
    updated_state["reasoning_trace"].append(f"ImpactEstimator: Analyzed impact for {len(all_impact_estimates)} events.")
    
    return updated_state

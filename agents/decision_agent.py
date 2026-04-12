"""Generate 5-7 actionable strategic decisions."""

from __future__ import annotations

import json
import logging
from typing import Any, List

from graph import AgentState, StrategicDecision
from agents.utils import get_gemini_llm
from pydantic import BaseModel, Field

LOGGER = logging.getLogger(__name__)

class DecisionOutput(BaseModel):
    decisions: List[StrategicDecision] = Field(description="A list of 5-7 strategic decisions")

def run(state: AgentState) -> AgentState:
    """Generate high-impact decisions based on synthesized insights and event impacts."""
    print(f"\n{'='*70}")
    print(f"🎯 [AGENT] DecisionAgent - Strategic Decision Generation")
    print(f"{'='*70}")
    
    llm = get_gemini_llm(model_env_var="GEMINI_MODEL", default_model="gemini-2.5-flash", temperature=0.1)
    if not llm:
        print("  ⚠️ LLM not available. Skipping decision generation.")
        return state

    company = state["company_name"]
    events = [e.model_dump() for e in state.get("extracted_events", [])]
    impacts = [i.model_dump() for i in state.get("impact_estimates", [])]
    strengths = [s.model_dump() if hasattr(s, 'model_dump') else s for s in state.get("strengths", [])]
    weaknesses = [w.model_dump() if hasattr(w, 'model_dump') else w for w in state.get("weaknesses", [])]
    
    prompt = f"""
    You are a senior strategic advisor for {company}. Based on the analyzed market intelligence, generate 5-7 high-impact strategic decisions.
    
    Each decision MUST include:
    1. action: (specific, measurable action)
    2. reason: (strategic reasoning linked to a specific market event)
    3. evidence: (the data point or event supporting this)
    4. expected_outcome: (measurable business impact)
    5. confidence: (0.0 to 1.0)
    
    Intelligence Context:
    - Market Events: {json.dumps(events)}
    - Impact Analysis: {json.dumps(impacts)}
    - Synthesized Strengths: {json.dumps(strengths)}
    - Synthesized Weaknesses: {json.dumps(weaknesses)}
    
    Return exactly 5-7 decisions in a DecisionOutput object.
    """
    
    try:
        print(f"  🤖 AI is formulating {company}'s strategic roadmap...")
        structured_llm = llm.with_structured_output(DecisionOutput)
        response = structured_llm.invoke(prompt)
        
        strategic_decisions = response.decisions
        print(f"  ✅ Formulated {len(strategic_decisions)} strategic decisions.")
        
    except Exception as exc:
        LOGGER.error(f"DecisionAgent failed: {exc}")
        return state

    updated_state = dict(state)
    updated_state["strategic_decisions"] = strategic_decisions
    
    if "reasoning_trace" not in updated_state:
        updated_state["reasoning_trace"] = []
    updated_state["reasoning_trace"].append(f"DecisionAgent: Generated {len(strategic_decisions)} strategic decisions.")
    
    return updated_state

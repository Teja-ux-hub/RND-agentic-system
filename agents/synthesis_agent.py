"""Synthesize raw intelligence into actionable strategic insights."""

from __future__ import annotations

import json
from typing import Any, List

from agents.utils import get_gemini_llm, LOGGER
from graph import AgentState, Strength, Weakness, Recommendation, Battlecard
from pydantic import BaseModel, Field


class SynthesisOutput(BaseModel):
    strengths: list[Strength] = Field(description="The company's key strengths (must reference competitor/event)")
    weaknesses: list[Weakness] = Field(description="The company's key weaknesses (must reference competitor/event)")
    market_trends: list[str] = Field(description="Key market trends affecting the company")
    battlecard: Battlecard = Field(description="A sales battlecard for the company")


def _call_gemini_for_synthesis(state: AgentState) -> dict[str, Any]:
    llm = get_gemini_llm(model_env_var="GEMINI_MODEL", default_model="gemini-2.5-flash", temperature=0.1)
    
    if not llm:
        return {
            "strengths": [],
            "weaknesses": [],
            "market_trends": [],
            "battlecard": {"strengths": [], "weaknesses": [], "win_themes": {}},
        }

    try:
        from langchain_core.prompts import ChatPromptTemplate

        company = state["company_name"]
        events = [e.model_dump() for e in state.get("extracted_events", [])]
        impacts = [i.model_dump() for i in state.get("impact_estimates", [])]
        
        prompt = f"""
        You are a world-class business strategist. Your goal is to synthesize raw market events and impact estimates for {company} into high-quality, actionable strategic insights.
        
        AVOID GENERIC SWOT.
        Every insight MUST:
        1. Reference a specific competitor.
        2. Reference a specific market event.
        3. Include the business impact (on revenue, users, or market position).
        
        Context:
        - Strategic Events: {json.dumps(events)}
        - Impact Estimations: {json.dumps(impacts)}
        
        Return the synthesis as structured JSON matching the SynthesisOutput model.
        """
        
        print(f"  > Calling Gemini for high-quality strategic synthesis ({company})...")
        structured_llm = llm.with_structured_output(SynthesisOutput)
        response = structured_llm.invoke(prompt)
        
        return {
            "strengths": [s.model_dump() for s in response.strengths],
            "weaknesses": [w.model_dump() for w in response.weaknesses],
            "market_trends": response.market_trends,
            "battlecard": response.battlecard.model_dump(),
        }
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("SynthesisAgent analysis failed for %s: %s", state["company_name"], exc)
        return {
            "strengths": [],
            "weaknesses": [],
            "market_trends": [],
            "battlecard": {"strengths": [], "weaknesses": [], "win_themes": {}},
        }


def run(state: AgentState) -> AgentState:
    """Synthesize raw intelligence into actionable strategic insights."""
    print(f"\n{'='*70}")
    print(f"🧠 [AGENT] SynthesisAgent - Strategic Intelligence Synthesis")
    print(f"{'='*70}")
    print(f"Analyzing data for: {state['company_name']}")
    
    LOGGER.info(f"SynthesisAgent: starting high-quality synthesis for {state['company_name']}")

    print("  🤖 AI synthesis in progress: Converting data to specific strategic insights...")
    synthesis_result = _call_gemini_for_synthesis(state)

    print(f"  ✅ Synthesis complete: {len(synthesis_result['strengths'])} specific strengths, {len(synthesis_result['weaknesses'])} weaknesses identified.")
    print(f"  📈 Market trends: {len(synthesis_result['market_trends'])} key trends.")
    print(f"{'='*70}\n")

    updated_state = dict(state)
    updated_state["strengths"] = synthesis_result["strengths"]
    updated_state["weaknesses"] = synthesis_result["weaknesses"]
    updated_state["market_trends"] = synthesis_result["market_trends"]
    updated_state["battlecard"] = synthesis_result["battlecard"]
    
    if "reasoning_trace" not in updated_state:
        updated_state["reasoning_trace"] = []
    updated_state["reasoning_trace"].append(f"SynthesisAgent: Generated {len(synthesis_result['strengths'])} strengths and {len(synthesis_result['weaknesses'])} weaknesses.")

    return updated_state

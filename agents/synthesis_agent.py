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


def _call_gemini_for_synthesis(state: AgentState) -> tuple[dict, dict]:
    llm = get_gemini_llm(model_env_var="GEMINI_MODEL", default_model="gemini-2.5-flash", temperature=0.1)

    _empty = {
        "strengths": [], "weaknesses": [], "market_trends": [],
        "battlecard": {"strengths": [], "weaknesses": [], "win_themes": {}},
    }
    if not llm:
        return _empty, _empty

    try:
        from langchain_core.prompts import ChatPromptTemplate

        company = state["company_name"]
        events = [e.model_dump() for e in state.get("extracted_events", [])]
        impacts = [i.model_dump() for i in state.get("impact_estimates", [])]
        
        prompt = f"""You are a competitive intelligence synthesis agent for {company}.
You are part of a competitive intelligence workflow. Prioritize specific, verifiable, recent business evidence.
Avoid generic strategy language. Prefer concrete facts over vague summaries.
If evidence is weak, say so explicitly. Do not invent metrics, product names, dates, pricing, or partnerships.
Normalize findings into structured categories so downstream agents can compare companies consistently.
Always favor outputs that are useful for weekly reporting, alerts, and competitive decision-making.

Your goal is to convert structured events and impact estimates into clear, actionable intelligence
for a product dashboard and weekly report.

Do NOT generate generic SWOT text.
Do NOT generate vague strategy statements.
Every insight must be tied to a specific competitor and specific evidence.

Required output sections:
1. competitor_moves — what competitors did recently and why it matters
2. pricing_insights — pricing changes, packaging shifts, free tier changes
3. product_and_feature_insights — launches, updates, feature gaps
4. review_and_customer_signal_insights — sentiment shifts, complaints, migration signals
5. messaging_and_positioning_insights — homepage changes, claimed differentiators, new angles
6. market_trends — macro trends affecting the company
7. risks_to_monitor — specific risks with named competitor and evidence
8. opportunities_to_exploit — specific opportunities with named competitor and evidence
9. battlecards — how to win against each named competitor

Rules:
- Each insight must reference a named competitor.
- Each insight must reference at least one event or evidence item.
- State why it matters for revenue, users, retention, positioning, or pricing.
- Keep insights compact and high-signal.
- Prioritize items suitable for a weekly executive report.

Context:
- Strategic Events: {json.dumps(events)}
- Impact Estimations: {json.dumps(impacts)}

Return structured JSON with all 9 sections.
"""

        print(f"  > Calling Gemini for high-quality strategic synthesis ({company})...")
        structured_llm = llm.with_structured_output(SynthesisOutput)
        response = structured_llm.invoke(prompt)

        synthesis_dict = {
            "strengths": [s.model_dump() for s in response.strengths],
            "weaknesses": [w.model_dump() for w in response.weaknesses],
            "market_trends": response.market_trends,
            "battlecard": response.battlecard.model_dump(),
        }

        # Store full synthesis output for downstream agents and PDF
        full_synthesis = synthesis_dict.copy()
        full_synthesis["competitor_moves"] = getattr(response, "competitor_moves", [])
        full_synthesis["pricing_insights"] = getattr(response, "pricing_insights", [])
        full_synthesis["product_and_feature_insights"] = getattr(response, "product_and_feature_insights", [])
        full_synthesis["review_and_customer_signal_insights"] = getattr(response, "review_and_customer_signal_insights", [])
        full_synthesis["messaging_and_positioning_insights"] = getattr(response, "messaging_and_positioning_insights", [])
        full_synthesis["risks_to_monitor"] = getattr(response, "risks_to_monitor", [])
        full_synthesis["opportunities_to_exploit"] = getattr(response, "opportunities_to_exploit", [])

        return synthesis_dict, full_synthesis
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("SynthesisAgent analysis failed for %s: %s", state["company_name"], exc)
        _empty = {
            "strengths": [], "weaknesses": [], "market_trends": [],
            "battlecard": {"strengths": [], "weaknesses": [], "win_themes": {}},
        }
        return _empty, _empty


def run(state: AgentState) -> AgentState:
    """Synthesize raw intelligence into actionable strategic insights."""
    print(f"\n{'='*70}")
    print(f"🧠 [AGENT] SynthesisAgent - Strategic Intelligence Synthesis")
    print(f"{'='*70}")
    print(f"Analyzing data for: {state['company_name']}")
    
    LOGGER.info(f"SynthesisAgent: starting high-quality synthesis for {state['company_name']}")

    print("  🤖 AI synthesis in progress: Converting data to specific strategic insights...")
    synthesis_result, full_synthesis = _call_gemini_for_synthesis(state)

    print(f"  ✅ Synthesis complete: {len(synthesis_result['strengths'])} strengths, {len(synthesis_result['weaknesses'])} weaknesses identified.")
    print(f"  📈 Market trends: {len(synthesis_result['market_trends'])} key trends.")
    print(f"{'='*70}\n")

    updated_state = dict(state)
    updated_state["strengths"] = synthesis_result["strengths"]
    updated_state["weaknesses"] = synthesis_result["weaknesses"]
    updated_state["market_trends"] = synthesis_result["market_trends"]
    updated_state["battlecard"] = synthesis_result["battlecard"]
    updated_state["synthesis_output"] = full_synthesis
    
    if "reasoning_trace" not in updated_state:
        updated_state["reasoning_trace"] = []
    updated_state["reasoning_trace"].append(f"SynthesisAgent: Generated {len(synthesis_result['strengths'])} strengths and {len(synthesis_result['weaknesses'])} weaknesses.")

    return updated_state

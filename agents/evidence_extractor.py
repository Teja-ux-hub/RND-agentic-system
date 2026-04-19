"""Extract structured events from raw news data."""

from __future__ import annotations

import json
import logging
from typing import Any, List

from graph import AgentState, CompetitorEvent, NewsItem
from agents.utils import get_gemini_llm
from pydantic import BaseModel, Field

LOGGER = logging.getLogger(__name__)

class ExtractionOutput(BaseModel):
    events: List[CompetitorEvent] = Field(description="A list of extracted competitor events")

def run(state: AgentState) -> AgentState:
    """Extract only important events (launch, pricing, partnership, expansion) from news."""
    print(f"\n{'='*70}")
    print(f"🔍 [AGENT] EvidenceExtractorAgent - Event Extraction")
    print(f"{'='*70}")
    
    llm = get_gemini_llm(model_env_var="GEMINI_MODEL", default_model="gemini-2.5-flash", temperature=0.1)
    if not llm:
        print("  ⚠️ LLM not available. Skipping extraction.")
        return state

    all_extracted_events: List[CompetitorEvent] = []
    
    # Process news data for each company
    for company, news_items in state["news_data"].items():
        if not news_items:
            continue
            
        print(f"\n  Processing news for: {company}")
        
        # Prepare context for Gemini
        context = "\n".join([
            f"Title: {item['title']}\nSnippet: {item['snippet']}\nURL: {item['url']}\n---"
            for item in news_items
        ])
        
        prompt = f"""You are an evidence extraction agent in a competitive intelligence system.
You are part of a competitive intelligence workflow. Prioritize specific, verifiable, recent business evidence.
Avoid generic strategy language. Prefer concrete facts over vague summaries.
If evidence is weak, say so explicitly. Do not invent metrics, product names, dates, pricing, or partnerships.
Normalize findings into structured categories so downstream agents can compare companies consistently.

Extract ONLY the most important strategic business events for {company} from the context below.

Focus on these event types:
- launch
- pricing_change
- packaging_change
- promotion
- partnership
- expansion
- acquisition
- positioning_change
- review_signal
- customer_experience_signal
- hiring_signal
- market_claim

Extraction rules:
1. Only extract events supported by the provided evidence.
2. Ignore weak or duplicate items.
3. Prefer recent, high-business-impact items.
4. For pricing items, capture old price and new price if clearly stated; otherwise leave as null.
5. For review items, capture whether the signal is positive, negative, or mixed.
6. For positioning items, capture the claimed differentiator if visible.
7. Keep descriptions concise and evidence-linked.
8. Return structured output only.

News Context:
{context}

For each event return:
- company (set to "{company}")
- event_type (from the list above)
- priority (high, medium, or low)
- description (concise, evidence-linked)
- evidence_type (news, blog, pricing_page, review, website_copy, market_report)
- source_url
- event_date (if available, else null)
- old_value (if available, else null)
- new_value (if available, else null)
- sentiment_signal (positive, negative, or mixed — only for review/customer signals, else null)
- positioning_angle (claimed differentiator — only for positioning changes, else null)
"""
        
        try:
            structured_llm = llm.with_structured_output(ExtractionOutput)
            response = structured_llm.invoke(prompt)
            
            # Ensure competitor name is set correctly
            for event in response.events:
                event.competitor = company
                all_extracted_events.append(event)
                
            print(f"  ✅ Extracted {len(response.events)} strategic events.")
            
        except Exception as exc:
            LOGGER.error(f"EvidenceExtractorAgent failed for {company}: {exc}")
            continue

    updated_state = dict(state)
    updated_state["extracted_events"] = all_extracted_events
    
    if "reasoning_trace" not in updated_state:
        updated_state["reasoning_trace"] = []
    updated_state["reasoning_trace"].append(f"EvidenceExtractor: Extracted {len(all_extracted_events)} events from news.")
    
    return updated_state

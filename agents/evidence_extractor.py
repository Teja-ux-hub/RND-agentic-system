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
        
        prompt = f"""
        Extract ONLY the most important strategic business events for {company} from the news below.
        Focus on: product launches, pricing changes, key partnerships, and market expansions.
        
        News Context:
        {context}
        
        For each event, specify:
        1. event_type: (launch, pricing, partnership, or expansion)
        2. description: (concise, high-impact summary)
        3. source_url: (the original URL from the news)
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

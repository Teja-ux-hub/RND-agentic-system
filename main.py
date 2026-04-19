"""API entrypoint for the Competitive Intelligence Multi-Agent System."""

from __future__ import annotations

import os
import uvicorn
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from graph import AgentState, get_app

# Load environment
load_dotenv(find_dotenv())

app = FastAPI(
    title="Competitive Intelligence API",
    description="Production-grade AI API for market analysis and strategic reporting",
    version="2.0.0"
)

# --- Models ---
class AnalysisRequest(BaseModel):
    company: str
    sector: Optional[str] = None
    competitors: Optional[List[str]] = None

# --- API Routes ---
router = APIRouter()

@router.get("/")
async def root():
    """Redirect root URL to interactive documentation."""
    return RedirectResponse(url="/docs")

@router.get("/favicon.ico")
async def favicon():
    """Silence favicon.ico 404s."""
    return {}

@router.post("/analyze")
async def analyze(request: AnalysisRequest):
    """Run the full AI pipeline and return structured JSON + file paths."""
    try:
        # Initialize state exactly as graph.py expects
        initial_state: AgentState = {
            "company_name": request.company,
            "sector": request.sector,
            "competitors": request.competitors or [],
            "ticker": None,
            "company_description": "",
            "company_profile": {},
            "competitor_tickers": {},
            "competitor_meta": [],
            "strengths": [],
            "weaknesses": [],
            "market_trends": [],
            "product_moves": {},
            "actions": [],
            "battlecard": {"strengths": [], "weaknesses": [], "win_themes": {}},
            "news_data": {},
            "metrics": [],
            "scoring_matrices": {},
            "synthesis_output": {},
            "alert_summary": {},
            "strategy_summary": "",
            "pdf_path": "",
            "excel_path": "",
            "reasoning_trace": []
        }

        # Execute Graph
        workflow = get_app()
        final_state = workflow.invoke(initial_state)

        # Return combined data
        return {
            "company": final_state["company_name"],
            "analysis": {
                "strengths": [s.get("description") if isinstance(s, dict) else s.description for s in final_state["strengths"]],
                "weaknesses": [w.get("description") if isinstance(w, dict) else w.description for w in final_state["weaknesses"]],
                "recommendations": [a.get("action_title") if isinstance(a, dict) else a.action_title for a in final_state["actions"]],
                "summary": final_state["strategy_summary"]
            },
            "files": {
                "pdf_path": final_state["pdf_path"],
                "download_url": f"/download/{request.company.lower().replace(' ', '_')}"
            },
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download/{company}")
async def download_report(company: str):
    """Serve the generated PDF report."""
    # Matches the path generated in StrategyAgent
    reports_dir = Path("outputs/reports")
    pdf_path = reports_dir / f"{company.lower().replace(' ', '_')}_strategy_report.pdf"
    
    if pdf_path.exists():
        return FileResponse(
            path=pdf_path,
            filename=f"{company}_strategy_report.pdf",
            media_type='application/pdf'
        )
    raise HTTPException(status_code=404, detail="Report not found. Run /analyze first.")

@router.get("/health")
async def health():
    return {"status": "ok"}

app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

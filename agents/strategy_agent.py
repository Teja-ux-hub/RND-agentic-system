"""Generate a strategy memo and export PDF/Excel outputs."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from graph import AgentState
from agents.utils import get_gemini_llm

LOGGER = logging.getLogger(__name__)


def _fallback_strategy_summary(state: AgentState) -> str:
    company = state['company_name'].title()
    competitors = [c.title() for c in state.get('competitors', [])]
    comp_list = ", ".join(competitors) or "market rivals"
    
    lines = [
        f"# Strategic Executive Summary: {company}",
        f"- {company} is currently being analyzed against its primary market rivals: {comp_list}.",
        f"- The analysis focuses on {company}'s current market positioning and growth trajectory.",
        f"- Strategic recommendations are based on observed market trends and available financial metrics.",
        "",
        f"# {company} Competitive Advantage Analysis",
        f"- {company} maintains its market position through its core operational strengths and brand recognition.",
        "- Customer loyalty and platform stickiness are key drivers for long-term sustainability.",
        f"- Recent strategic moves suggest a focus on optimizing core services while exploring adjacent growth opportunities.",
        "",
        "# Rivalry deep-dive",
    ]

    for competitor in state.get("competitors", []):
        c_title = competitor.title()
        lines.extend(
            [
                f"## {c_title} vs {company}",
                f"- **Competitive Stance**: {c_title} is a key player with significant market presence in the {state.get('sector', 'relevant')} sector.",
                f"- **Comparative Analysis**: {c_title} competes directly with {company} on service quality and pricing efficiency.",
                f"- **Key Move**: {', '.join(move.get('name', '') for move in state.get('product_moves', {}).get(competitor, [])[:2]) or 'Recent platform updates and operational optimizations.'}",
                "",
            ]
        )

    lines.extend(
        [
            "# Stock Trend & Valuation Overview",
            f"- {company}'s market valuation is influenced by its path to sustainable profitability and revenue growth.",
            "- Stock price action typically correlates with broader market sentiment and sector-specific news intensity.",
            "",
            "# Market Dominance Recommendations",
            f"1. Enhance {company}'s core product offering to increase user retention and lifetime value.",
            "2. Accelerate digital transformation to improve operational efficiency across the board.",
            "3. Optimize logistics and supply chain management to reduce unit costs.",
            "4. Expand into high-growth untapped markets where competitor presence is minimal.",
            "5. Leverage data analytics for hyper-personalized customer engagement.",
            "6. Form strategic partnerships with key industry stakeholders.",
            "7. Explore new monetization models to diversify revenue streams.",
            "8. Invest in sustainable and green technologies to future-proof operations.",
            "9. Strengthen brand identity through targeted marketing and community building.",
            "10. Continuously monitor competitor moves and adapt strategy in real-time.",
            "",
            "# Strategic Guardrails (What NOT to copy)",
            "- Avoid engaging in aggressive price wars that lead to value destruction.",
            "- Don't over-expand into non-core areas without a clear path to profitability.",
            "- Never compromise on product quality or customer service for short-term gains.",
            "- Resist copying competitor features that do not align with the core brand mission.",
            "- Avoid opaque operational practices that could erode stakeholder trust.",
        ]
    )
    return "\n".join(lines)


def _generate_strategy_markdown(state: AgentState) -> str:
    llm = get_gemini_llm(model_env_var="GEMINI_MODEL", default_model="gemini-2.0-flash", temperature=0.1)
    prompt = (
        "You are a Senior Strategy Consultant. Create a GODLEVEL competitive intelligence report.\n"
        f"Primary Company: {state['company_name']}\n"
        f"Sector: {state.get('sector', 'N/A')}\n\n"
        "The goal is not just data, but deep strategic insight: 'Are we behind? Why? How to go deeper?'\n\n"
        "Sections Required:\n"
        "1. Executive Summary: Ahead/Behind/Equal status and the 1-3 power reasons why.\n"
        "2. Competitive Moat Analysis: Why our company is unique (or why rivals are winning).\n"
        "3. Market Deepening Strategy: 3-5 concrete moves to penetrate untapped segments or cities.\n"
        "4. Public Issues & PR Crisis: Recent major complaints, scandals, or regulatory storms (yours + rivals).\n"
        "5. User Sentiment & Feature Feedback: What users say about latest updates and explicit rival comparisons.\n"
        "6. Rivalry Matrix: Direct comparison of pricing, UX, trust, and network effects.\n"
        "7. 10 Bold Actions for Dominance and 5 Traps to Avoid.\n\n"
        f"Data context:\n"
        f"- Market Position: {json.dumps(state.get('market_position', {}))}\n"
        f"- Public Issues: {json.dumps(state.get('public_issues', {}))}\n"
        f"- User Sentiment: {json.dumps(state.get('user_sentiment', {}))}\n"
        f"- Product Initiatives: {json.dumps(state.get('product_moves', {}), default=str)}\n"
        f"- Market Metrics: {json.dumps(state.get('metrics', []), default=str)}\n"
    )

    if llm:
        try:
            response = llm.invoke(prompt)
            if response.content:
                return response.content
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("StrategyAgent Gemini generation failed, using fallback summary: %s", exc)

    return _fallback_strategy_summary(state)


def _ensure_output_dirs() -> tuple[str, str]:
    reports_dir = os.getenv("REPORTS_DIR", os.path.join("outputs", "reports"))
    data_dir = os.getenv("DATA_DIR", os.path.join("outputs", "data"))
    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)
    return reports_dir, data_dir


def _save_metrics_excel(metrics: list[dict], company_name: str, data_dir: str) -> str:
    safe_name = company_name.lower().replace(" ", "_")
    excel_path = os.path.join(data_dir, f"{safe_name}_metrics.xlsx")
    
    # Ensure clear column mapping for Excel
    formatted_metrics = []
    for m in metrics:
        formatted_metrics.append({
            "Company Name": m.get("Company"),
            "Ticker": m.get("Ticker"),
            "Current Price": m.get("CurrentPrice"),
            "7D % Change": m.get("WeekChangePct"),
            "Market Cap": m.get("MarketCap")
        })
    
    pd.DataFrame(formatted_metrics).to_excel(excel_path, index=False, engine="openpyxl")
    return excel_path


def _top_strategy_bullets(markdown_text: str, max_items: int = 5) -> list[str]:
    bullets = []
    for line in markdown_text.splitlines():
        stripped = line.strip()
        # Look for lines starting with - or * or numbers like 1. 
        if stripped.startswith(("- ", "* ", "1. ", "2. ", "3. ", "4. ", "5. ")):
            # Remove the prefix
            content = stripped.lstrip("-* ").strip()
            if content and not content.startswith("#"):
                bullets.append(content)
        if len(bullets) >= max_items:
            break
    return bullets or ["Analytical run completed; review the full Markdown summary for deep strategic insights."]


def _save_pdf_summary(state: AgentState, strategy_md: str, reports_dir: str) -> str:
    safe_name = state["company_name"].lower().replace(" ", "_")
    pdf_path = os.path.join(reports_dir, f"{safe_name}_strategy_report.pdf")
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"Competitive Intelligence Brief: {state['company_name']}", styles["Title"]),
        Paragraph(datetime.now().strftime("%Y-%m-%d"), styles["Normal"]),
        Spacer(1, 8),
        Paragraph(f"<b>Overview:</b> {state.get('company_description', '')}", styles["BodyText"]),
        Spacer(1, 8),
        Paragraph(
            f"<b>Competitors:</b> {', '.join(state.get('competitors', [])) or 'No competitors found'}",
            styles["BodyText"],
        ),
        Spacer(1, 10),
    ]

    metrics_rows = [["Company", "7-Day %", "Current Price"]]
    for row in state.get("metrics", [])[:6]:
        metrics_rows.append(
            [
                str(row.get("Company", "")),
                str(row.get("WeekChangePct", "")),
                str(row.get("CurrentPrice", "")),
            ]
        )

    table = Table(metrics_rows, colWidths=[170, 90, 110])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            ]
        )
    )
    story.extend([table, Spacer(1, 10), Paragraph("Top 5 Strategy Bullets", styles["Heading2"])])

    for bullet in _top_strategy_bullets(strategy_md):
        story.append(Paragraph(f"- {bullet}", styles["BodyText"]))
        story.append(Spacer(1, 4))

    doc.build(story)
    return pdf_path


def run(state: AgentState) -> AgentState:
    print(f"\n--- [AGENT] StrategyAgent finalizing report for: {state['company_name']} ---")
    LOGGER.info("StrategyAgent: generating strategy summary and exports")

    reports_dir, data_dir = _ensure_output_dirs()
    
    print("Asking Gemini to synthesize all findings into a Markdown strategy memo...")
    strategy_summary = _generate_strategy_markdown(state)
    
    print("Generating Excel export for market metrics...")
    excel_path = _save_metrics_excel(state.get("metrics", []), state["company_name"], data_dir)
    
    print("Generating PDF summary report with top strategy bullets...")
    pdf_path = _save_pdf_summary(state, strategy_summary, reports_dir)

    updated_state = dict(state)
    updated_state["strategy_summary"] = strategy_summary
    updated_state["excel_path"] = excel_path
    updated_state["pdf_path"] = pdf_path
    return updated_state

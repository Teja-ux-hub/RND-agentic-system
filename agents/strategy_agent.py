"""Generate a strategy memo and export PDF/Excel outputs."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime

import pandas as pd
try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    plt = None

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak

from graph import AgentState, ScoringMatrix

LOGGER = logging.getLogger(__name__)


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


def _create_chart(scoring_matrices: dict[str, ScoringMatrix], company_name: str, reports_dir: str) -> str | None:
    """Creates a bar chart of the competitive scoring matrix and saves it to a file."""
    if not HAS_MATPLOTLIB or not scoring_matrices:
        LOGGER.warning("Matplotlib not installed or no scoring data. Skipping chart generation.")
        return None

    labels = list(scoring_matrices.keys())
    data = {
        "Price": [v.price_competitiveness for v in scoring_matrices.values()],
        "Features": [v.feature_parity for v in scoring_matrices.values()],
        "Momentum": [v.market_momentum for v in scoring_matrices.values()],
        "Brand": [v.brand_strength for v in scoring_matrices.values()],
    }

    x = range(len(labels))
    width = 0.2

    fig, ax = plt.subplots(figsize=(10, 6))
    for i, (attribute, values) in enumerate(data.items()):
        offset = width * (i - 1.5)
        rects = ax.bar([val + offset for val in x], values, width, label=attribute)
        ax.bar_label(rects, padding=3, fmt="%.1f")

    ax.set_ylabel("Scores (1-10)")
    ax.set_title(f"Competitive Scoring Matrix: {company_name} vs. Rivals")
    ax.set_xticks(x, labels)
    ax.legend(loc="upper left", ncols=len(data.keys()))
    ax.set_ylim(0, 11)

    chart_path = os.path.join(reports_dir, f"{company_name.lower().replace(' ', '_')}_chart.png")
    fig.tight_layout()
    plt.savefig(chart_path)
    LOGGER.info("Chart saved to %s", chart_path)
    return chart_path


def _save_pdf_summary(state: AgentState, reports_dir: str) -> str:
    safe_name = state["company_name"].lower().replace(" ", "_")
    pdf_path = os.path.join(reports_dir, f"{safe_name}_strategy_report.pdf")
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"<b style='color:#2563eb;'>Competitive Intelligence Brief</b>", styles["Title"]),
        Paragraph(f"<b>{state['company_name']}</b>", styles["Heading1"]),
        Paragraph(datetime.now().strftime("%B %Y - Confidential Report"), styles["Normal"]),
        Spacer(1, 16),
        Paragraph(
            f"<b>Executive Overview:</b> {state.get('company_description', 'Comprehensive competitive analysis')}",
            styles["BodyText"]
        ),
        Spacer(1, 8),
    ]
    
    # Key Competitors
    competitors_list = state.get('competitors', [])
    if competitors_list:
        story.append(
            Paragraph(
                f"<b>Market Landscape:</b> Analyzing {len(competitors_list)} key competitors: {', '.join(competitors_list[:5])}{'...' if len(competitors_list) > 5 else ''}",
                styles["BodyText"]
            )
        )
        Spacer(1, 10)

    # Add chart
    chart_path = _create_chart(state.get("scoring_matrices", {}), state["company_name"], reports_dir)
    if chart_path and os.path.exists(chart_path):
        story.append(Image(chart_path, width=500, height=250))
        story.append(Spacer(1, 12))

    # Strategic Decisions Section (New)
    if state.get("strategic_decisions"):
        story.append(Spacer(1, 16))
        story.append(Paragraph("🚀 High-Impact Strategic Roadmap", styles["Heading2"]))
        story.append(Spacer(1, 8))
        for idx, decision in enumerate(state["strategic_decisions"], 1):
            story.append(Paragraph(f"<b>Decision {idx}: {decision.action}</b>", styles["BodyText"]))
            story.append(Paragraph(f"   <i>Reason: {decision.reason}</i>", styles["BodyText"]))
            story.append(Paragraph(f"   <i>Evidence: {decision.evidence}</i>", styles["BodyText"]))
            story.append(Paragraph(f"   <i>Outcome: {decision.expected_outcome} | Confidence: {int(decision.confidence*100)}%</i>", styles["BodyText"]))
            story.append(Spacer(1, 10))

    # Strengths Section
    if state.get("strengths"):
        story.append(Spacer(1, 16))
        story.append(Paragraph("🎯 Evidence-Backed Strengths", styles["Heading2"]))
        story.append(Spacer(1, 8))
        for idx, s in enumerate(state["strengths"], 1):
            desc = s.description if hasattr(s, 'description') else s.get('description', 'N/A')
            impact = s.impact if hasattr(s, 'impact') else s.get('impact', 'N/A')
            links = s.evidence_links if hasattr(s, 'evidence_links') else s.get('evidence_links', [])
            
            story.append(Paragraph(f"<b>{idx}. {desc}</b>", styles["BodyText"]))
            story.append(Paragraph(f"   <i>Business Impact: {impact}</i>", styles["BodyText"]))
            if links:
                story.append(Paragraph(f"   <link href='{links[0]}' color='#2563eb'>Source Evidence</link>", styles["BodyText"]))
            story.append(Spacer(1, 10))

    # Weaknesses Section
    if state.get("weaknesses"):
        story.append(Spacer(1, 16))
        story.append(Paragraph("⚠️ Strategic Vulnerabilities", styles["Heading2"]))
        story.append(Spacer(1, 8))
        for idx, w in enumerate(state["weaknesses"], 1):
            desc = w.description if hasattr(w, 'description') else w.get('description', 'N/A')
            impact = w.impact if hasattr(w, 'impact') else w.get('impact', 'N/A')
            links = w.evidence_links if hasattr(w, 'evidence_links') else w.get('evidence_links', [])

            story.append(Paragraph(f"<b>{idx}. {desc}</b>", styles["BodyText"]))
            story.append(Paragraph(f"   <i>Risk Impact: {impact}</i>", styles["BodyText"]))
            if links:
                story.append(Paragraph(f"   <link href='{links[0]}' color='#dc2626'>Risk Evidence</link>", styles["BodyText"]))
            story.append(Spacer(1, 10))

    story.append(PageBreak())

    # Extracted Events (New Section)
    if state.get("extracted_events"):
        story.append(Paragraph("📰 Critical Market Events", styles["Heading2"]))
        story.append(Spacer(1, 8))
        for idx, event in enumerate(state["extracted_events"][:10], 1):
            story.append(Paragraph(f"<b>{idx}. {event.competitor}: {event.event_type.capitalize()}</b>", styles["BodyText"]))
            story.append(Paragraph(f"   <i>{event.description}</i>", styles["BodyText"]))
            story.append(Paragraph(f"   <link href='{event.source_url}' color='#2563eb'>Read Full Article</link>", styles["BodyText"]))
            story.append(Spacer(1, 8))
        story.append(Spacer(1, 16))

    # Add summary text
    summary_text = state.get("strategy_summary", "No summary available.").replace("\n", "<br/>")
    story.append(Paragraph("📊 Synthesized Market Analysis", styles["Heading2"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(summary_text, styles["BodyText"]))
    
    # Footer
    story.append(Spacer(1, 24))
    story.append(Paragraph("<hr/>", styles["Normal"]))
    story.append(Paragraph(
        "<i>This report is confidential and intended for authorized use only. For questions, contact your strategic advisor.</i>",
        styles["BodyText"]
    ))

    doc.build(story)
    return pdf_path


def run(state: AgentState) -> AgentState:
    print(f"\n--- [AGENT] StrategyAgent generating professional reports for: {state['company_name']} ---")
    LOGGER.info("StrategyAgent: generating reports")

    reports_dir, data_dir = _ensure_output_dirs()
    
    print("Generating Excel export for market metrics...")
    excel_path = _save_metrics_excel(state.get("metrics", []), state["company_name"], data_dir)
    
    print("Generating PDF report with enhanced strategic intelligence...")
    pdf_path = _save_pdf_summary(state, reports_dir)
    
    print(f"\nStrategy report generated: {pdf_path}")
    print(f"Metrics data exported: {excel_path}")

    updated_state = dict(state)
    updated_state["excel_path"] = excel_path
    updated_state["pdf_path"] = pdf_path
    return updated_state

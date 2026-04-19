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
    S = styles

    def h1(text): return Paragraph(f"<b>{text}</b>", S["Heading1"])
    def h2(text): return Paragraph(f"<b>{text}</b>", S["Heading2"])
    def body(text): return Paragraph(str(text).replace("\n", "<br/>"), S["BodyText"])
    def bullet(text): return Paragraph(f"• {text}", S["BodyText"])
    def sp(): return Spacer(1, 10)

    story = []

    # ── 1. Executive Summary ──────────────────────────────────────────────
    story += [h1("1. Executive Summary"), sp(),
              body(f"<b>Company:</b> {state['company_name']}"),
              body(datetime.now().strftime("%B %Y — Confidential Report")), sp(),
              body(state.get("company_description", "Comprehensive competitive analysis.")), sp()]

    # ── 2. Company Overview ───────────────────────────────────────────────
    story += [PageBreak(), h1("2. Company Overview"), sp(),
              body(state.get("company_description", "N/A")), sp()]

    # ── 3. Competitor Watchlist ───────────────────────────────────────────
    story += [h1("3. Competitor Watchlist"), sp()]
    comp_meta = state.get("competitor_meta", [])
    if comp_meta:
        table_data = [["Company", "Type", "Priority", "Reason"]]
        for c in comp_meta:
            table_data.append([c.get("name",""), c.get("competitor_type",""), c.get("priority",""), c.get("reason","")[:80]])
        t = Table(table_data, colWidths=[100, 70, 60, 270])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
            ("FONTSIZE",   (0,0), (-1,-1), 8),
            ("GRID",       (0,0), (-1,-1), 0.4, colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
        ]))
        story += [t, sp()]
    else:
        for c in state.get("competitors", []):
            story.append(bullet(c))
    story.append(sp())

    # ── 4. Key Competitor Moves This Week ─────────────────────────────────
    story += [h1("4. Key Competitor Moves This Week"), sp()]
    synthesis = state.get("synthesis_output", {})
    for move in synthesis.get("competitor_moves", []):
        story.append(bullet(str(move)))
    story.append(sp())

    # ── 5. Pricing Intelligence ───────────────────────────────────────────
    story += [h1("5. Pricing Intelligence"), sp()]
    for item in synthesis.get("pricing_insights", []):
        story.append(bullet(str(item)))
    pricing_events = [e for e in state.get("extracted_events", []) if "pricing" in getattr(e, "event_type", "")]
    for e in pricing_events:
        old = getattr(e, "old_value", None)
        new = getattr(e, "new_value", None)
        change_str = f" ({old} → {new})" if old and new else ""
        story.append(bullet(f"{e.competitor}: {e.description}{change_str}"))
        if e.source_url:
            story.append(Paragraph(f"   <link href='{e.source_url}' color='#2563eb'>Source</link>", S["BodyText"]))
    story.append(sp())

    # ── 6. Product and Feature Updates ───────────────────────────────────
    story += [h1("6. Product and Feature Updates"), sp()]
    for item in synthesis.get("product_and_feature_insights", []):
        story.append(bullet(str(item)))
    story.append(sp())

    # ── 7. Reviews and Customer Signals ──────────────────────────────────
    story += [h1("7. Reviews and Customer Signals"), sp()]
    for item in synthesis.get("review_and_customer_signal_insights", []):
        story.append(bullet(str(item)))
    review_events = [e for e in state.get("extracted_events", []) if "review" in getattr(e, "event_type", "") or "customer" in getattr(e, "event_type", "")]
    for e in review_events:
        sentiment = getattr(e, "sentiment_signal", None)
        label = f" [{sentiment}]" if sentiment else ""
        story.append(bullet(f"{e.competitor}{label}: {e.description}"))
    story.append(sp())

    # ── 8. Messaging and Positioning Shifts ──────────────────────────────
    story += [h1("8. Messaging and Positioning Shifts"), sp()]
    for item in synthesis.get("messaging_and_positioning_insights", []):
        story.append(bullet(str(item)))
    story.append(sp())

    # ── 9. Market and News Intelligence ──────────────────────────────────
    story += [h1("9. Market and News Intelligence"), sp()]
    for trend in state.get("market_trends", []):
        story.append(bullet(str(trend)))
    story.append(sp())

    # ── 10. Risks and Opportunities ──────────────────────────────────────
    story += [PageBreak(), h1("10. Risks and Opportunities"), sp(), h2("Risks to Monitor")]
    for r in synthesis.get("risks_to_monitor", []):
        story.append(bullet(str(r)))
    story += [sp(), h2("Opportunities to Exploit")]
    for o in synthesis.get("opportunities_to_exploit", []):
        story.append(bullet(str(o)))
    story.append(sp())

    # ── 11. Recommended Actions ───────────────────────────────────────────
    story += [h1("11. Recommended Actions"), sp()]
    for idx, decision in enumerate(state.get("strategic_decisions", []), 1):
        cat = getattr(decision, "category", "general")
        action = getattr(decision, "action", "")
        reason = getattr(decision, "reason", "")
        outcome = getattr(decision, "expected_outcome", "")
        urgency = getattr(decision, "urgency", "")
        conf = getattr(decision, "confidence", 0)
        story.append(body(f"<b>{idx}. [{cat.upper()}] {action}</b>"))
        story.append(body(f"   Reason: {reason}"))
        story.append(body(f"   Expected Outcome: {outcome} | Urgency: {urgency} | Confidence: {int(conf*100)}%"))
        story.append(sp())

    # ── 12. Alerts Summary ────────────────────────────────────────────────
    story += [h1("12. Alerts Summary"), sp()]
    alert_summary = state.get("alert_summary", {})
    for level in ["instant", "daily_digest", "weekly_digest"]:
        items = alert_summary.get(level, [])
        if items:
            story.append(h2(f"{level.replace('_', ' ').title()} ({len(items)})"))
            for a in items:
                story.append(bullet(f"{a.get('competitor','')}: {a.get('event','')} — {a.get('rationale','')}"))
            story.append(sp())

    # ── 13. Evidence Appendix ─────────────────────────────────────────────
    story += [PageBreak(), h1("13. Evidence Appendix"), sp()]
    for idx, event in enumerate(state.get("extracted_events", []), 1):
        story.append(body(f"<b>{idx}. {event.competitor} — {getattr(event,'event_type','').replace('_',' ').title()}</b>"))
        story.append(body(f"   {event.description}"))
        if event.source_url:
            story.append(Paragraph(f"   <link href='{event.source_url}' color='#2563eb'>Source: {event.source_url[:80]}</link>", S["BodyText"]))
        story.append(sp())

    # Footer
    story += [Spacer(1, 24),
              Paragraph("<hr/>", S["Normal"]),
              Paragraph("<i>Confidential. For authorized use only.</i>", S["BodyText"])]

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

# Competitive Intelligence Multi-Agent System

A Python 3.11+ project that uses LangGraph, LangChain, Gemini, Tavily, yfinance, pandas, and reportlab to analyze a company against top competitors and generate a one-page PDF, an Excel file, and a compact JSON summary.

## High-Level Architecture

```text
CLI (main.py)
    |
    v
LangGraph StateGraph (graph.py)
    |
    +--> CompetitorFinderAgent
    +--> NewsAndInnovationAgent
    +--> MetricsAgent
    +--> StrategyAgent
            |
            +--> Excel export
            +--> PDF export
```

## Tech Stack

- Python 3.11+
- LangGraph + LangChain
- Gemini API via `langchain-google-genai`
- Tavily API via `tavily-python`
- `yfinance`
- `pandas` + `openpyxl`
- `reportlab`
- `.env` + `python-dotenv`
- `requests`

## How to get God-Level Results

1.  **Rename `.env.example` to `.env`**.
2.  **Add your API Keys**: Get a free Gemini key from Google AI Studio and a Tavily key.
3.  **Run the analysis**: The system will now generate a high-quality, data-driven strategy report with live stock prices and news.

Even without API keys, the system will use a high-quality "God-Level" template to provide a professional-looking analysis based on pre-configured competitive moats and scaling strategies.

## Example Command

```bash
python main.py --company "Tesla" --sector "Electric Vehicles" --competitors Rivian "Lucid Motors"
```

## Notes

- The workflow degrades gracefully when APIs are unavailable.
- Output folders are created automatically in `outputs/reports/` and `outputs/data/`.
- The stock helper uses a small built-in company-to-ticker mapping for common examples and otherwise tries short uppercase symbols.

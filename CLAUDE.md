# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based stock analysis and recommendation system that focuses on TSX (Toronto Stock Exchange) listed companies. The project consists of these modules:

- `recommender.py`: Pure-Python scoring engine. Turns a `Ticker.info` dict into a `StockScore` (composite 0-100, six pillar scores, verdict, reasons, red flags). No network access; all thresholds live in `METRIC_RULES` and `PILLAR_WEIGHTS`.
- `support_handler.py`: Data access via the `stock_handler` class (symbol list, yfinance fetch) plus `score_symbol()` / `recommend()` wrappers around the engine
- `stock_recomend.py`: CLI entry point (ranking table, `--detail`, `--all`, `--capital`, `--excel`)
- `stock_web_gui.py`: Django web UI (`/analyze/` returns a score alongside raw info; `/recommend/` ranks a list)
- `stock_gui.py`: Tkinter desktop UI

## Architecture

The codebase follows a simple modular design:

1. **Data Source**: Fetches TSX company symbols from `tsx.com/files/trading/interlisted-companies.txt`
2. **Data Processing**: Uses `yfinance` library to retrieve detailed stock information
3. **Analysis**: `recommender.score_stock()` maps each metric through a piecewise-linear curve, averages them into pillars (value, quality, growth, momentum, analyst, dividend), weights them into a composite, checks red flags, and decides a verdict
4. **Output**: Console table/detail, JSON for the web UI, Excel export, and optional position sizing via `suggest_allocation()`

Key architectural components:
- `stock_handler` class: Central class handling all stock data operations
- External data dependencies: TSX symbol list (web), Yahoo Finance API (via yfinance)
- File I/O: Excel output for symbol lists (`tsx_symbols.xlsx`)

## Dependencies

Listed in `requirements.txt`:
- `yfinance`: Yahoo Finance API access for stock data
- `pandas`: Data manipulation and Excel file operations  
- `requests`: HTTP requests for TSX symbol list
- `openpyxl`: Excel file writing support
- `django`: web interface only

## Running the Code

Since this is a simple Python project without formal build tools:

```bash
pip install -r requirements.txt

# Score and rank the default watchlist / specific symbols / the whole TSX
python stock_recomend.py
python stock_recomend.py --detail CEU.TO CCO.TO
python stock_recomend.py --all --top 25 --capital 10000 --excel

# Run the offline test suite (no network needed)
python -m unittest discover -s tests -v

# Run individual analysis
python -c "from support_handler import stock_handler; sh = stock_handler(); sh.print_stock_info('CEU.TO')"
```

## Key Functionality

The `stock_handler` class provides:
- `get_all_stock_symbols()`: Fetch current TSX symbol list
- `get_company_info(symbol)`: Get comprehensive stock data
- `print_stock_info(symbol)`: Display formatted financial analysis
- `analyze_etf(ticker)`: ETF-specific analysis
- `get_all_stock()`: Export symbols to Excel
- `score_symbol(symbol)`: Fetch and score one symbol
- `recommend(symbols)`: Fetch, score and rank many symbols concurrently (JSON cache optional)

Stock analysis includes: market valuation, profitability metrics, balance sheet data, analyst recommendations, and price performance.

When changing scoring behaviour, edit the curves in `recommender.METRIC_RULES` rather than adding special cases, keep `score_stock()` free of network calls, and add a fixture-based test in `tests/test_recommender.py`.

## Development Notes

- Tests: `unittest`, under `tests/`, fully offline (the engine is tested against fixture dicts)
- No linting or formatting configuration found
- `.stock_cache.json` is a local fetch cache and is git-ignored
- Yahoo Finance's `dividendYield` has switched between fraction and percent form across yfinance versions; `recommender.dividend_yield_fraction()` normalises it, prefer that over the raw field
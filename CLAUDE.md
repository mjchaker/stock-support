# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based stock analysis and recommendation system that focuses on TSX (Toronto Stock Exchange) listed companies. The project consists of two main modules:

- `stock_recomend.py`: Main entry point and data aggregation
- `support_handler.py`: Core stock analysis functionality via the `stock_handler` class

## Architecture

The codebase follows a simple modular design:

1. **Data Source**: Fetches TSX company symbols from `tsx.com/files/trading/interlisted-companies.txt`
2. **Data Processing**: Uses `yfinance` library to retrieve detailed stock information
3. **Analysis**: Provides comprehensive financial analysis including market cap, PE ratios, profitability metrics, and analyst recommendations
4. **Output**: Formats data for Excel export and console display

Key architectural components:
- `stock_handler` class: Central class handling all stock data operations
- External data dependencies: TSX symbol list (web), Yahoo Finance API (via yfinance)
- File I/O: Excel output for symbol lists (`tsx_symbols.xlsx`)

## Dependencies

The project uses these external libraries:
- `yfinance`: Yahoo Finance API access for stock data
- `pandas`: Data manipulation and Excel file operations  
- `requests`: HTTP requests for TSX symbol list
- `openpyxl` (implied): Excel file writing support

## Running the Code

Since this is a simple Python project without formal build tools:

```bash
# Run the main application
python stock_recomend.py

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

Stock analysis includes: market valuation, profitability metrics, balance sheet data, analyst recommendations, and price performance.

## Development Notes

- No formal testing framework detected
- No linting or formatting configuration found
- No dependency management files (requirements.txt, setup.py) present
- Consider adding these for better project structure and reproducibility
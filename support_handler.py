import pandas as pd
import yfinance as yf
from pprint import pprint
import requests
import os

import recommender

class stock_handler:
    def __init__(self):
        self.stock_symbol_list = "https://www.tsx.com/files/trading/interlisted-companies.txt"
    
    def get_all_stock_symbols(self):
        # Download the content of the file
        response = requests.get(self.stock_symbol_list)
        response.raise_for_status()  # Raise error if the request failed
        lines = response.text.splitlines()

        symbols = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith("As of") or line.startswith("Symbol"):
                continue
            parts = line.split()
            if parts:
                symbols.append(parts[0])  # First word is the TSX Symbol
        
        # Save to Excel
        cleaned_symbols = [s.split(':')[0] for s in symbols]
        return cleaned_symbols
    
    def get_all_stock(self):
        
        symbols = self.get_all_stock_symbols()
        df = pd.DataFrame({'Symbol': symbols})
        base_filename = "tsx_symbols.xlsx"
        filename = base_filename
        counter = 1
        while os.path.exists(filename):
            filename = f"tsx_symbols_{counter}.xlsx"
            counter += 1

        # Save the DataFrame to the new Excel file
        df.to_excel(filename, index=False)

        return filename
    
    def get_company_info(self, symbol):
        # Fetch data using yfinance
        company = yf.Ticker(symbol)
        info = company.info
        return info

    def score_symbol(self, symbol):
        """Fetch one symbol and return its recommender.StockScore."""
        symbol = recommender.normalize_symbol(symbol)
        try:
            info = self.get_company_info(symbol)
        except Exception as exc:
            return recommender.score_stock(symbol, None, str(exc))
        return recommender.score_stock(symbol, info)

    def recommend(self, symbols=None, workers=8, cache_path=None, progress=None):
        """Score and rank a list of symbols (default: the built-in watchlist).

        Returns a list of recommender.StockScore, best first.  Pass the
        output of get_all_stock_symbols() to scan the whole TSX.
        """
        if not symbols:
            symbols = recommender.DEFAULT_WATCHLIST
        return recommender.screen(
            symbols,
            fetcher=self.get_company_info,
            workers=workers,
            cache_path=cache_path,
            progress=progress,
        )
    
    def print_stock_info(self, stock):
        info = self.get_company_info(stock)
        print(f"========== {info.get('longName', stock)} ({stock}) ==========")
        
        try:
            # Company Overview
            print("\n📄 Company Info:")
            print(f"Sector: {info.get('sector')}")
            print(f"Industry: {info.get('industry')}")
            print(f"Website: {info.get('website')}")
            print(f"Exchange: {info.get('exchange')}")
            print(f"Description: {info.get('longBusinessSummary')[:300]}...")

            # Market & Valuation
            print("\n💰 Market & Valuation:")
            print(f"Market Cap: {info.get('marketCap'):,}")
            print(f"PE Ratio (TTM): {info.get('trailingPE')}")
            print(f"PEG Ratio (5 yr expected): {info.get('pegRatio')}")
            print(f"Price to Book: {info.get('priceToBook')}")
            print(f"Forward PE: {info.get('forwardPE')}")

            # Profitability & Margins
            print("\n📊 Profitability:")
            print(f"Return on Equity (ROE): {info.get('returnOnEquity')}")
            print(f"Return on Assets (ROA): {info.get('returnOnAssets')}")
            print(f"Profit Margin: {info.get('profitMargins')}")

            # Earnings & Revenue
            print("\n📈 Financial Performance:")
            print(f"Revenue (TTM): {info.get('totalRevenue'):,}")
            print(f"Gross Profit: {info.get('grossProfits'):,}")
            print(f"Net Income: {info.get('netIncomeToCommon'):,}")
            print(f"Quarterly Revenue Growth: {info.get('revenueQuarterlyGrowth')}")
            print(f"Quarterly Earnings Growth: {info.get('earningsQuarterlyGrowth')}")

            # Dividends
            print("\n💵 Dividends:")
            print(f"Dividend Yield: {info.get('dividendYield')}")
            print(f"Dividend Rate: {info.get('dividendRate')}")
            print(f"Payout Ratio: {info.get('payoutRatio')}")

            # Debt & Liquidity
            print("\n🏦 Balance Sheet:")
            print(f"Total Debt: {info.get('totalDebt'):,}")
            print(f"Current Ratio: {info.get('currentRatio')}")
            print(f"Debt to Equity: {info.get('debtToEquity')}")

            # Analyst Opinion
            print("\n📢 Analyst Recommendation:")
            print(f"Recommendation: {info.get('recommendationKey')}")
            print(f"Target Mean Price: {info.get('targetMeanPrice')}")
            print(f"Target High Price: {info.get('targetHighPrice')}")
            print(f"Target Low Price: {info.get('targetLowPrice')}")

            # Recent Price
            print("\n📉 Price Data:")
            print(f"Current Price: {info.get('currentPrice')}")
            print(f"52-Week High: {info.get('fiftyTwoWeekHigh')}")
            print(f"52-Week Low: {info.get('fiftyTwoWeekLow')}")
            # Verdict
            print("\n🎯 Verdict:")
            print(recommender.format_detail(recommender.score_stock(stock, info)))
        except Exception as exc:
            print(f"No Stock ({exc})")
            
    
    def analyze_etf(self, ticker):
        etf = yf.Ticker(ticker)
        info = etf.info

        print(f"\n========== {info.get('longName')} ({ticker}) ==========")
        print(f"Fund Family: {info.get('fundFamily')}")
        print(f"Category: {info.get('category')}")
        print(f"Exchange: {info.get('exchange')}")

        # Price & Performance
        print("\n📈 Price & Performance:")
        print(f"Current Price: {info.get('currentPrice')}")
        print(f"52-Week High: {info.get('fiftyTwoWeekHigh')}")
        print(f"52-Week Low: {info.get('fiftyTwoWeekLow')}")
        print(f"1y Return: {info.get('yield') * 100 if info.get('yield') else 'N/A'}%")

        # Fees
        print("\n💸 Fees & Yield:")
        print(f"Expense Ratio: {info.get('expenseRatio')}")
        print(f"Dividend Yield: {info.get('dividendYield')}")
        print(f"Annual Dividend: {info.get('dividendRate')}")

        # Risk
        print("\n⚠️ Risk & Volatility:")
        print(f"Beta: {info.get('beta')}")
        print(f"Morningstar Risk Rating: {info.get('morningStarRiskRating')}")
        print(f"Morningstar Overall Rating: {info.get('morningStarOverallRating')}")

        # AUM & Liquidity
        print("\n🏦 Fund Size & Liquidity:")
        print(f"AUM (Assets Under Management): {info.get('totalAssets')}")
        print(f"Volume: {info.get('volume')}")
        print(f"Average Volume: {info.get('averageVolume')}")
    
    def should_buy_etf(self, info):
        if info.get('expenseRatio') and info['expenseRatio'] < 0.2:
            if info.get('totalAssets') and info['totalAssets'] > 1_000_000_000:
                if info.get('morningStarOverallRating') and info['morningStarOverallRating'] >= 4:
                    print("\n✅ This ETF looks strong based on low fees, high AUM, and performance.")
                    return
        print("\n⚠️ This ETF may not meet best-in-class criteria. Investigate further.")

        
    def get_assets2liabilities(self):
        pass

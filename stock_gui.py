"""Stock Analyzer GUI Application

This module provides a comprehensive graphical user interface for analyzing TSX (Toronto Stock Exchange)
listed companies. The application allows users to search for stocks by symbol, view detailed financial
analysis, and export TSX symbol data to Excel format.

The GUI organizes stock information into four main categories:
- Company Information: Basic company details and business summary
- Market & Valuation: Market cap, price information, and valuation ratios
- Financial Performance: Profitability metrics, revenue, and balance sheet data
- Analysis & Recommendations: Analyst recommendations and dividend information

Dependencies:
    - tkinter: Standard Python GUI toolkit for the user interface
    - threading: For running stock analysis in background threads to prevent GUI freezing
    - support_handler: Custom module containing the stock_handler class for data retrieval

Usage:
    Run this file directly to launch the GUI application:
    python stock_gui.py
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
from support_handler import stock_handler


class StockAnalyzerGUI:
    """Main GUI application class for stock analysis.
    
    This class creates and manages the entire graphical user interface for the stock analyzer.
    It handles user interactions, displays stock data in organized tabs, and manages background
    data retrieval operations.
    
    Attributes:
        root (tk.Tk): The main tkinter window
        stock_handler (stock_handler): Instance of the stock data handler class
        symbol_var (tk.StringVar): Tkinter variable holding the current stock symbol
        analyze_btn (ttk.Button): Reference to the analyze button for state management
        notebook (ttk.Notebook): Tab container for organizing different data views
        Various label widgets: References to GUI labels for updating displayed information
    """
    
    def __init__(self, root):
        """Initialize the Stock Analyzer GUI.
        
        Sets up the main window, creates the stock handler instance, and initializes
        the user interface components.
        
        Args:
            root (tk.Tk): The main tkinter root window
        """
        self.root = root
        self.root.title("Stock Analyzer - TSX Companies")
        self.root.geometry("1200x800")  # Set initial window size (width x height)
        
        # Initialize the stock data handler
        self.stock_handler = stock_handler()
        
        # Set up the user interface
        self.setup_ui()
        
    def setup_ui(self):
        """Create and configure the main user interface layout.
        
        Sets up the main window structure including:
        - Main container frame with padding
        - Grid configuration for responsive resizing
        - Application title
        - Search section with input controls
        - Results section with tabbed interface
        
        The layout uses a two-column design with search controls on the left
        and results displayed in tabs on the right.
        """
        # Main container frame with padding for better appearance
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights for responsive resizing
        # These settings allow the window to resize properly
        self.root.columnconfigure(0, weight=1)  # Allow root window to expand horizontally
        self.root.rowconfigure(0, weight=1)     # Allow root window to expand vertically
        main_frame.columnconfigure(1, weight=1) # Results section expands with window
        main_frame.rowconfigure(1, weight=1)    # Main content area expands vertically
        
        # Application title at the top
        title_label = ttk.Label(main_frame, text="TSX Stock Analyzer", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 10))  # Spans both columns
        
        # Left panel: Search and control section
        search_frame = ttk.LabelFrame(main_frame, text="Stock Search", padding="10")
        search_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N), padx=(0, 5))
        
        # Stock symbol input section
        ttk.Label(search_frame, text="Enter Stock Symbol:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        # Default to a sample TSX stock symbol
        self.symbol_var = tk.StringVar(value="CEU.TO")
        symbol_entry = ttk.Entry(search_frame, textvariable=self.symbol_var, width=15)
        symbol_entry.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Main analyze button
        self.analyze_btn = ttk.Button(search_frame, text="Analyze Stock", command=self.analyze_stock)
        self.analyze_btn.grid(row=2, column=0, sticky=(tk.W, tk.E))
        
        # Quick access buttons for common stocks
        ttk.Label(search_frame, text="Quick Access:").grid(row=3, column=0, sticky=tk.W, pady=(15, 5))
        
        # Popular TSX stocks for quick analysis
        quick_stocks = ["CEU.TO", "CCO.TO", "TSAT.TO"]
        for i, stock in enumerate(quick_stocks):
            btn = ttk.Button(search_frame, text=stock, 
                           command=lambda s=stock: self.quick_analyze(s))
            btn.grid(row=4+i, column=0, sticky=(tk.W, tk.E), pady=2)
        
        # Utility button to export complete TSX symbol list
        export_btn = ttk.Button(search_frame, text="Export All TSX Symbols", 
                               command=self.export_symbols)
        export_btn.grid(row=8, column=0, sticky=(tk.W, tk.E), pady=(15, 0))
        
        # Configure search frame to resize properly
        search_frame.columnconfigure(0, weight=1)
        
        # Right panel: Results section with tabbed interface
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        
        # Create all the result tabs
        self.create_result_tabs()
        
    def create_result_tabs(self):
        """Create the tabbed interface for displaying stock analysis results.
        
        Sets up four main tabs for organizing different types of stock information:
        1. Company Info: Basic company details and business description
        2. Market & Valuation: Market capitalization, price data, and valuation ratios
        3. Financial Performance: Revenue, profitability, and balance sheet metrics
        4. Analysis & Recommendations: Analyst ratings and dividend information
        
        Each tab is created as a separate frame and added to the notebook widget.
        """
        # Company Info Tab
        self.company_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.company_frame, text="Company Info")
        
        # Market & Valuation Tab
        self.market_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.market_frame, text="Market & Valuation")
        
        # Financial Performance Tab
        self.financial_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.financial_frame, text="Financial Performance")
        
        # Analysis Tab
        self.analysis_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.analysis_frame, text="Analysis & Recommendations")
        
        # Create content areas for each tab
        self.setup_company_tab()
        self.setup_market_tab()
        self.setup_financial_tab()
        self.setup_analysis_tab()
        
    def setup_company_tab(self):
        """Configure the Company Information tab.
        
        Creates a scrollable text widget to display:
        - Company name and stock symbol
        - Sector and industry classification
        - Stock exchange information
        - Company website
        - Business summary description
        
        The text area is scrollable to accommodate varying lengths of business summaries.
        """
        # Company information display
        self.company_text = scrolledtext.ScrolledText(self.company_frame, wrap=tk.WORD, 
                                                     height=20, width=70)
        self.company_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
    def setup_market_tab(self):
        """Configure the Market & Valuation tab.
        
        Creates organized sections for different types of market data:
        
        Market Capitalization Section:
        - Total market value of the company
        
        Valuation Ratios Section:
        - P/E Ratio (Price-to-Earnings): Current price relative to earnings per share
        - PEG Ratio: P/E ratio adjusted for earnings growth rate
        - Price to Book: Market price relative to book value per share
        - Forward P/E: Expected P/E ratio based on forward earnings estimates
        
        Price Information Section:
        - Current stock price
        - 52-week high and low prices
        
        All sections use labeled frames for clear organization and visual separation.
        """
        # Market data in a structured layout
        market_container = ttk.Frame(self.market_frame)
        market_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Market Cap section
        market_cap_frame = ttk.LabelFrame(market_container, text="Market Capitalization", padding="10")
        market_cap_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.market_cap_label = ttk.Label(market_cap_frame, text="Market Cap: -", font=("Arial", 12))
        self.market_cap_label.pack(anchor=tk.W)
        
        # Ratios section
        ratios_frame = ttk.LabelFrame(market_container, text="Valuation Ratios", padding="10")
        ratios_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.pe_label = ttk.Label(ratios_frame, text="P/E Ratio (TTM): -")
        self.pe_label.pack(anchor=tk.W, pady=2)
        
        self.peg_label = ttk.Label(ratios_frame, text="PEG Ratio: -")
        self.peg_label.pack(anchor=tk.W, pady=2)
        
        self.pb_label = ttk.Label(ratios_frame, text="Price to Book: -")
        self.pb_label.pack(anchor=tk.W, pady=2)
        
        self.forward_pe_label = ttk.Label(ratios_frame, text="Forward P/E: -")
        self.forward_pe_label.pack(anchor=tk.W, pady=2)
        
        # Price section
        price_frame = ttk.LabelFrame(market_container, text="Price Information", padding="10")
        price_frame.pack(fill=tk.X)
        
        self.current_price_label = ttk.Label(price_frame, text="Current Price: -", font=("Arial", 12, "bold"))
        self.current_price_label.pack(anchor=tk.W, pady=2)
        
        self.week_high_label = ttk.Label(price_frame, text="52-Week High: -")
        self.week_high_label.pack(anchor=tk.W, pady=2)
        
        self.week_low_label = ttk.Label(price_frame, text="52-Week Low: -")
        self.week_low_label.pack(anchor=tk.W, pady=2)
        
    def setup_financial_tab(self):
        """Configure the Financial Performance tab.
        
        Creates organized sections for key financial metrics:
        
        Profitability Metrics Section:
        - ROE (Return on Equity): How effectively the company uses shareholders' equity
        - ROA (Return on Assets): How efficiently the company uses its assets
        - Profit Margin: Percentage of revenue that becomes profit
        
        Revenue & Earnings Section:
        - Revenue (TTM): Total revenue over the trailing twelve months
        - Gross Profit: Revenue minus cost of goods sold
        - Net Income: Final profit after all expenses and taxes
        
        Balance Sheet Section:
        - Total Debt: Company's total debt obligations
        - Current Ratio: Ability to pay short-term debts (current assets/current liabilities)
        - Debt to Equity: Financial leverage ratio (total debt/shareholders' equity)
        
        These metrics help assess the company's financial health and performance.
        """
        financial_container = ttk.Frame(self.financial_frame)
        financial_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Profitability section
        profit_frame = ttk.LabelFrame(financial_container, text="Profitability Metrics", padding="10")
        profit_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.roe_label = ttk.Label(profit_frame, text="Return on Equity (ROE): -")
        self.roe_label.pack(anchor=tk.W, pady=2)
        
        self.roa_label = ttk.Label(profit_frame, text="Return on Assets (ROA): -")
        self.roa_label.pack(anchor=tk.W, pady=2)
        
        self.profit_margin_label = ttk.Label(profit_frame, text="Profit Margin: -")
        self.profit_margin_label.pack(anchor=tk.W, pady=2)
        
        # Revenue & Earnings section
        revenue_frame = ttk.LabelFrame(financial_container, text="Revenue & Earnings", padding="10")
        revenue_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.revenue_label = ttk.Label(revenue_frame, text="Revenue (TTM): -")
        self.revenue_label.pack(anchor=tk.W, pady=2)
        
        self.gross_profit_label = ttk.Label(revenue_frame, text="Gross Profit: -")
        self.gross_profit_label.pack(anchor=tk.W, pady=2)
        
        self.net_income_label = ttk.Label(revenue_frame, text="Net Income: -")
        self.net_income_label.pack(anchor=tk.W, pady=2)
        
        # Balance Sheet section
        balance_frame = ttk.LabelFrame(financial_container, text="Balance Sheet", padding="10")
        balance_frame.pack(fill=tk.X)
        
        self.total_debt_label = ttk.Label(balance_frame, text="Total Debt: -")
        self.total_debt_label.pack(anchor=tk.W, pady=2)
        
        self.current_ratio_label = ttk.Label(balance_frame, text="Current Ratio: -")
        self.current_ratio_label.pack(anchor=tk.W, pady=2)
        
        self.debt_equity_label = ttk.Label(balance_frame, text="Debt to Equity: -")
        self.debt_equity_label.pack(anchor=tk.W, pady=2)
        
    def setup_analysis_tab(self):
        """Configure the Analysis & Recommendations tab.
        
        Creates sections for analyst opinions and dividend information:
        
        Analyst Recommendations Section:
        - Overall recommendation (buy, hold, sell)
        - Target Mean Price: Average analyst price target
        - Target High/Low: Range of analyst price targets
        
        Dividend Information Section:
        - Dividend Yield: Annual dividend as percentage of stock price
        - Dividend Rate: Annual dividend payment per share
        - Payout Ratio: Percentage of earnings paid as dividends
        
        This information helps investors understand professional analyst opinions
        and dividend income potential.
        """
        analysis_container = ttk.Frame(self.analysis_frame)
        analysis_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Analyst Recommendations
        analyst_frame = ttk.LabelFrame(analysis_container, text="Analyst Recommendations", padding="10")
        analyst_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.recommendation_label = ttk.Label(analyst_frame, text="Recommendation: -", font=("Arial", 12, "bold"))
        self.recommendation_label.pack(anchor=tk.W, pady=2)
        
        self.target_mean_label = ttk.Label(analyst_frame, text="Target Mean Price: -")
        self.target_mean_label.pack(anchor=tk.W, pady=2)
        
        self.target_high_label = ttk.Label(analyst_frame, text="Target High Price: -")
        self.target_high_label.pack(anchor=tk.W, pady=2)
        
        self.target_low_label = ttk.Label(analyst_frame, text="Target Low Price: -")
        self.target_low_label.pack(anchor=tk.W, pady=2)
        
        # Dividends section
        dividend_frame = ttk.LabelFrame(analysis_container, text="Dividend Information", padding="10")
        dividend_frame.pack(fill=tk.X)
        
        self.dividend_yield_label = ttk.Label(dividend_frame, text="Dividend Yield: -")
        self.dividend_yield_label.pack(anchor=tk.W, pady=2)
        
        self.dividend_rate_label = ttk.Label(dividend_frame, text="Dividend Rate: -")
        self.dividend_rate_label.pack(anchor=tk.W, pady=2)
        
        self.payout_ratio_label = ttk.Label(dividend_frame, text="Payout Ratio: -")
        self.payout_ratio_label.pack(anchor=tk.W, pady=2)
        
    def quick_analyze(self, symbol):
        """Perform quick analysis using a predefined stock symbol.
        
        This method is called by the quick access buttons to automatically
        populate the symbol field and trigger analysis.
        
        Args:
            symbol (str): The stock symbol to analyze (e.g., 'CEU.TO')
        """
        self.symbol_var.set(symbol)
        self.analyze_stock()
        
    def analyze_stock(self):
        """Initiate stock analysis for the entered symbol.
        
        This method:
        1. Validates that a stock symbol has been entered
        2. Disables the analyze button to prevent multiple simultaneous requests
        3. Starts a background thread to fetch stock data without freezing the GUI
        4. Handles any errors that occur during the validation process
        
        The actual data fetching is performed in _analyze_stock_thread() to maintain
        GUI responsiveness during network operations.
        """
        symbol = self.symbol_var.get().strip()
        if not symbol:
            messagebox.showerror("Error", "Please enter a stock symbol")
            return
            
        # Disable button during analysis
        self.analyze_btn.config(state="disabled", text="Analyzing...")
        
        # Run analysis in separate thread to prevent GUI freezing
        thread = threading.Thread(target=self._analyze_stock_thread, args=(symbol,))
        thread.daemon = True
        thread.start()
        
    def _analyze_stock_thread(self, symbol):
        """Background thread worker for fetching stock data.
        
        This method runs in a separate thread to prevent the GUI from freezing
        during network requests to fetch stock information.
        
        Args:
            symbol (str): The stock symbol to fetch data for
            
        The method fetches data using the stock_handler and then schedules
        GUI updates on the main thread using root.after() to ensure thread safety.
        Any exceptions are caught and error messages are displayed to the user.
        """
        try:
            info = self.stock_handler.get_company_info(symbol)
            # Update GUI in main thread
            self.root.after(0, self._update_display, info, symbol)
        except Exception as e:
            self.root.after(0, self._show_error, str(e))
            
    def _update_display(self, info, symbol):
        """Update the GUI with fetched stock information.
        
        This method runs on the main GUI thread and updates all the display
        elements with the stock data retrieved from the Yahoo Finance API.
        
        Args:
            info (dict): Dictionary containing stock information from yfinance
            symbol (str): The stock symbol that was analyzed
            
        The method updates all four tabs with relevant information:
        - Company tab: Basic company information and business summary
        - Market tab: Market cap, valuation ratios, and price information
        - Financial tab: Profitability metrics, revenue, and balance sheet data
        - Analysis tab: Analyst recommendations and dividend information
        
        All monetary values are formatted using helper methods for consistent display.
        The analyze button is re-enabled after the update is complete.
        """
        try:
            # Update Company Info tab
            company_info = f"""Company: {info.get('longName', 'N/A')} ({symbol})

Sector: {info.get('sector', 'N/A')}
Industry: {info.get('industry', 'N/A')}
Exchange: {info.get('exchange', 'N/A')}
Website: {info.get('website', 'N/A')}

Business Summary:
{info.get('longBusinessSummary', 'No description available')[:500]}..."""
            
            self.company_text.delete(1.0, tk.END)
            self.company_text.insert(tk.END, company_info)
            
            # Update Market & Valuation tab
            self.market_cap_label.config(text=f"Market Cap: {self._format_number(info.get('marketCap'))}")
            self.pe_label.config(text=f"P/E Ratio (TTM): {self._format_ratio(info.get('trailingPE'))}")
            self.peg_label.config(text=f"PEG Ratio: {self._format_ratio(info.get('pegRatio'))}")
            self.pb_label.config(text=f"Price to Book: {self._format_ratio(info.get('priceToBook'))}")
            self.forward_pe_label.config(text=f"Forward P/E: {self._format_ratio(info.get('forwardPE'))}")
            self.current_price_label.config(text=f"Current Price: ${self._format_price(info.get('currentPrice'))}")
            self.week_high_label.config(text=f"52-Week High: ${self._format_price(info.get('fiftyTwoWeekHigh'))}")
            self.week_low_label.config(text=f"52-Week Low: ${self._format_price(info.get('fiftyTwoWeekLow'))}")
            
            # Update Financial Performance tab
            self.roe_label.config(text=f"Return on Equity (ROE): {self._format_percent(info.get('returnOnEquity'))}")
            self.roa_label.config(text=f"Return on Assets (ROA): {self._format_percent(info.get('returnOnAssets'))}")
            self.profit_margin_label.config(text=f"Profit Margin: {self._format_percent(info.get('profitMargins'))}")
            self.revenue_label.config(text=f"Revenue (TTM): {self._format_number(info.get('totalRevenue'))}")
            self.gross_profit_label.config(text=f"Gross Profit: {self._format_number(info.get('grossProfits'))}")
            self.net_income_label.config(text=f"Net Income: {self._format_number(info.get('netIncomeToCommon'))}")
            self.total_debt_label.config(text=f"Total Debt: {self._format_number(info.get('totalDebt'))}")
            self.current_ratio_label.config(text=f"Current Ratio: {self._format_ratio(info.get('currentRatio'))}")
            self.debt_equity_label.config(text=f"Debt to Equity: {self._format_ratio(info.get('debtToEquity'))}")
            
            # Update Analysis tab
            self.recommendation_label.config(text=f"Recommendation: {info.get('recommendationKey', 'N/A').upper()}")
            self.target_mean_label.config(text=f"Target Mean Price: ${self._format_price(info.get('targetMeanPrice'))}")
            self.target_high_label.config(text=f"Target High Price: ${self._format_price(info.get('targetHighPrice'))}")
            self.target_low_label.config(text=f"Target Low Price: ${self._format_price(info.get('targetLowPrice'))}")
            self.dividend_yield_label.config(text=f"Dividend Yield: {self._format_percent(info.get('dividendYield'))}")
            self.dividend_rate_label.config(text=f"Dividend Rate: ${self._format_price(info.get('dividendRate'))}")
            self.payout_ratio_label.config(text=f"Payout Ratio: {self._format_percent(info.get('payoutRatio'))}")
            
        except Exception as e:
            self._show_error(f"Error updating display: {str(e)}")
        finally:
            # Re-enable button
            self.analyze_btn.config(state="normal", text="Analyze Stock")
            
    def _format_number(self, value):
        """Format large monetary values with appropriate unit suffixes.
        
        Converts large numbers to more readable format using standard financial abbreviations:
        - Values >= 1 billion: displayed as "$X.XXB"
        - Values >= 1 million: displayed as "$X.XXM" 
        - Values >= 1 thousand: displayed as "$X.XXK"
        - Smaller values: displayed as "$X,XXX.XX"
        
        Args:
            value (float or None): The numerical value to format
            
        Returns:
            str: Formatted string representation of the value, or "N/A" if value is None/invalid
        """
        if value is None:
            return "N/A"
        try:
            if value >= 1_000_000_000:
                return f"${value/1_000_000_000:.2f}B"
            elif value >= 1_000_000:
                return f"${value/1_000_000:.2f}M"
            elif value >= 1_000:
                return f"${value/1_000:.2f}K"
            else:
                return f"${value:,.2f}"
        except:
            return "N/A"
            
    def _format_price(self, value):
        """Format price values to two decimal places.
        
        Args:
            value (float or None): The price value to format
            
        Returns:
            str: Price formatted to 2 decimal places, or "N/A" if value is None/invalid
        """
        if value is None:
            return "N/A"
        try:
            return f"{value:.2f}"
        except:
            return "N/A"
            
    def _format_ratio(self, value):
        """Format ratio values to two decimal places.
        
        Used for financial ratios like P/E ratio, debt-to-equity ratio, etc.
        
        Args:
            value (float or None): The ratio value to format
            
        Returns:
            str: Ratio formatted to 2 decimal places, or "N/A" if value is None/invalid
        """
        if value is None:
            return "N/A"
        try:
            return f"{value:.2f}"
        except:
            return "N/A"
            
    def _format_percent(self, value):
        """Format decimal values as percentages.
        
        Converts decimal values (e.g., 0.15) to percentage format (e.g., "15.00%").
        Used for metrics like ROE, ROA, profit margins, and dividend yields.
        
        Args:
            value (float or None): The decimal value to convert to percentage
            
        Returns:
            str: Percentage formatted to 2 decimal places with % symbol, or "N/A" if value is None/invalid
        """
        if value is None:
            return "N/A"
        try:
            return f"{value*100:.2f}%"
        except:
            return "N/A"
            
    def _show_error(self, error_msg):
        """Display error messages to the user and reset the analyze button.
        
        Shows a modal error dialog with the provided error message and
        re-enables the analyze button for further attempts.
        
        Args:
            error_msg (str): The error message to display to the user
        """
        messagebox.showerror("Error", f"Failed to analyze stock: {error_msg}")
        self.analyze_btn.config(state="normal", text="Analyze Stock")
        
    def export_symbols(self):
        """Export all TSX stock symbols to an Excel file.
        
        Uses the stock_handler's get_all_stock() method to:
        1. Fetch the current list of TSX company symbols from the web
        2. Save the symbols to an Excel file (tsx_symbols.xlsx)
        3. Display a success message with the filename
        
        Any errors during the export process are caught and displayed to the user.
        This feature is useful for getting a complete list of available TSX symbols
        for further analysis or research.
        """
        try:
            filename = self.stock_handler.get_all_stock()
            messagebox.showinfo("Success", f"TSX symbols exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export symbols: {str(e)}")

def main():
    """Main entry point for the Stock Analyzer GUI application.
    
    Creates the main tkinter window, initializes the StockAnalyzerGUI class,
    and starts the GUI event loop. This function is called when the script
    is run directly.
    """
    root = tk.Tk()
    app = StockAnalyzerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
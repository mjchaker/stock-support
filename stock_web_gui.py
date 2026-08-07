"""Django Web GUI for Stock Analysis

This module provides a comprehensive web-based interface for analyzing TSX (Toronto Stock Exchange)
listed companies using the Django web framework. The application is designed as a standalone
script that can be executed directly without requiring a separate Django project setup.

The web interface mirrors the functionality of the tkinter GUI (stock_gui.py) but provides
a more modern, accessible, and mobile-friendly experience through a web browser.

Architecture:
    - Standalone Django application with embedded configuration
    - Single-file deployment with no external templates or static files
    - RESTful AJAX endpoints for dynamic data loading
    - Bootstrap CSS framework for responsive design
    - jQuery for client-side interactivity and AJAX requests

Features:
    - Real-time stock analysis with loading indicators
    - Responsive web design optimized for desktop and mobile devices
    - Four organized data sections: Company Info, Market & Valuation, Financial Performance, Analysis
    - Quick access buttons for popular TSX stocks (CEU.TO, CCO.TO, TSAT.TO)
    - Excel export functionality for complete TSX symbol lists
    - Error handling with user-friendly messages
    - No database required - all data fetched from Yahoo Finance API

Technical Implementation:
    - Django settings configured programmatically within the module
    - URL routing defined in the same file for simplicity
    - CSRF protection disabled for development (not recommended for production)
    - HTML template embedded as string for self-contained deployment
    - JavaScript formatting functions for consistent financial data display

Security Considerations:
    - Uses development-only secret key (change for production)
    - CSRF middleware not fully implemented (development only)
    - Allowed hosts restricted to localhost/127.0.0.1
    - No user authentication or session management

Dependencies:
    - Django>=3.2: Web framework for the application server
    - support_handler: Custom module containing stock_handler class for data retrieval
    - yfinance: (indirect) Via support_handler for Yahoo Finance API access
    - pandas: (indirect) Via support_handler for data manipulation

Usage:
    Basic usage:
        python stock_web_gui.py
        
    Custom host/port:
        python stock_web_gui.py runserver 0.0.0.0:8080
        
    Then open your browser to: http://127.0.0.1:8000 (or specified host:port)
    
    To stop the server, press Ctrl+C in the terminal.

API Endpoints:
    GET /: Main interface page with HTML form and results display
    POST /analyze/: AJAX endpoint for stock analysis (expects 'symbol' parameter)
    POST /export/: AJAX endpoint for TSX symbol export to Excel

Browser Compatibility:
    - Modern browsers with JavaScript enabled
    - Bootstrap 5.1.3 and jQuery 3.6.0 loaded from CDN
    - Responsive design works on mobile devices
"""

import os
import sys
import json
from io import StringIO
import django
from django.conf import settings
from django.core.management import execute_from_command_line
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.urls import path
from django.core.wsgi import get_wsgi_application
from django.template import Template, Context
from support_handler import stock_handler


# Configure Django settings programmatically
# This allows the application to run as a standalone script without requiring
# a separate Django project structure or settings.py file
if not settings.configured:
    settings.configure(
        # Enable debug mode for development (shows detailed error pages)
        DEBUG=True,
        
        # Development-only secret key (NEVER use this in production)
        SECRET_KEY='django-insecure-stock-analyzer-development-key-only',
        
        # Point to this module for URL configuration
        ROOT_URLCONF=__name__,
        
        # Restrict access to localhost only for security
        ALLOWED_HOSTS=['127.0.0.1', 'localhost'],
        
        # Minimal Django apps - only static files support needed
        INSTALLED_APPS=[
            'django.contrib.staticfiles',
        ],
        
        # Template configuration (though we use embedded HTML strings)
        TEMPLATES=[{
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [],  # No template directories needed
            'APP_DIRS': True,
            'OPTIONS': {
                'context_processors': [
                    'django.template.context_processors.debug',
                    'django.template.context_processors.request',
                ],
            },
        }],
        
        # Static files configuration (CSS, JS served from CDN)
        STATIC_URL='/static/',
        
        # Enable timezone support
        USE_TZ=True,
    )


# Initialize Django framework with the configured settings
django.setup()

# Create global stock handler instance for data retrieval
# This instance is reused across all requests for efficiency
stock_handler_instance = stock_handler()


def index(request):
    """Main page view displaying the stock analyzer interface.
    
    Renders the main HTML template with the stock analysis form and results sections.
    The page includes Bootstrap for styling and jQuery for AJAX functionality.
    
    Args:
        request: Django HTTP request object
        
    Returns:
        HttpResponse: Rendered HTML page
    """
    # HTML template embedded as string for self-contained deployment
    # This eliminates the need for separate template files
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TSX Stock Analyzer - Web Interface</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
        <style>
            /* Custom CSS for the stock analyzer interface */
            .stock-info-card { 
                margin-bottom: 20px; /* Spacing between result cards */
            }
            .loading { 
                display: none; /* Hidden by default, shown during analysis */
            }
            .error-message { 
                color: #dc3545; /* Bootstrap danger color for errors */
            }
            .success-message { 
                color: #198754; /* Bootstrap success color for confirmations */
            }
            .metric-value { 
                font-weight: bold; 
                color: #0d6efd; /* Bootstrap primary color for financial values */
            }
            .quick-btn { 
                margin: 5px; /* Spacing around quick access buttons */
            }
            #results { 
                display: none; /* Hidden until first analysis is performed */
            }
        </style>
    </head>
    <body>
        <div class="container mt-4">
            <div class="row">
                <div class="col-12">
                    <h1 class="text-center mb-4">TSX Stock Analyzer</h1>
                    <p class="text-center text-muted">Web-based interface for analyzing Toronto Stock Exchange companies</p>
                </div>
            </div>
            
            <div class="row">
                <!-- Search Panel -->
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-header">
                            <h5>Stock Search</h5>
                        </div>
                        <div class="card-body">
                            <form id="stockForm">
                                <div class="mb-3">
                                    <label for="symbol" class="form-label">Enter Stock Symbol:</label>
                                    <input type="text" class="form-control" id="symbol" value="CEU.TO" required>
                                </div>
                                <button type="submit" class="btn btn-primary w-100" id="analyzeBtn">
                                    Analyze Stock
                                </button>
                                <div class="loading text-center mt-2">
                                    <div class="spinner-border spinner-border-sm" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                    Analyzing...
                                </div>
                            </form>
                            
                            <hr>
                            
                            <h6>Quick Access:</h6>
                            <button class="btn btn-outline-secondary btn-sm quick-btn" onclick="quickAnalyze('CEU.TO')">CEU.TO</button>
                            <button class="btn btn-outline-secondary btn-sm quick-btn" onclick="quickAnalyze('CCO.TO')">CCO.TO</button>
                            <button class="btn btn-outline-secondary btn-sm quick-btn" onclick="quickAnalyze('TSAT.TO')">TSAT.TO</button>
                            
                            <hr>
                            
                            <button class="btn btn-success w-100" onclick="exportSymbols()">
                                Export All TSX Symbols
                            </button>
                            
                            <div id="messages" class="mt-3"></div>
                        </div>
                    </div>
                </div>
                
                <!-- Results Panel -->
                <div class="col-md-8">
                    <div id="results">
                        <!-- Company Information -->
                        <div class="card stock-info-card">
                            <div class="card-header">
                                <h5>Company Information</h5>
                            </div>
                            <div class="card-body" id="companyInfo">
                                <!-- Company details will be populated here -->
                            </div>
                        </div>
                        
                        <!-- Market & Valuation -->
                        <div class="card stock-info-card">
                            <div class="card-header">
                                <h5>Market & Valuation</h5>
                            </div>
                            <div class="card-body">
                                <div class="row">
                                    <div class="col-md-6">
                                        <h6>Market Capitalization</h6>
                                        <p><span class="metric-value" id="marketCap">-</span></p>
                                        
                                        <h6>Price Information</h6>
                                        <p>Current Price: <span class="metric-value" id="currentPrice">-</span></p>
                                        <p>52-Week High: <span class="metric-value" id="weekHigh">-</span></p>
                                        <p>52-Week Low: <span class="metric-value" id="weekLow">-</span></p>
                                    </div>
                                    <div class="col-md-6">
                                        <h6>Valuation Ratios</h6>
                                        <p>P/E Ratio (TTM): <span class="metric-value" id="peRatio">-</span></p>
                                        <p>PEG Ratio: <span class="metric-value" id="pegRatio">-</span></p>
                                        <p>Price to Book: <span class="metric-value" id="pbRatio">-</span></p>
                                        <p>Forward P/E: <span class="metric-value" id="forwardPE">-</span></p>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Financial Performance -->
                        <div class="card stock-info-card">
                            <div class="card-header">
                                <h5>Financial Performance</h5>
                            </div>
                            <div class="card-body">
                                <div class="row">
                                    <div class="col-md-4">
                                        <h6>Profitability Metrics</h6>
                                        <p>Return on Equity (ROE): <span class="metric-value" id="roe">-</span></p>
                                        <p>Return on Assets (ROA): <span class="metric-value" id="roa">-</span></p>
                                        <p>Profit Margin: <span class="metric-value" id="profitMargin">-</span></p>
                                    </div>
                                    <div class="col-md-4">
                                        <h6>Revenue & Earnings</h6>
                                        <p>Revenue (TTM): <span class="metric-value" id="revenue">-</span></p>
                                        <p>Gross Profit: <span class="metric-value" id="grossProfit">-</span></p>
                                        <p>Net Income: <span class="metric-value" id="netIncome">-</span></p>
                                    </div>
                                    <div class="col-md-4">
                                        <h6>Balance Sheet</h6>
                                        <p>Total Debt: <span class="metric-value" id="totalDebt">-</span></p>
                                        <p>Current Ratio: <span class="metric-value" id="currentRatio">-</span></p>
                                        <p>Debt to Equity: <span class="metric-value" id="debtEquity">-</span></p>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Analysis & Recommendations -->
                        <div class="card stock-info-card">
                            <div class="card-header">
                                <h5>Analysis & Recommendations</h5>
                            </div>
                            <div class="card-body">
                                <div class="row">
                                    <div class="col-md-6">
                                        <h6>Analyst Recommendations</h6>
                                        <p>Recommendation: <span class="metric-value" id="recommendation">-</span></p>
                                        <p>Target Mean Price: <span class="metric-value" id="targetMean">-</span></p>
                                        <p>Target High Price: <span class="metric-value" id="targetHigh">-</span></p>
                                        <p>Target Low Price: <span class="metric-value" id="targetLow">-</span></p>
                                    </div>
                                    <div class="col-md-6">
                                        <h6>Dividend Information</h6>
                                        <p>Dividend Yield: <span class="metric-value" id="dividendYield">-</span></p>
                                        <p>Dividend Rate: <span class="metric-value" id="dividendRate">-</span></p>
                                        <p>Payout Ratio: <span class="metric-value" id="payoutRatio">-</span></p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            /* JavaScript functionality for the stock analyzer web interface */
            
            // Stock analysis form handler - prevents default form submission
            // and triggers AJAX-based analysis instead
            $('#stockForm').on('submit', function(e) {
                e.preventDefault(); // Prevent page reload
                analyzeStock();
            });
            
            /**
             * Main function for analyzing a stock symbol via AJAX
             * Validates input, shows loading state, makes server request, and handles response
             */
            function analyzeStock() {
                const symbol = $('#symbol').val().trim();
                
                // Input validation
                if (!symbol) {
                    showMessage('Please enter a stock symbol', 'error');
                    return;
                }
                
                // Update UI to show loading state
                $('#analyzeBtn').prop('disabled', true);  // Prevent multiple simultaneous requests
                $('.loading').show();                     // Show spinner and loading text
                showMessage('', '');                      // Clear any previous messages
                
                // Make AJAX request to analyze endpoint
                $.ajax({
                    url: '/analyze/',
                    method: 'POST',
                    data: {
                        'symbol': symbol,
                        'csrfmiddlewaretoken': '{{ csrf_token }}'  // CSRF protection
                    },
                    success: function(data) {
                        if (data.success) {
                            // Update the display with received stock data
                            updateDisplay(data.info, symbol);
                            $('#results').show();  // Make results section visible
                            showMessage('Analysis completed successfully!', 'success');
                        } else {
                            // Server returned an error
                            showMessage('Error: ' + data.error, 'error');
                        }
                    },
                    error: function() {
                        // AJAX request failed (network error, server down, etc.)
                        showMessage('Failed to analyze stock. Please try again.', 'error');
                    },
                    complete: function() {
                        // Always executed after success or error
                        $('#analyzeBtn').prop('disabled', false);  // Re-enable button
                        $('.loading').hide();                      // Hide loading spinner
                    }
                });
            }
            
            /**
             * Quick analysis function for predefined stock symbols
             * Used by the quick access buttons to populate symbol field and trigger analysis
             * 
             * @param {string} symbol - The stock symbol to analyze (e.g., 'CEU.TO')
             */
            function quickAnalyze(symbol) {
                $('#symbol').val(symbol);  // Set the symbol input field
                analyzeStock();            // Trigger the analysis
            }
            
            /**
             * Export all TSX symbols to Excel file
             * Makes AJAX request to server to generate and save Excel file with current TSX symbols
             */
            function exportSymbols() {
                showMessage('Exporting TSX symbols...', 'info');
                
                $.ajax({
                    url: '/export/',
                    method: 'POST',
                    data: {
                        'csrfmiddlewaretoken': '{{ csrf_token }}'  // CSRF protection
                    },
                    success: function(data) {
                        if (data.success) {
                            showMessage('TSX symbols exported to ' + data.filename, 'success');
                        } else {
                            showMessage('Export failed: ' + data.error, 'error');
                        }
                    },
                    error: function() {
                        showMessage('Export failed. Please try again.', 'error');
                    }
                });
            }
            
            /**
             * Update the web interface with stock information received from the server
             * Populates all four main sections: Company Info, Market & Valuation, 
             * Financial Performance, and Analysis & Recommendations
             * 
             * @param {Object} info - Stock information object from yfinance API
             * @param {string} symbol - The stock symbol that was analyzed
             */
            function updateDisplay(info, symbol) {
                // Update company information section
                const companyHtml = `
                    <h6>${info.longName || 'N/A'} (${symbol})</h6>
                    <p><strong>Sector:</strong> ${info.sector || 'N/A'}</p>
                    <p><strong>Industry:</strong> ${info.industry || 'N/A'}</p>
                    <p><strong>Exchange:</strong> ${info.exchange || 'N/A'}</p>
                    <p><strong>Website:</strong> ${info.website ? '<a href="' + info.website + '" target="_blank">' + info.website + '</a>' : 'N/A'}</p>
                    <p><strong>Business Summary:</strong></p>
                    <p>${(info.longBusinessSummary || 'No description available').substring(0, 500)}...</p>
                `;
                $('#companyInfo').html(companyHtml);
                
                // Update market & valuation data
                $('#marketCap').text(formatNumber(info.marketCap) || 'N/A');
                $('#currentPrice').text('$' + (formatPrice(info.currentPrice) || 'N/A'));
                $('#weekHigh').text('$' + (formatPrice(info.fiftyTwoWeekHigh) || 'N/A'));
                $('#weekLow').text('$' + (formatPrice(info.fiftyTwoWeekLow) || 'N/A'));
                $('#peRatio').text(formatRatio(info.trailingPE) || 'N/A');
                $('#pegRatio').text(formatRatio(info.pegRatio) || 'N/A');
                $('#pbRatio').text(formatRatio(info.priceToBook) || 'N/A');
                $('#forwardPE').text(formatRatio(info.forwardPE) || 'N/A');
                
                // Update financial performance data
                $('#roe').text(formatPercent(info.returnOnEquity) || 'N/A');
                $('#roa').text(formatPercent(info.returnOnAssets) || 'N/A');
                $('#profitMargin').text(formatPercent(info.profitMargins) || 'N/A');
                $('#revenue').text(formatNumber(info.totalRevenue) || 'N/A');
                $('#grossProfit').text(formatNumber(info.grossProfits) || 'N/A');
                $('#netIncome').text(formatNumber(info.netIncomeToCommon) || 'N/A');
                $('#totalDebt').text(formatNumber(info.totalDebt) || 'N/A');
                $('#currentRatio').text(formatRatio(info.currentRatio) || 'N/A');
                $('#debtEquity').text(formatRatio(info.debtToEquity) || 'N/A');
                
                // Update analysis & recommendations data
                $('#recommendation').text((info.recommendationKey || 'N/A').toUpperCase());
                $('#targetMean').text('$' + (formatPrice(info.targetMeanPrice) || 'N/A'));
                $('#targetHigh').text('$' + (formatPrice(info.targetHighPrice) || 'N/A'));
                $('#targetLow').text('$' + (formatPrice(info.targetLowPrice) || 'N/A'));
                $('#dividendYield').text(formatPercent(info.dividendYield) || 'N/A');
                $('#dividendRate').text('$' + (formatPrice(info.dividendRate) || 'N/A'));
                $('#payoutRatio').text(formatPercent(info.payoutRatio) || 'N/A');
            }
            
            /* Data formatting functions for consistent display of financial values */
            
            /**
             * Format large monetary values with appropriate unit suffixes
             * Converts large numbers to readable format with B/M/K suffixes
             * 
             * @param {number|null} value - The numerical value to format
             * @returns {string|null} Formatted string or null if value is invalid
             */
            function formatNumber(value) {
                if (!value) return null;
                if (value >= 1000000000) return '$' + (value/1000000000).toFixed(2) + 'B';  // Billions
                if (value >= 1000000) return '$' + (value/1000000).toFixed(2) + 'M';       // Millions
                if (value >= 1000) return '$' + (value/1000).toFixed(2) + 'K';             // Thousands
                return '$' + value.toFixed(2);                                              // Under 1000
            }
            
            /**
             * Format price values to two decimal places
             * Used for stock prices, target prices, dividend rates, etc.
             * 
             * @param {number|null} value - The price value to format
             * @returns {string|null} Price formatted to 2 decimals or null if invalid
             */
            function formatPrice(value) {
                if (!value) return null;
                return value.toFixed(2);
            }
            
            /**
             * Format ratio values to two decimal places
             * Used for financial ratios like P/E, debt-to-equity, current ratio, etc.
             * 
             * @param {number|null} value - The ratio value to format
             * @returns {string|null} Ratio formatted to 2 decimals or null if invalid
             */
            function formatRatio(value) {
                if (!value) return null;
                return value.toFixed(2);
            }
            
            /**
             * Format decimal values as percentages
             * Converts decimal values (e.g., 0.15) to percentage format (e.g., "15.00%")
             * Used for ROE, ROA, profit margins, dividend yields, etc.
             * 
             * @param {number|null} value - The decimal value to convert to percentage
             * @returns {string|null} Percentage formatted with % symbol or null if invalid
             */
            function formatPercent(value) {
                if (!value) return null;
                return (value * 100).toFixed(2) + '%';
            }
            
            /**
             * Display status messages to the user
             * Shows success, error, or info messages in the designated message area
             * 
             * @param {string} message - The message text to display (empty string clears messages)
             * @param {string} type - Message type: 'success', 'error', 'info', or empty
             */
            function showMessage(message, type) {
                const messageDiv = $('#messages');
                
                // Clear messages if no message provided
                if (!message) {
                    messageDiv.html('');
                    return;
                }
                
                // Determine CSS class based on message type
                let className = '';
                switch(type) {
                    case 'success': className = 'success-message'; break;  // Green text
                    case 'error': className = 'error-message'; break;      // Red text
                    case 'info': className = 'text-info'; break;           // Blue text
                    default: className = ''; break;                        // Default styling
                }
                
                // Display the message with appropriate styling
                messageDiv.html('<div class="' + className + '">' + message + '</div>');
            }
        </script>
    </body>
    </html>
    """
    
    return HttpResponse(html_template)


def analyze_stock(request):
    """AJAX endpoint for stock analysis.
    
    Handles POST requests to analyze a specific stock symbol using the stock_handler.
    Returns JSON response with stock information or error message.
    
    Args:
        request: Django HTTP request object containing stock symbol
        
    Returns:
        JsonResponse: JSON containing success status and stock data or error message
    """
    if request.method == 'POST':
        symbol = request.POST.get('symbol', '').strip()
        
        if not symbol:
            return JsonResponse({
                'success': False,
                'error': 'Please provide a stock symbol'
            })
        
        try:
            # Get stock information using the stock handler
            info = stock_handler_instance.get_company_info(symbol)
            
            return JsonResponse({
                'success': True,
                'info': info,
                'symbol': symbol
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


def export_symbols(request):
    """AJAX endpoint for exporting TSX symbols.
    
    Handles POST requests to export all TSX symbols to Excel file using the stock_handler.
    Returns JSON response with success status and filename or error message.
    
    Args:
        request: Django HTTP request object
        
    Returns:
        JsonResponse: JSON containing success status and filename or error message
    """
    if request.method == 'POST':
        try:
            # Export symbols using the stock handler
            filename = stock_handler_instance.get_all_stock()
            
            return JsonResponse({
                'success': True,
                'filename': filename
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


# URL patterns
urlpatterns = [
    path('', index, name='index'),
    path('analyze/', analyze_stock, name='analyze'),
    path('export/', export_symbols, name='export'),
]


def main():
    """Main entry point for the Django web application.
    
    Sets up the Django environment and starts the development server.
    The application will be available at http://127.0.0.1:8000
    
    Usage:
        python stock_web_gui.py
        python stock_web_gui.py runserver 0.0.0.0:8080  # Custom host/port
    """
    print("=" * 60)
    print("TSX Stock Analyzer - Django Web Interface")
    print("=" * 60)
    print("Starting Django development server...")
    print("Open your browser to: http://127.0.0.1:8000")
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    
    # Set up command line arguments
    if len(sys.argv) == 1:
        sys.argv.append('runserver')
    
    # Execute Django management command
    try:
        execute_from_command_line(sys.argv)
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)


if __name__ == '__main__':
    main()
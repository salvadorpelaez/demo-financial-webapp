from flask import Flask, render_template, request, jsonify, send_from_directory
import sqlite3
import yfinance as yf
import pandas as pd
import requests
import os
import threading
from datetime import datetime
import time
from technical_indicators import indicators_bp
from supabase import create_client
from agents.router import run_valuation
from dotenv import load_dotenv

load_dotenv()

# Supabase client
_supabase_url = os.getenv("SUPABASE_URL")
_supabase_key = os.getenv("SUPABASE_KEY")
supabase_client = create_client(_supabase_url, _supabase_key) if _supabase_url and _supabase_key else None

app = Flask(__name__)

# Register technical indicators blueprint
app.register_blueprint(indicators_bp)

# Add Alpha Vantage API key - Replace with your actual API key
# Get free key from: https://www.alphavantage.co/support/#api-key
ALPHA_VANTAGE_API_KEY = os.environ.get('ALPHA_VANTAGE_API_KEY', 'demo')  # Use 'demo' for testing

DB_PATH = os.path.join(os.path.dirname(__file__), "S&P500_Master.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH,
                          timeout=10.0,  # Increase timeout to 10 seconds
                          isolation_level='DEFERRED')  # Use deferred isolation for better concurrency
    conn.row_factory = sqlite3.Row
    
    # Enable WAL mode for better concurrent access
    conn.execute("PRAGMA journal_mode=WAL")
    # Set busy timeout to handle locks gracefully
    conn.execute("PRAGMA busy_timeout=15000")  # 15 seconds
    # Optimize for single-user access
    conn.execute("PRAGMA synchronous=NORMAL")
    # Set cache size for better performance
    conn.execute("PRAGMA cache_size=10000")
    
    return conn

def get_search_connection():
    """Get a dedicated connection for search operations"""
    conn = sqlite3.connect(r"c:\Users\salva\CascadeProjects\sp500-database-webapp\database\search_cache.db", 
                          timeout=5.0,  # Shorter timeout for search
                          isolation_level='DEFERRED')  # Use deferred isolation
    conn.row_factory = sqlite3.Row
    
    # Optimized settings for read-heavy search operations
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")  # 5 seconds
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=5000")
    conn.execute("PRAGMA temp_store=MEMORY")  # Use memory for temp tables
    
    return conn

def get_stock_details(cursor, ticker):
    """Get stock details from NYSE, NASDAQ, or Companies table"""
    # Try NYSE first
    cursor.execute("SELECT Ticker, Company_Name, 'NYSE' as exchange FROM NYSE WHERE Ticker = ?", (ticker,))
    result = cursor.fetchone()
    if result:
        return {'ticker': result['Ticker'], 'name': result['Company_Name'], 'exchange': result['exchange']}
    
    # Try NASDAQ
    cursor.execute("SELECT Symbol, CompanyName, 'NASDAQ' as exchange FROM NASDAQ WHERE Symbol = ?", (ticker,))
    result = cursor.fetchone()
    if result:
        return {'ticker': result['Symbol'], 'name': result['CompanyName'], 'exchange': result['exchange']}
    
    # Try Companies (S&P 500)
    cursor.execute("SELECT Ticker, Name, 'S&P 500' as exchange FROM Companies WHERE Ticker = ?", (ticker,))
    result = cursor.fetchone()
    if result:
        return {'ticker': result['Ticker'], 'name': result['Name'], 'exchange': result['exchange']}
    
    return {'ticker': ticker, 'name': 'Unknown', 'exchange': 'Unknown'}

def execute_with_retry(cursor, query, params=None, max_retries=5):
    """Execute database query with retry logic for handling locks"""
    for attempt in range(max_retries):
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return  # Success, exit retry loop
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                print(f"Database locked, retrying... (attempt {attempt + 1}/{max_retries})")
                time.sleep(0.2 * (attempt + 1))  # More aggressive backoff
                continue
            else:
                raise  # Re-raise the error if max retries reached or different error

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/sp500')
def sp500_page():
    # This will serve the valsp500mainpage_v1.0.11 content
    # For now, we'll create a template for the S&P 500 page
    return render_template('sp500.html')

@app.route('/index-selector')
def index_selector_page():
    # This will serve the valmainpage_v1.0.11 index page as index selector
    return render_template('index_selector.html')

@app.route('/test')
def test_page():
    return render_template('test_classification.html')

@app.route('/api/market-data')
def get_market_data():
    try:
        # Define order: US first, then European at bottom
        ordered_indices = [
            ("S&P 500", "^GSPC"),
            ("NASDAQ", "^IXIC"),
            ("Dow Jones", "^DJI"),
            ("10Y Treasury", "^TNX"),
            ("Crude Oil", "CL=F"),
            ("Nikkei 225", "^N225"),
            ("Hang Seng", "^HSI"),
            ("ASX 200", "^AXJO"),
            ("CAC 40", "^FCHI"),
            ("FTSE 100", "^FTSE"), 
            ("DAX", "^GDAXI")
        ]
        
        # Get all indices using yfinance (supports European markets)
        all_tickers = [symbol for name, symbol in ordered_indices]
        data = yf.download(all_tickers, period='2d', interval='1d')
        
        ticker_names = {
            '^DJI': 'Dow Jones',
            '^GSPC': 'S&P 500', 
            '^IXIC': 'NASDAQ',
            '^TNX': '10Y Treasury',
            'CL=F': 'Crude Oil',
            '^N225': 'Nikkei 225',
            '^HSI': 'Hang Seng',
            '^AXJO': 'ASX 200',
            '^FCHI': 'CAC 40',
            '^FTSE': 'FTSE 100',
            '^GDAXI': 'DAX'
        }
        
        latest_data = {}
        
        for name, symbol in ordered_indices:
            try:
                if symbol in data['Close'].columns:
                    close_prices = data['Close'][symbol].dropna()
                    if len(close_prices) == 0:
                        continue
                        
                    latest_price = close_prices.iloc[-1]
                    
                    # Get previous price for change calculation
                    if len(close_prices) > 1:
                        previous_price = close_prices.iloc[-2]
                    else:
                        # If no previous data, use open price
                        if symbol in data['Open'].columns:
                            open_prices = data['Open'][symbol].dropna()
                            if len(open_prices) > 0:
                                previous_price = open_prices.iloc[-1]
                            else:
                                previous_price = latest_price
                        else:
                            previous_price = latest_price
                    
                    # Handle NaN values
                    if pd.isna(latest_price) or pd.isna(previous_price) or previous_price == 0:
                        latest_price = 0  # Default to 0 if no data
                        previous_price = 0
                        change = 0
                        change_percent = 0
                    else:
                        change = latest_price - previous_price
                        change_percent = (change / previous_price * 100)
                    
                    latest_data[symbol] = {
                        'name': name,
                        'price': round(float(latest_price), 2) if latest_price != 0 else 'N/A',
                        'change': round(float(change), 2),
                        'change_percent': round(float(change_percent), 2)
                    }
                else:
                    # If ticker not found, add placeholder
                    latest_data[symbol] = {
                        'name': name,
                        'price': 'N/A',
                        'change': 0,
                        'change_percent': 0
                    }
            except Exception as ticker_error:
                # Add placeholder for failed ticker
                latest_data[symbol] = {
                    'name': name,
                    'price': 'Error',
                    'change': 0,
                    'change_percent': 0
                }
        
        # Create ordered response based on the defined order
        ordered_data = {}
        for name, symbol in ordered_indices:
            if symbol in latest_data:
                ordered_data[symbol] = latest_data[symbol]
        
        return jsonify({'data': ordered_data})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/main')
def main_page():
    return render_template('main.html')

@app.route('/technical_indicators')
def technical_indicators():
    return render_template('technical_indicators.html')

@app.route('/feature2')
def feature2():
    return render_template('feature2.html')

@app.route('/feature3')
def feature3():
    return render_template('feature3.html')

@app.route('/api/companies')
def get_companies():
    conn = get_db_connection()
    try:
        # Try to get table names first
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        if not tables:
            return jsonify({'error': 'No tables found in database'})
        
        # Explicitly use the Companies table
        cursor.execute("SELECT Ticker, Name, Sector, Sub_Sector, Classification FROM Companies")
        companies = cursor.fetchall()
        
        # Convert to list of dictionaries with specific column order
        companies_list = []
        for company in companies:
            classification = company['Classification'] if company['Classification'] else ''
            # Convert to Title Case for display
            if classification:
                classification = classification.title()
            
            companies_list.append({
                'ticker': company['Ticker'],
                'name': company['Name'], 
                'sector': company['Sector'],
                'sub_sector': company['Sub_Sector'],
                'classification': classification
            })
        
        return jsonify({
            'companies': companies_list,
            'total_count': len(companies_list)
        })
    except Exception as e:
        return jsonify({'error': str(e)})
    finally:
        conn.close()

@app.route('/api/sectors')
def get_sectors():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT Sector FROM Companies ORDER BY Sector")
        sectors = [row[0] for row in cursor.fetchall()]
        return jsonify({'sectors': sectors})
    except Exception as e:
        return jsonify({'error': str(e)})
    finally:
        conn.close()

@app.route('/api/subsectors')
def get_subsectors():
    sector = request.args.get('sector', '')
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if sector:
            cursor.execute("SELECT DISTINCT Sub_Sector FROM Companies WHERE Sector = ? ORDER BY Sub_Sector", (sector,))
        else:
            cursor.execute("SELECT DISTINCT Sub_Sector FROM Companies ORDER BY Sub_Sector")
        subsectors = [row[0] for row in cursor.fetchall()]
        return jsonify({'subsectors': subsectors})
    except Exception as e:
        return jsonify({'error': str(e)})
    finally:
        conn.close()

@app.route('/api/filter')
def filter_companies():
    sector = request.args.get('sector', '')
    sub_sector = request.args.get('sub_sector', '')
    classification = request.args.get('classification', '')
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Build query based on filters using Companies table directly
        query = "SELECT Ticker, Name, Sector, Sub_Sector, Classification FROM Companies WHERE 1=1"
        params = []
        
        if sector:
            query += " AND Sector = ?"
            params.append(sector)
        
        if sub_sector:
            query += " AND Sub_Sector = ?"
            params.append(sub_sector)
        
        if classification:
            # Convert Title Case back to original format for database query
            original_classification = classification.upper()
            query += " AND Classification = ?"
            params.append(original_classification)
        
        query += " ORDER BY Name"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        # Convert to list of dictionaries with Title Case conversion
        companies_list = []
        for result in results:
            classification = result['Classification'] if result['Classification'] else ''
            # Convert to Title Case for display
            if classification:
                classification = classification.title()
            
            companies_list.append({
                'ticker': result['Ticker'],
                'name': result['Name'],
                'sector': result['Sector'],
                'sub_sector': result['Sub_Sector'],
                'classification': classification
            })
        
        return jsonify({
            'companies': companies_list,
            'total_count': len(companies_list)
        })
    except Exception as e:
        print(f"ERROR in filter: {e}")
        return jsonify({'error': str(e)})
    finally:
        conn.close()

@app.route('/api/search')
def search_companies():
    query = request.args.get('q', '').lower()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        if not tables:
            return jsonify({'error': 'No tables found in database'})
        
        table_name = tables[0]['name']
        
        # Get column names for dynamic search
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        column_names = [col['name'] for col in columns]
        
        # Build search query with specific columns
        search_query = f"""
            SELECT c.Ticker, c.Name, c.Sector, c.Sub_Sector, 
                   COALESCE(s.Classification, '') as Classification
            FROM {table_name} c 
            LEFT JOIN Staging_Updates s ON c.Ticker = s.Ticker
            WHERE LOWER(c.Ticker) LIKE ? OR LOWER(c.Name) LIKE ? OR LOWER(c.Sector) LIKE ? 
                  OR LOWER(c.Sub_Sector) LIKE ? OR COALESCE(s.Classification, '') LIKE ?
        """
        search_params = [f'%{query}%'] * 5
        
        cursor.execute(search_query, search_params)
        results = cursor.fetchall()
        
        # Convert to list of dictionaries with specific column order
        companies_list = []
        for result in results:
            companies_list.append({
                'ticker': result['Ticker'],
                'name': result['Name'],
                'sector': result['Sector'], 
                'sub_sector': result['Sub_Sector'],
                'classification': result['Classification'] if result['Classification'] else ''
            })
        
        return jsonify({
            'companies': companies_list,
            'query': query,
            'total_count': len(results)
        })
    except Exception as e:
        return jsonify({'error': str(e)})
    finally:
        conn.close()

@app.route('/api/columns')
def get_columns():
    """Get available column classifications"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Get distinct classification values from Companies table
        cursor.execute("SELECT DISTINCT Classification FROM Companies WHERE Classification IS NOT NULL AND Classification != '' ORDER BY Classification")
        classifications = cursor.fetchall()
        
        classification_list = []
        
        for cls in classifications:
            if cls['Classification'] and cls['Classification'].strip():
                # Convert to Title Case for display
                display_value = cls['Classification'].strip().title()
                classification_list.append({
                    'value': display_value,  # Use Title Case for both value and label
                    'label': display_value
                })
        
        # If no classifications found, provide default values
        if not classification_list:
            classification_list = [
                {'value': 'Value', 'label': 'Value'},
                {'value': 'Borderline', 'label': 'Borderline'},
                {'value': 'Hypergrowth', 'label': 'Hypergrowth'},
                {'value': 'Flag', 'label': 'Flag'}
            ]
        
        return jsonify({'columns': classification_list})
            
    except Exception as e:
        print(f"Error in /api/columns: {e}")
        # Fallback on error
        classification_list = [
            {'value': 'Value', 'label': 'Value'},
            {'value': 'Borderline', 'label': 'Borderline'},
            {'value': 'Hypergrowth', 'label': 'Hypergrowth'},
            {'value': 'Flag', 'label': 'Flag'}
        ]
        return jsonify({'columns': classification_list})
    finally:
        conn.close()

@app.route('/api/all-stocks')
def get_all_stocks():
    """Get all stocks from all exchanges (Companies, NASDAQ, NYSE)"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        all_stocks = []
        
        # Get S&P 500 companies
        cursor.execute("""
            SELECT Symbol as ticker, CompanyName as name, 'S&P 500' as exchange, 
                   COALESCE(Sector, 'N/A') as sector
            FROM Companies 
            WHERE Symbol IS NOT NULL AND CompanyName IS NOT NULL
            ORDER BY Symbol
        """)
        sp500_stocks = cursor.fetchall()
        for stock in sp500_stocks:
            all_stocks.append({
                'ticker': stock[0],
                'name': stock[1],
                'exchange': stock[2],
                'sector': stock[3]
            })
        
        # Get NASDAQ stocks
        cursor.execute("""
            SELECT Symbol as ticker, CompanyName as name, 'NASDAQ' as exchange,
                   COALESCE(Sector, 'N/A') as sector
            FROM NASDAQ 
            WHERE Symbol IS NOT NULL AND CompanyName IS NOT NULL
            ORDER BY Symbol
        """)
        nasdaq_stocks = cursor.fetchall()
        for stock in nasdaq_stocks:
            all_stocks.append({
                'ticker': stock[0],
                'name': stock[1],
                'exchange': stock[2],
                'sector': stock[3]
            })
        
        # Get NYSE stocks
        cursor.execute("""
            SELECT Ticker as ticker, Company_Name as name, 'NYSE' as exchange,
                   COALESCE(Sector, 'N/A') as sector
            FROM NYSE 
            WHERE Ticker IS NOT NULL AND Company_Name IS NOT NULL
            ORDER BY Ticker
        """)
        nyse_stocks = cursor.fetchall()
        for stock in nyse_stocks:
            all_stocks.append({
                'ticker': stock[0],
                'name': stock[1],
                'exchange': stock[2],
                'sector': stock[3]
            })
        
        return jsonify(all_stocks)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/search-stock')
def search_stock():
    """Search for stocks in NASDAQ and NYSE tables, then fetch current price from yfinance"""
    query = request.args.get('query', '').strip()
    
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400
    
    conn = None
    try:
        conn = get_search_connection()  # Use dedicated search connection
        cursor = conn.cursor()
        results = []
        
        # Search NASDAQ table
        execute_with_retry(cursor, """
            SELECT ticker, name, 'NASDAQ' as exchange
            FROM nasdaq_search 
            WHERE UPPER(ticker) LIKE UPPER(?) OR UPPER(name) LIKE UPPER(?)
            ORDER BY 
                CASE 
                    WHEN UPPER(ticker) = UPPER(?) THEN 1
                    WHEN UPPER(name) LIKE UPPER(?) THEN 2
                    ELSE 3
                END
            LIMIT 10
        """, (f'%{query}%', f'%{query}%', query, f'%{query}%'))
        
        nasdaq_results = cursor.fetchall()
        for row in nasdaq_results:
            results.append({
                'ticker': row[0],
                'name': row[1],
                'exchange': row[2]
            })
        
        # Also search NYSE table (not conditional)
        execute_with_retry(cursor, """
            SELECT ticker, name, 'NYSE' as exchange
            FROM nyse_search 
            WHERE UPPER(ticker) LIKE UPPER(?) OR UPPER(name) LIKE UPPER(?)
            ORDER BY 
                CASE 
                    WHEN UPPER(ticker) = UPPER(?) THEN 1
                    WHEN UPPER(name) LIKE UPPER(?) THEN 2
                    ELSE 3
                END
            LIMIT 10
        """, (f'%{query}%', f'%{query}%', query, f'%{query}%'))
        
        nyse_results = cursor.fetchall()
        for row in nyse_results:
            results.append({
                'ticker': row[0],
                'name': row[1],
                'exchange': row[2]
            })
        
        # Also search Companies table (S&P 500)
        execute_with_retry(cursor, """
            SELECT ticker, name, 'S&P 500' as exchange
            FROM companies_search 
            WHERE UPPER(ticker) LIKE UPPER(?) OR UPPER(name) LIKE UPPER(?)
            ORDER BY 
                CASE 
                    WHEN UPPER(ticker) = UPPER(?) THEN 1
                    WHEN UPPER(name) LIKE UPPER(?) THEN 2
                    ELSE 3
                END
            LIMIT 10
        """, (f'%{query}%', f'%{query}%', query, f'%{query}%'))
        
        sp500_results = cursor.fetchall()
        for row in sp500_results:
            results.append({
                'ticker': row[0],
                'name': row[1],
                'exchange': row[2]
            })
        
        # Return results immediately without waiting for yfinance prices
        # Stock prices will be fetched on the frontend asynchronously
        return jsonify(results)
        
    except Exception as e:
        print(f"Error in search: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/stock-prices')
def get_stock_prices():
    """Get stock prices for multiple tickers asynchronously"""
    tickers = request.args.get('tickers', '').split(',')
    tickers = [t.strip() for t in tickers if t.strip()]

    if not tickers:
        return jsonify({'error': 'No tickers provided'}), 400

    prices = {}
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period='2d')
            if not hist.empty and len(hist) >= 1:
                current_price = float(hist['Close'].iloc[-1])
                previous_close = float(hist['Close'].iloc[-2]) if len(hist) >= 2 else current_price
                change = current_price - previous_close
                change_percent = (change / previous_close * 100) if previous_close != 0 else 0
                prices[ticker] = {
                    'price': round(current_price, 2),
                    'change': round(change, 2),
                    'change_percent': round(change_percent, 2)
                }
            else:
                prices[ticker] = {'price': 'N/A', 'change': 0, 'change_percent': 0}
        except Exception:
            prices[ticker] = {'price': 'N/A', 'change': 0, 'change_percent': 0}

    return jsonify(prices)

@app.route('/api/stock-prices-legacy')
def get_stock_prices_legacy():
    """Legacy endpoint kept for compatibility"""
    tickers = request.args.get('tickers', '').split(',')
    tickers = [t.strip() for t in tickers if t.strip()]

    if not tickers:
        return jsonify({'error': 'No tickers provided'}), 400

    try:
        prices = {}
        for ticker in tickers:
            prices[ticker] = {
                    'price': 'N/A',
                    'change': 0,
                    'change_percent': 0
                }
        
        return jsonify(prices)
        
    except Exception as e:
        print(f"Error fetching stock prices: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/add-to-portfolio', methods=['POST'])
def add_to_portfolio():
    """Add a stock to the test_user's portfolio in database"""
    data = request.get_json()
    
    if not data or 'ticker' not in data:
        return jsonify({'error': 'Ticker is required'}), 400
    
    ticker = data['ticker']
    name = data['name']
    exchange = data['exchange']
    price = data.get('price', 0)
    change = data.get('change', 0)
    change_percent = data.get('change_percent', 0)
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get test_user ID
        cursor.execute("SELECT id FROM users WHERE username = 'test_user'")
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'error': 'Test user not found'}), 404
        
        user_id = user['id']
        
        # Check if stock already exists in user's portfolio
        cursor.execute("SELECT ticker FROM portfolio WHERE user_id = ? AND ticker = ?", (user_id, ticker))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing stock (update timestamp and shares if needed)
            cursor.execute('''
                UPDATE portfolio 
                SET added_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND ticker = ?
            ''', (user_id, ticker))
            message = f"{ticker} updated in portfolio"
        else:
            # Insert new stock
            cursor.execute('''
                INSERT INTO portfolio (user_id, ticker, shares)
                VALUES (?, ?, 1.0)
            ''', (user_id, ticker))
            message = f"{ticker} added to portfolio"
        
        conn.commit()
        
        # Get updated portfolio for test_user
        cursor.execute('''
            SELECT ticker, shares, added_at
            FROM portfolio
            WHERE user_id = ?
            ORDER BY added_at DESC
        ''', (user_id,))
        portfolio = cursor.fetchall()
        
        # Convert to list of dictionaries and fetch stock info from original tables
        portfolio_list = []
        for stock in portfolio:
            # Get stock details from the appropriate table
            stock_details = get_stock_details(cursor, stock['ticker'])
            
            portfolio_list.append({
                'ticker': stock['ticker'],
                'name': stock_details.get('name', 'Unknown'),
                'exchange': stock_details.get('exchange', 'Unknown'),
                'price': stock_details.get('price', 0),
                'change': stock_details.get('change', 0),
                'change_percent': stock_details.get('change_percent', 0),
                'added_at': stock['added_at']
            })
        
        return jsonify({
            'success': True,
            'message': message,
            'portfolio': portfolio_list,
            'size': len(portfolio_list)
        })
        
    except Exception as e:
        print(f"Error adding to portfolio: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/get-portfolio')
def get_portfolio():
    """Get the test_user's portfolio from database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get test_user ID
        cursor.execute("SELECT id FROM users WHERE username = 'test_user'")
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'portfolio': [], 'size': 0})
        
        user_id = user['id']
        
        cursor.execute('''
            SELECT ticker, shares, added_at
            FROM portfolio
            WHERE user_id = ?
            ORDER BY added_at DESC
        ''', (user_id,))
        portfolio = cursor.fetchall()
        
        # Convert to list of dictionaries and fetch stock info from original tables
        portfolio_list = []
        for stock in portfolio:
            # Get stock details from the appropriate table
            stock_details = get_stock_details(cursor, stock['ticker'])
            
            portfolio_list.append({
                'ticker': stock['ticker'],
                'name': stock_details.get('name', 'Unknown'),
                'exchange': stock_details.get('exchange', 'Unknown'),
                'price': stock_details.get('price', 0),
                'change': stock_details.get('change', 0),
                'change_percent': stock_details.get('change_percent', 0),
                'added_at': stock['added_at']
            })
        
        conn.close()
        
        return jsonify({
            'portfolio': portfolio_list,
            'size': len(portfolio_list)
        })
        
    except Exception as e:
        print(f"Error getting portfolio: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/remove-from-portfolio', methods=['DELETE'])
def remove_from_portfolio():
    """Remove a stock from the test_user's portfolio in database"""
    data = request.get_json()
    
    if not data or 'ticker' not in data:
        return jsonify({'error': 'Ticker is required'}), 400
    
    ticker = data['ticker']
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get test_user ID
        execute_with_retry(cursor, "SELECT id FROM users WHERE username = 'test_user'")
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'error': 'Test user not found'}), 404
        
        user_id = user['id']
        
        # Check if stock exists in user's portfolio
        execute_with_retry(cursor, "SELECT ticker FROM portfolio WHERE user_id = ? AND ticker = ?", (user_id, ticker))
        existing = cursor.fetchone()
        
        if not existing:
            return jsonify({'error': 'Stock not found in portfolio'}), 404
        
        # Remove the stock
        execute_with_retry(cursor, "DELETE FROM portfolio WHERE user_id = ? AND ticker = ?", (user_id, ticker))
        conn.commit()
        
        # Get updated portfolio for test_user
        execute_with_retry(cursor, '''
            SELECT ticker, shares, added_at
            FROM portfolio
            WHERE user_id = ?
            ORDER BY added_at DESC
        ''', (user_id,))
        portfolio = cursor.fetchall()
        
        # Convert to list of dictionaries and fetch stock info from original tables
        portfolio_list = []
        for stock in portfolio:
            # Get stock details from the appropriate table
            stock_details = get_stock_details(cursor, stock['ticker'])
            
            portfolio_list.append({
                'ticker': stock['ticker'],
                'name': stock_details.get('name', 'Unknown'),
                'exchange': stock_details.get('exchange', 'Unknown'),
                'price': stock_details.get('price', 0),
                'change': stock_details.get('change', 0),
                'change_percent': stock_details.get('change_percent', 0),
                'added_at': stock['added_at']
            })
        
        return jsonify({
            'success': True,
            'message': f"{ticker} removed from portfolio",
            'portfolio': portfolio_list,
            'portfolio_size': len(portfolio_list)
        })
        
    except Exception as e:
        print(f"Error removing from portfolio: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/stock-graph')
def stock_graph():
    """Display stock graph page"""
    ticker = request.args.get('ticker', '')
    name = request.args.get('name', '')
    exchange = request.args.get('exchange', '')
    
    return render_template('stock_graph.html', ticker=ticker, name=name, exchange=exchange)

@app.route('/api/stock-data')
def get_stock_data():
    """Get stock data for graph display"""
    ticker = request.args.get('ticker', '').strip()
    timeframe = request.args.get('timeframe', '1w')
    
    if not ticker:
        return jsonify({'error': 'Ticker parameter is required'}), 400
    
    try:
        import yfinance as yf
        
        # Map timeframe to yfinance period
        period_map = {
            '1d': '1d',
            '1w': '5d',    # 5 trading days for 1 week
            '1m': '1mo',
            '3m': '3mo',
            '1y': '1y'
        }
        
        period = period_map.get(timeframe, '5d')
        
        # Fetch stock data
        stock = yf.Ticker(ticker)
        
        # Get historical data
        hist = stock.history(period=period, interval='1d')
        
        if hist.empty:
            return jsonify({'error': 'No data found for this ticker'}), 404
        
        # Get current price info
        current_data = stock.history(period='2d', interval='1d')
        
        if len(current_data) < 2:
            prev_close = current_data['Close'].iloc[-1]
        else:
            prev_close = current_data['Close'].iloc[-2]
        
        current_price = current_data['Close'].iloc[-1]
        change = current_price - prev_close
        change_percent = (change / prev_close) * 100 if prev_close != 0 else 0
        
        # Prepare data for chart
        labels = []
        prices = []
        
        for date, row in hist.iterrows():
            labels.append(date.strftime('%Y-%m-%d'))
            prices.append(float(row['Close']))
        
        # Get volume
        volume = current_data['Volume'].iloc[-1] if not current_data.empty else None
        
        return jsonify({
            'ticker': ticker,
            'current_price': float(current_price),
            'change': float(change),
            'change_percent': float(change_percent),
            'volume': int(volume) if volume else None,
            'labels': labels,
            'prices': prices
        })
        
    except Exception as e:
        print(f"Error fetching stock data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/portfolio')
def portfolio_page():
    return render_template('portfolio.html')


@app.route('/api/investable-stocks')
def get_investable_stocks():
    """Get VALUE and HYPERGROWTH stocks from the Companies table"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT Ticker, Name, Sector, Sub_Sector, Classification, Primary_Reason
            FROM Companies
            WHERE Classification IN ('VALUE', 'HYPERGROWTH')
            ORDER BY Classification, Name
        """)
        rows = cursor.fetchall()
        stocks = [{
            'ticker': r['Ticker'],
            'name': r['Name'],
            'sector': r['Sector'],
            'sub_sector': r['Sub_Sector'],
            'classification': r['Classification'],
            'primary_reason': r['Primary_Reason']
        } for r in rows]
        return jsonify({'stocks': stocks, 'total': len(stocks)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/supabase-portfolio', methods=['GET'])
def get_supabase_portfolio():
    if not supabase_client:
        return jsonify({'error': 'Supabase not configured'}), 500
    try:
        result = supabase_client.table('portfolio').select('*').order('created_at', desc=True).execute()
        return jsonify({'portfolio': result.data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/supabase-portfolio/add', methods=['POST'])
def add_to_supabase_portfolio():
    if not supabase_client:
        return jsonify({'error': 'Supabase not configured'}), 500
    data = request.get_json()
    ticker = data.get('ticker')
    if not ticker:
        return jsonify({'error': 'Ticker required'}), 400
    try:
        existing = supabase_client.table('portfolio').select('id').eq('ticker', ticker).execute()
        if existing.data:
            return jsonify({'message': f'{ticker} already in portfolio'})
        supabase_client.table('portfolio').insert({
            'ticker': data.get('ticker'),
            'name': data.get('name'),
            'sector': data.get('sector'),
            'classification': data.get('classification'),
            'primary_reason': data.get('primary_reason')
        }).execute()
        return jsonify({'success': True, 'message': f'{ticker} added to portfolio'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/supabase-portfolio/remove', methods=['DELETE'])
def remove_from_supabase_portfolio():
    if not supabase_client:
        return jsonify({'error': 'Supabase not configured'}), 500
    data = request.get_json()
    ticker = data.get('ticker')
    if not ticker:
        return jsonify({'error': 'Ticker required'}), 400
    try:
        supabase_client.table('portfolio').delete().eq('ticker', ticker).execute()
        return jsonify({'success': True, 'message': f'{ticker} removed from portfolio'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyze/<ticker>', methods=['POST'])
def analyze_stock(ticker):
    """Trigger valuation analysis for a stock — runs in background thread"""
    if not supabase_client:
        return jsonify({'error': 'Supabase not configured'}), 500

    data = request.get_json() or {}
    company_name = data.get('name', ticker)
    classification = data.get('classification', 'VALUE')
    primary_reason = data.get('primary_reason', '')

    try:
        result = run_valuation(ticker, company_name, classification, primary_reason)
        supabase_client.table('valuations').upsert({
            'ticker': ticker,
            'classification': result['classification'],
            'report': result['report'],
            'recommendation': result['recommendation'],
            'summary': result['summary']
        }, on_conflict='ticker').execute()
        print(f"[analyze] Saved valuation for {ticker}", flush=True)
        return jsonify({'message': f'Analysis complete for {ticker}.', 'recommendation': result.get('recommendation', '')})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/valuation/<ticker>', methods=['GET'])
def get_valuation(ticker):
    """Get saved valuation for a ticker from Supabase"""
    if not supabase_client:
        return jsonify({'error': 'Supabase not configured'}), 500
    try:
        result = supabase_client.table('valuations').select('*').eq('ticker', ticker).order('created_at', desc=True).limit(1).execute()
        if result.data:
            return jsonify({'valuation': result.data[0]})
        return jsonify({'valuation': None})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug, port=5000)

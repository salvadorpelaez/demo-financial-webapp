from flask import Flask, render_template, request, jsonify, send_from_directory
import sqlite3
import yfinance as yf
import pandas as pd
import requests
import os
from datetime import datetime
from technical_indicators import indicators_bp

app = Flask(__name__)

# Register technical indicators blueprint
app.register_blueprint(indicators_bp)

# Add Alpha Vantage API key - Replace with your actual API key
# Get free key from: https://www.alphavantage.co/support/#api-key
ALPHA_VANTAGE_API_KEY = os.environ.get('ALPHA_VANTAGE_API_KEY', 'demo')  # Use 'demo' for testing

def get_db_connection():
    conn = sqlite3.connect(r"c:\Users\salva\CascadeProjects\sp500-database-webapp\S&P500_Master.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/sp500')
def sp500_page():
    # This will serve the valsp500mainpage_v1.0.11 content
    # For now, we'll create a template for the S&P 500 page
    return render_template('sp500.html')

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

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

if __name__ == '__main__':
    app.run(debug=True, port=5000)

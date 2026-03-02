from flask import Flask, render_template, request, jsonify
import sqlite3

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('S&P500_Master.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

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
        
        # Get data from the first table found
        table_name = tables[0]['name']
        cursor.execute(f"SELECT Ticker, Name, Sector, Sub_Sector FROM {table_name}")
        companies = cursor.fetchall()
        
        # Convert to list of dictionaries with specific column order
        companies_list = []
        for company in companies:
            companies_list.append({
                'ticker': company['Ticker'],
                'name': company['Name'], 
                'sector': company['Sector'],
                'sub_sector': company['Sub_Sector']
            })
        
        return jsonify({
            'table_name': table_name,
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
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Build query based on filters
        query = "SELECT Ticker, Name, Sector, Sub_Sector FROM Companies WHERE 1=1"
        params = []
        
        if sector:
            query += " AND Sector = ?"
            params.append(sector)
        
        if sub_sector:
            query += " AND Sub_Sector = ?"
            params.append(sub_sector)
        
        query += " ORDER BY Name"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        # Convert to list of dictionaries with specific column order
        companies_list = []
        for result in results:
            companies_list.append({
                'ticker': result['Ticker'],
                'name': result['Name'],
                'sector': result['Sector'], 
                'sub_sector': result['Sub_Sector']
            })
        
        return jsonify({
            'companies': companies_list,
            'filters': {
                'sector': sector,
                'sub_sector': sub_sector
            },
            'total_count': len(results)
        })
    except Exception as e:
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
        search_query = f"SELECT Ticker, Name, Sector, Sub_Sector FROM {table_name} WHERE LOWER(Ticker) LIKE ? OR LOWER(Name) LIKE ? OR LOWER(Sector) LIKE ? OR LOWER(Sub_Sector) LIKE ?"
        search_params = [f'%{query}%'] * 4
        
        cursor.execute(search_query, search_params)
        results = cursor.fetchall()
        
        # Convert to list of dictionaries with specific column order
        companies_list = []
        for result in results:
            companies_list.append({
                'ticker': result['Ticker'],
                'name': result['Name'],
                'sector': result['Sector'], 
                'sub_sector': result['Sub_Sector']
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)

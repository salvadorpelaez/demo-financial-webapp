#!/usr/bin/env python3

import sqlite3
import os

def create_search_database():
    """Create a separate database for search operations"""
    search_db_path = 'database/search_cache.db'
    
    # Ensure database directory exists
    os.makedirs('database', exist_ok=True)
    
    conn = sqlite3.connect(search_db_path)
    cursor = conn.cursor()
    
    # Create optimized search tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nasdaq_search (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            exchange TEXT DEFAULT 'NASDAQ'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nyse_search (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            exchange TEXT DEFAULT 'NYSE'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS companies_search (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            exchange TEXT DEFAULT 'S&P 500'
        )
    ''')
    
    # Copy data from main database
    main_db_path = 'S&P500_Master.db'
    
    try:
        main_conn = sqlite3.connect(main_db_path)
        main_cursor = main_conn.cursor()
        
        # Copy NASDAQ data
        main_cursor.execute("SELECT Symbol, CompanyName FROM NASDAQ LIMIT 1000")
        nasdaq_data = main_cursor.fetchall()
        for row in nasdaq_data:
            cursor.execute("INSERT OR REPLACE INTO nasdaq_search (ticker, name, exchange) VALUES (?, ?, 'NASDAQ')", row)
        
        # Copy NYSE data
        main_cursor.execute("SELECT Ticker, Company_Name FROM NYSE LIMIT 1000")
        nyse_data = main_cursor.fetchall()
        for row in nyse_data:
            cursor.execute("INSERT OR REPLACE INTO nyse_search (ticker, name, exchange) VALUES (?, ?, 'NYSE')", row)
        
        # Copy Companies data
        main_cursor.execute("SELECT Ticker, Name FROM Companies LIMIT 500")
        companies_data = main_cursor.fetchall()
        for row in companies_data:
            cursor.execute("INSERT OR REPLACE INTO companies_search (ticker, name, exchange) VALUES (?, ?, 'S&P 500')", row)
        
        main_conn.close()
        
        conn.commit()
        conn.close()
        
        print("Search database created successfully!")
        print(f"NASDAQ records: {len(nasdaq_data)}")
        print(f"NYSE records: {len(nyse_data)}")
        print(f"Companies records: {len(companies_data)}")
        
        return True
        
    except Exception as e:
        print(f"Error copying data: {e}")
        conn.close()
        return False

if __name__ == "__main__":
    create_search_database()

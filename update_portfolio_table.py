#!/usr/bin/env python3

import sqlite3
import os

def update_portfolio_table():
    """Update portfolio table to use ticker column instead of name"""
    db_path = 'database/stock_database.db'
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check current table structure
    cursor.execute("PRAGMA table_info(portfolio)")
    columns = cursor.fetchall()
    print("Current portfolio table structure:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    # Drop and recreate table with correct column names
    cursor.execute("DROP TABLE IF EXISTS portfolio")
    
    # Create portfolio table with ticker column
    cursor.execute('''
        CREATE TABLE portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            company_name TEXT NOT NULL,
            exchange TEXT NOT NULL,
            price REAL,
            change REAL,
            change_percent REAL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, ticker)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Portfolio table updated successfully!")

if __name__ == "__main__":
    update_portfolio_table()

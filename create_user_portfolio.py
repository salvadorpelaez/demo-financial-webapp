#!/usr/bin/env python3

import sqlite3
import os

def create_user_portfolio_tables():
    """Create users and portfolio tables in the database"""
    db_path = 'database/stock_database.db'
    
    # Ensure database directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create portfolio table with user relationship
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            name TEXT NOT NULL,
            exchange TEXT NOT NULL,
            price REAL,
            change REAL,
            change_percent REAL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, ticker)
        )
    ''')
    
    # Insert test_user if not exists
    cursor.execute("SELECT id FROM users WHERE username = 'test_user'")
    test_user = cursor.fetchone()
    
    if not test_user:
        cursor.execute("INSERT INTO users (username, email) VALUES (?, ?)", ('test_user', 'test@example.com'))
        print("Created test_user")
    else:
        print("test_user already exists")
    
    conn.commit()
    conn.close()
    print("Users and portfolio tables created successfully!")

if __name__ == "__main__":
    create_user_portfolio_tables()

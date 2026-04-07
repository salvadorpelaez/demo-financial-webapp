"""
MCP Client — Financial Data Service
Thin wrapper that calls the financial-app-mcp-server HTTP endpoints
instead of making direct yfinance calls.

The MCP server must be running locally:
    cd ../financial-app-mcp-server && python http_server.py

MCP_BASE_URL can be overridden via environment variable for production.
"""

import os
import json
import requests

MCP_BASE_URL = os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:8001")
TIMEOUT = 30  # seconds


def _post(endpoint: str, payload: dict) -> dict:
    """Make a POST call to the MCP server and return parsed JSON."""
    try:
        resp = requests.post(
            f"{MCP_BASE_URL}/tools/{endpoint}",
            json=payload,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        return {"error": "MCP server is not running. Start it with: python http_server.py"}
    except requests.Timeout:
        return {"error": f"MCP server timed out after {TIMEOUT}s"}
    except Exception as e:
        return {"error": str(e)}


def get_market_data(symbol: str, period: str = "2d", start_date: str = "", end_date: str = "") -> dict:
    """
    Fetch OHLCV price history for a ticker.
    Returns parsed dict with 'symbol', 'rows', 'data' keys.
    """
    return _post("get_market_data", {
        "symbol": symbol,
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
    })


def get_fundamentals(symbol: str) -> dict:
    """
    Fetch key fundamental metrics for a ticker.
    Returns parsed dict with P/E, market cap, EPS, etc.
    """
    return _post("get_fundamentals", {"symbol": symbol})


def get_technicals(symbol: str, period: str = "6mo") -> dict:
    """
    Fetch RSI, MACD, and Bollinger Bands for a ticker.
    """
    return _post("get_technicals", {"symbol": symbol, "period": period})


def get_current_price(symbol: str) -> dict:
    """
    Convenience: returns current price, previous close, change, change_percent.
    Derived from get_market_data with period='5d'.
    """
    data = get_market_data(symbol, period="5d")
    if "error" in data:
        return data

    rows = data.get("data", {})
    if not rows:
        return {"error": f"No price data for {symbol}"}

    dates = sorted(rows.keys())
    latest = rows[dates[-1]]
    prev   = rows[dates[-2]] if len(dates) >= 2 else latest

    current = round(float(latest["Close"]), 2)
    previous = round(float(prev["Close"]), 2)
    change = round(current - previous, 2)
    change_pct = round((change / previous * 100) if previous != 0 else 0, 2)

    return {
        "symbol": symbol,
        "price": current,
        "previous_close": previous,
        "change": change,
        "change_percent": change_pct,
    }

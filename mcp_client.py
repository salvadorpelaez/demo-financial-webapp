"""
MCP Client — Financial Data Service
Calls financial-app-mcp-server via real MCP streamable-http protocol.
Falls back to direct yfinance if MCP server is unreachable (e.g. Vercel).

Local dev  : python server.py http  → MCP endpoint http://127.0.0.1:8002/mcp
Production : set MCP_SERVER_URL env var to hosted MCP server, or leave
             unset to use yfinance fallback automatically.
"""

import asyncio
import json
import os

MCP_ENDPOINT = os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:8002/mcp")


# ── MCP transport (real protocol) ─────────────────────────────────────────────

async def _call_tool(tool_name: str, args: dict) -> str:
    from mcp.client.streamable_http import streamablehttp_client
    from mcp import ClientSession
    async with streamablehttp_client(MCP_ENDPOINT) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, args)
            return result.content[0].text


def _mcp_call(tool_name: str, args: dict) -> dict:
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            raw = loop.run_until_complete(_call_tool(tool_name, args))
            return json.loads(raw)
        finally:
            loop.close()
    except Exception:
        return {"_mcp_unavailable": True}


# ── yfinance fallback ─────────────────────────────────────────────────────────

def _yf_market_data(symbol: str, period: str = "2d") -> dict:
    import yfinance as yf
    try:
        df = yf.Ticker(symbol).history(period=period)
        if df.empty:
            return {"error": f"No data for {symbol}"}
        df.index = df.index.strftime("%Y-%m-%d")
        return {
            "symbol": symbol.upper(),
            "rows": len(df),
            "data": df[["Open", "High", "Low", "Close", "Volume"]].round(4).to_dict(orient="index")
        }
    except Exception as e:
        return {"error": str(e)}


def _yf_fundamentals(symbol: str) -> dict:
    import yfinance as yf
    try:
        info = yf.Ticker(symbol).info
        return {
            "symbol": symbol.upper(),
            "name": info.get("longName"),
            "sector": info.get("sector"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "eps": info.get("trailingEps"),
            "revenue": info.get("totalRevenue"),
            "dividend_yield": info.get("dividendYield"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "beta": info.get("beta"),
        }
    except Exception as e:
        return {"error": str(e)}


# ── Public API ────────────────────────────────────────────────────────────────

def get_market_data(symbol: str, period: str = "2d",
                    start_date: str = "", end_date: str = "") -> dict:
    result = _mcp_call("get_market_data", {
        "symbol": symbol, "period": period,
        "start_date": start_date, "end_date": end_date,
    })
    if result.get("_mcp_unavailable"):
        return _yf_market_data(symbol, period)
    return result


def get_fundamentals(symbol: str) -> dict:
    result = _mcp_call("get_fundamentals", {"symbol": symbol})
    if result.get("_mcp_unavailable"):
        return _yf_fundamentals(symbol)
    return result


def get_technicals(symbol: str, period: str = "6mo") -> dict:
    result = _mcp_call("get_technicals", {"symbol": symbol, "period": period})
    if result.get("_mcp_unavailable"):
        return {"error": "Technicals require MCP server — not available in fallback mode"}
    return result


def get_current_price(symbol: str) -> dict:
    data = get_market_data(symbol, period="5d")
    if "error" in data:
        return data
    rows = data.get("data", {})
    if not rows:
        return {"error": f"No price data for {symbol}"}
    dates    = sorted(rows.keys())
    latest   = rows[dates[-1]]
    prev     = rows[dates[-2]] if len(dates) >= 2 else latest
    current  = round(float(latest["Close"]), 2)
    previous = round(float(prev["Close"]), 2)
    change   = round(current - previous, 2)
    change_pct = round((change / previous * 100) if previous != 0 else 0, 2)
    return {
        "symbol": symbol, "price": current,
        "previous_close": previous,
        "change": change, "change_percent": change_pct,
    }

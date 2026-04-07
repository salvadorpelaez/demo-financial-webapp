"""
MCP Client — Financial Data Service
Calls financial-app-mcp-server via the real MCP streamable-http protocol.
Flask (sync) bridges to async MCP client via asyncio event loop.

The MCP server must be running:
    cd ../financial-app-mcp-server && python server.py http

MCP endpoint: http://127.0.0.1:8002/mcp
"""

import asyncio
import json
import os

from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

MCP_ENDPOINT = os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:8002/mcp")


async def _call_tool(tool_name: str, args: dict) -> str:
    """Open an MCP session, call a tool, return the raw text result."""
    async with streamablehttp_client(MCP_ENDPOINT) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, args)
            return result.content[0].text


def _mcp_call(tool_name: str, args: dict) -> dict:
    """Sync wrapper — runs async MCP call in a fresh event loop."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            raw = loop.run_until_complete(_call_tool(tool_name, args))
            return json.loads(raw)
        finally:
            loop.close()
    except Exception as e:
        return {"error": f"MCP call failed ({tool_name}): {str(e)}"}


# ── Public API (same interface as before — Flask routes unchanged) ─────────────

def get_market_data(symbol: str, period: str = "2d",
                    start_date: str = "", end_date: str = "") -> dict:
    return _mcp_call("get_market_data", {
        "symbol": symbol, "period": period,
        "start_date": start_date, "end_date": end_date,
    })


def get_fundamentals(symbol: str) -> dict:
    return _mcp_call("get_fundamentals", {"symbol": symbol})


def get_technicals(symbol: str, period: str = "6mo") -> dict:
    return _mcp_call("get_technicals", {"symbol": symbol, "period": period})


def get_current_price(symbol: str) -> dict:
    """Convenience: current price, previous close, change, change_percent."""
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
        "symbol":         symbol,
        "price":          current,
        "previous_close": previous,
        "change":         change,
        "change_percent": change_pct,
    }

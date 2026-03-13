"""
technical_indicators.py
-----------------------
Flask blueprint for Valerious Technical Indicators feature.
Fetches indicator data from Alpha Vantage API.
Setup:
1. pip install flask requests python-dotenv
2. Add ALPHA_VANTAGE_API_KEY=your_key to your .env file
3. Register blueprint in your main app.py:
from technical_indicators import indicators_bp
app.register_blueprint(indicators_bp)
"""
import os
import requests
from flask import Blueprint, jsonify, request
from dotenv import load_dotenv

load_dotenv()

indicators_bp = Blueprint("indicators", __name__)
ALPHA_VANTAGE_BASE = "https://www.alphavantage.co/query"
API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "demo")

# ---------------------------------------------------------------------------
# Indicator metadata — used by the frontend to build the selector UI
# ---------------------------------------------------------------------------
INDICATOR_CATALOG = [
    # Moving Averages
    {"id": "SMA", "full": "Simple Moving Average", "cat": "moving", "function": "SMA"},
    {"id": "EMA", "full": "Exponential Moving Average", "cat": "moving", "function": "EMA"},
    {"id": "WMA", "full": "Weighted Moving Average", "cat": "moving", "function": "WMA"},
    {"id": "KAMA", "full": "Kaufman Adaptive Moving Average", "cat": "moving", "function": "KAMA"},
    {"id": "DEMA", "full": "Double Exponential Moving Average", "cat": "moving", "function": "DEMA"},
    {"id": "TEMA", "full": "Triple Exponential Moving Average", "cat": "moving", "function": "TEMA"},
    # Momentum
    {"id": "RSI", "full": "Relative Strength Index", "cat": "momentum", "function": "RSI"},
    {"id": "MACD", "full": "Moving Avg Convergence/Divergence", "cat": "momentum", "function": "MACD"},
    {"id": "STOCH", "full": "Stochastic Oscillator", "cat": "momentum", "function": "STOCH"},
    {"id": "WILLR", "full": "Williams %R", "cat": "momentum", "function": "WILLR"},
    {"id": "MOM", "full": "Momentum", "cat": "momentum", "function": "MOM"},
    {"id": "CCI", "full": "Commodity Channel Index", "cat": "momentum", "function": "CCI"},
    {"id": "AROON", "full": "Aroon Oscillator", "cat": "momentum", "function": "AROON"},
    # Volatility & Trend
    {"id": "BBANDS", "full": "Bollinger Bands", "cat": "volatility", "function": "BBANDS"},
    {"id": "ADX", "full": "Average Directional Index", "cat": "volatility", "function": "ADX"},
    {"id": "ATR", "full": "Average True Range", "cat": "volatility", "function": "ATR"},
    {"id": "TRANGE", "full": "True Range", "cat": "volatility", "function": "TRANGE"},
    {"id": "MIDPOINT", "full": "Midpoint over Period", "cat": "volatility", "function": "MIDPOINT"},
    # Volume
    {"id": "OBV", "full": "On Balance Volume", "cat": "volume", "function": "OBV"},
    {"id": "AD", "full": "Chaikin A/D Line", "cat": "volume", "function": "AD"},
    {"id": "MFI", "full": "Money Flow Index", "cat": "volume", "function": "MFI"},
    {"id": "ADOSC", "full": "Chaikin A/D Oscillator", "cat": "volume", "function": "ADOSC"},
    # Advanced
    {"id": "HT_TRENDLINE", "full": "Hilbert Transform Trendline", "cat": "advanced", "function": "HT_TRENDLINE"},
    {"id": "HT_DCPERIOD", "full": "HT Dominant Cycle Period", "cat": "advanced", "function": "HT_DCPERIOD"},
    {"id": "APO", "full": "Absolute Price Oscillator", "cat": "advanced", "function": "APO"},
    {"id": "PPO", "full": "Percentage Price Oscillator", "cat": "advanced", "function": "PPO"},
    {"id": "ULTOSC", "full": "Ultimate Oscillator", "cat": "advanced", "function": "ULTOSC"},
]

# Indicators that return multiple series (e.g. MACD returns MACD + Signal + Hist)
MULTI_SERIES = {
    "MACD": ["MACD", "MACD_Signal", "MACD_Hist"],
    "STOCH": ["SlowK", "SlowD"],
    "BBANDS": ["Real Upper Band", "Real Middle Band", "Real Lower Band"],
    "AROON": ["Aroon Up", "Aroon Down"],
}

# Indicators that don't require a time_period param
NO_TIME_PERIOD = {"OBV", "AD", "ADOSC", "HT_TRENDLINE", "HT_DCPERIOD", "TRANGE", "MACD", "STOCH", "AROON", "ULTOSC"}

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@indicators_bp.route("/api/indicators/catalog", methods=["GET"])
def get_catalog():
    """Return the full indicator catalog for the frontend selector UI."""
    return jsonify({"indicators": INDICATOR_CATALOG})

@indicators_bp.route("/api/indicators/fetch", methods=["POST"])
def fetch_indicators():
    """
    Fetch one or more technical indicators for a given ticker.
    Request body (JSON):
    {
        "ticker": "AAPL",
        "indicators": ["RSI", "MACD", "BBANDS"],
        "interval": "daily", // optional, default: daily
        "time_period": 14 // optional, default: 14
    }
    Response:
    {
        "ticker": "AAPL",
        "results": {
            "RSI": { "latest": { "RSI": "67.42" }, "series": [...] },
            "MACD": { "latest": { "MACD": "...", "MACD_Signal": "...", ... }, "series": [...] },
            ...
        },
        "errors": { "WILLR": "API error message" }
    }
    """
    body = request.get_json()
    if not body:
        return jsonify({"error": "Request body required"}), 400
    
    ticker = body.get("ticker", "").upper().strip()
    indicators = body.get("indicators", [])
    interval = body.get("interval", "daily")
    time_period = body.get("time_period", 14)
    
    if not ticker:
        return jsonify({"error": "ticker is required"}), 400
    if not indicators:
        return jsonify({"error": "at least one indicator is required"}), 400
    
    results = {}
    errors = {}
    
    for indicator_id in indicators:
        try:
            data = _fetch_single_indicator(ticker, indicator_id, interval, time_period)
            results[indicator_id] = data
        except Exception as e:
            errors[indicator_id] = str(e)
    
    return jsonify({
        "ticker": ticker,
        "results": results,
        "errors": errors,
    })

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _fetch_single_indicator(ticker, indicator_id, interval, time_period):
    """Call Alpha Vantage for one indicator and return parsed latest + series."""
    params = {
        "function": indicator_id,
        "symbol": ticker,
        "interval": interval,
        "apikey": API_KEY,
        "datatype": "json",
    }
    
    if indicator_id not in NO_TIME_PERIOD:
        params["time_period"] = time_period
    
    # MACD needs specific series_type
    if indicator_id == "MACD":
        params["series_type"] = "close"
        params["fastperiod"] = 12
        params["slowperiod"] = 26
        params["signalperiod"] = 9
    
    if indicator_id in {"SMA", "EMA", "WMA", "KAMA", "DEMA", "TEMA",
                       "RSI", "WILLR", "MOM", "CCI", "ADX", "ATR",
                       "TRANGE", "MIDPOINT", "MFI", "APO", "PPO",
                       "HT_TRENDLINE", "HT_DCPERIOD", "ULTOSC", "BBANDS"}:
        params["series_type"] = "close"
    
    response = requests.get(ALPHA_VANTAGE_BASE, params=params, timeout=10)
    response.raise_for_status()
    raw = response.json()
    
    # Alpha Vantage wraps results in a key like "Technical Analysis: RSI"
    data_key = next((k for k in raw if k.startswith("Technical Analysis")), None)
    if data_key is None:
        # Check for API error/info messages
        if "Information" in raw:
            raise ValueError("API rate limit reached. Please wait or upgrade your plan.")
        if "Note" in raw:
            raise ValueError("API rate limit reached (5 calls/min on free tier).")
        raise ValueError(f"Unexpected response format: {list(raw.keys())}")
    
    time_series = raw[data_key]
    dates = sorted(time_series.keys(), reverse=True)
    latest_date = dates[0] if dates else None
    latest_values = time_series[latest_date] if latest_date else {}
    
    # Build a compact series (last 30 data points) for charting
    series = [
        {"date": d, **time_series[d]}
        for d in dates[:30]
    ]
    
    return {
        "latest_date": latest_date,
        "latest": latest_values,
        "series": series,
        "multi_series": MULTI_SERIES.get(indicator_id, None),
    }

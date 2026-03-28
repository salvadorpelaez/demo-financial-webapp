import yfinance as yf
import json
from .base import BaseAgent


SYSTEM_PROMPT = """You are a growth equity analyst specializing in hypergrowth companies.
You perform a structured analysis using real financial data and generate a directional signal classification.
This framework is for companies growing revenue >20% annually where traditional value metrics are unreliable.
The central question is not 'is this cheap?' but 'is this growth durable, and what is it worth?'
Your audience is an intelligent non-specialist. Show your work, use tables, avoid jargon.
This is an AI classification model for educational purposes only. It is not financial advice."""


class HypergrowthGrader(BaseAgent):

    def fetch_data(self, ticker: str) -> dict:
        t = yf.Ticker(ticker)
        info = t.info
        data = {k: info.get(k) for k in [
            'longName', 'marketCap', 'currentPrice', 'trailingEps',
            'sharesOutstanding', 'trailingPE', 'forwardPE',
            'priceToBook', 'returnOnEquity', 'debtToEquity',
            'totalDebt', 'totalRevenue', 'freeCashflow',
            'grossMargins', 'operatingMargins', 'profitMargins',
            'revenueGrowth', 'earningsGrowth', 'enterpriseValue',
            'enterpriseToRevenue', 'enterpriseToEbitda'
        ]}
        try:
            financials = t.financials.to_string()
        except Exception:
            financials = "Not available"
        try:
            balance_sheet = t.balance_sheet.to_string()
        except Exception:
            balance_sheet = "Not available"
        try:
            cashflow = t.cashflow.to_string()
        except Exception:
            cashflow = "Not available"

        return {
            "info": data,
            "financials": financials,
            "balance_sheet": balance_sheet,
            "cashflow": cashflow
        }

    def analyze(self, ticker: str, company_name: str, primary_reason: str) -> dict:
        print(f"[HypergrowthGrader] Fetching data for {ticker}...")
        data = self.fetch_data(ticker)

        user_prompt = f"""Analyze {ticker} ({company_name}) using the Hypergrowth investing framework.

Why this stock is classified as HYPERGROWTH: {primary_reason}

FINANCIAL DATA:
{json.dumps(data['info'], indent=2)}

INCOME STATEMENT:
{data['financials']}

BALANCE SHEET:
{data['balance_sheet']}

CASH FLOW:
{data['cashflow']}

Perform a structured analysis covering:
1. Revenue Growth Quality (5-year trend, CAGR, acceleration or deceleration)
2. TAM and Market Penetration (runway remaining)
3. Gross Margin Trajectory (expanding or contracting)
4. Rule of 40 Score (Revenue Growth % + FCF Margin %)
5. Operating Leverage (are expenses growing slower than revenue?)
6. Path to Profitability (cash runway, FCF trend)
7. Competitive Moat Formation (network effects, switching costs, data advantage)
8. Valuation — Reverse DCF (what growth rate does the current price imply?)
9. Risk Register (top 3 risks with severity)

End with:
- MODEL SIGNAL: POSITIVE SIGNAL / NEUTRAL SIGNAL / NEGATIVE SIGNAL — Model Output — This is not investment advice
- One-paragraph plain-English summary a non-specialist can understand
- Disclaimer: This is an AI classification model for educational purposes only. It is not financial advice."""

        print(f"[HypergrowthGrader] Running HYPERGROWTH analysis for {ticker}...")
        report = self.run(SYSTEM_PROMPT, user_prompt, max_tokens=4096)

        recommendation = "HOLD"
        for line in report.split('\n'):
            if 'MODEL SIGNAL:' in line.upper() or 'RECOMMENDATION:' in line.upper():
                if 'POSITIVE' in line.upper() or 'BUY' in line.upper():
                    recommendation = "BUY"
                elif 'NEGATIVE' in line.upper() or 'SELL' in line.upper():
                    recommendation = "SELL"
                break

        summary_lines = [l for l in report.split('\n') if len(l) > 80]
        summary = summary_lines[-1] if summary_lines else report[:300]

        return {
            "ticker": ticker,
            "classification": "HYPERGROWTH",
            "report": report,
            "recommendation": recommendation,
            "summary": summary
        }

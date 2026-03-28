import yfinance as yf
import json
from .base import BaseAgent


SYSTEM_PROMPT = """You are a disciplined value investing analyst trained in Warren Buffett's principles.
You perform a structured analysis using real financial data and generate a directional signal classification.
Your audience is an intelligent non-specialist — explain every calculation clearly, avoid jargon, and always show your work.
Use tables wherever possible. This is an AI classification model for educational purposes only. It is not financial advice."""


class StockGrader(BaseAgent):

    def fetch_data(self, ticker: str) -> dict:
        t = yf.Ticker(ticker)
        info = t.info
        data = {k: info.get(k) for k in [
            'longName', 'marketCap', 'currentPrice', 'trailingEps',
            'bookValue', 'sharesOutstanding', 'trailingPE',
            'priceToBook', 'returnOnEquity', 'debtToEquity',
            'totalDebt', 'totalRevenue', 'freeCashflow',
            'grossMargins', 'operatingMargins', 'profitMargins'
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
        print(f"[StockGrader] Fetching data for {ticker}...")
        data = self.fetch_data(ticker)

        user_prompt = f"""Analyze {ticker} ({company_name}) using the Warren Buffett value investing framework.

Why this stock is classified as VALUE: {primary_reason}

FINANCIAL DATA:
{json.dumps(data['info'], indent=2)}

INCOME STATEMENT:
{data['financials']}

BALANCE SHEET:
{data['balance_sheet']}

CASH FLOW:
{data['cashflow']}

Perform a structured analysis covering:
1. Intrinsic Value (Buffett formula: IV = EPS × (8.5 + 2g) × (4.4/Y) and Two-Stage DCF)
2. Retained Earnings Analysis (10-year MC/RE ratio)
3. Free Cash Flow and Profit Margins
4. Competitive Moat Assessment
5. Debt Analysis
6. Return on Equity (10-year trend)
7. Management Quality

End with:
- MODEL SIGNAL: POSITIVE SIGNAL / NEUTRAL SIGNAL / NEGATIVE SIGNAL — Model Output — This is not investment advice
- One-paragraph plain-English summary a non-specialist can understand
- Disclaimer: This is an AI classification model for educational purposes only. It is not financial advice."""

        print(f"[StockGrader] Running VALUE analysis for {ticker}...")
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
            "classification": "VALUE",
            "report": report,
            "recommendation": recommendation,
            "summary": summary
        }

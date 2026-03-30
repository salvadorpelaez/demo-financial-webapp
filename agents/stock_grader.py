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

        user_prompt = f"""Analyze {ticker} ({company_name}) using the full 13-step Warren Buffett value investing framework.

Why this stock is classified as VALUE: {primary_reason}

FINANCIAL DATA:
{json.dumps(data['info'], indent=2)}

INCOME STATEMENT:
{data['financials']}

BALANCE SHEET:
{data['balance_sheet']}

CASH FLOW:
{data['cashflow']}

CRITICAL INSTRUCTIONS:
- You MUST include all 13 steps below in your report, in order, using the exact headings shown.
- If data for a step is unavailable or incomplete, still include the section heading and write: "Data not available for this step — [brief explanation of what is missing and why it matters]."
- Never skip a section. Transparency about missing data is essential.
- Use tables wherever the data supports it.
- Show all calculations explicitly.

## STEP 1: Earnings Per Share (EPS) — 10-Year Trend
Analyze EPS over the past 10 years. Is it growing consistently? Show the trend.

## STEP 2: Return on Equity (ROE) — 10-Year Trend
Calculate ROE for each available year. Buffett looks for >15% sustained ROE.

## STEP 3: Return on Invested Capital (ROIC)
Calculate ROIC. Is the company generating returns well above its cost of capital?

## STEP 4: Debt-to-Equity Ratio
Assess the debt load. Buffett prefers companies that can pay off long-term debt within 3–4 years from earnings.

## STEP 5: Free Cash Flow (FCF)
Is the company generating consistent free cash flow? Show FCF trend and FCF margin.

## STEP 6: Profit Margins — Gross, Operating, Net
Analyze all three margin types. Are they stable or expanding? Buffett favors companies with durable, wide margins.

## STEP 7: Retained Earnings
Is the company retaining earnings and deploying them effectively? Analyze the 10-year retained earnings trend and the market cap / retained earnings ratio.

## STEP 8: Intrinsic Value — Ben Graham Formula
Calculate: IV = EPS × (8.5 + 2g) × (4.4 / Y)
Where g = estimated growth rate, Y = current 10-year Treasury yield (~4.5%). Compare to current price.

## STEP 9: Intrinsic Value — Discounted Cash Flow (DCF)
Perform a two-stage DCF. State your assumptions clearly (growth rate, discount rate, terminal value). Compare to current price and calculate margin of safety.

## STEP 10: Margin of Safety
What is the margin of safety based on Steps 8 and 9? Buffett requires at least 25–30% below intrinsic value.

## STEP 11: Competitive Moat
Assess the economic moat: brand, patents, switching costs, network effects, cost advantage. Rate as Wide / Narrow / None and explain.

## STEP 12: Management Quality
Assess capital allocation, share buybacks, dividends, insider ownership, and any notable management decisions visible in the data.

## STEP 13: Price-to-Book Value (P/B)
Calculate P/B ratio. How does it compare to historical averages and sector peers?

---

End with:
MODEL SIGNAL: POSITIVE SIGNAL / NEUTRAL SIGNAL / NEGATIVE SIGNAL — Model Output — This is not investment advice

PLAIN-ENGLISH SUMMARY: One paragraph summarizing the key findings for a non-specialist.

DISCLAIMER: This is an AI classification model for educational purposes only. It is not financial advice."""

        print(f"[StockGrader] Running VALUE analysis for {ticker}...")
        report = self.run(SYSTEM_PROMPT, user_prompt, max_tokens=8192)

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

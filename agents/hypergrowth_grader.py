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

        user_prompt = f"""Analyze {ticker} ({company_name}) using the full 9-step Hypergrowth investing framework.

Why this stock is classified as HYPERGROWTH: {primary_reason}

FINANCIAL DATA:
{json.dumps(data['info'], indent=2)}

INCOME STATEMENT:
{data['financials']}

BALANCE SHEET:
{data['balance_sheet']}

CASH FLOW:
{data['cashflow']}

CRITICAL INSTRUCTIONS:
- You MUST include all 9 steps below in your report, in order, using the exact headings shown.
- If data for a step is unavailable or incomplete, still include the section heading and write: "Data not available for this step — [brief explanation of what is missing and why it matters]."
- Never skip a section. Transparency about missing data is essential.
- Use tables wherever the data supports it.
- Show all calculations explicitly.

## STEP 1: Revenue Growth Quality
Analyze revenue growth over the past 5 years. Calculate CAGR. Is growth accelerating or decelerating? Consistency matters — show the year-by-year trend.

## STEP 2: TAM and Market Penetration
Assess the Total Addressable Market and current penetration rate. How much runway remains? Is the company still in early innings or approaching saturation?

## STEP 3: Gross Margin Trajectory
Is the gross margin expanding or contracting over time? For hypergrowth companies, expanding margins signal improving unit economics and pricing power.

## STEP 4: Rule of 40 Score
Calculate: Revenue Growth % + FCF Margin %. A score above 40 signals a healthy balance between growth and profitability. Show the calculation explicitly.

## STEP 5: Operating Leverage
Are operating expenses growing slower than revenue? Show the ratio of revenue growth to expense growth. Improving operating leverage is a key signal of scalability.

## STEP 6: Path to Profitability
Is the company profitable? If not, what is the cash runway and FCF trend? Is the path to profitability credible based on the data? Be direct about what the numbers show.

## STEP 7: Competitive Moat Formation
Assess moat durability for a high-growth company: network effects, switching costs, data advantages, platform lock-in. Rate as Strong / Developing / Weak and explain.

## STEP 8: Valuation — Reverse DCF
What revenue growth rate is implied by the current share price? State your assumptions (discount rate, terminal growth, margin targets). Is the implied growth rate achievable or does it require perfection?

## STEP 9: Risk Register
Identify the top 3 risks with severity (High / Medium / Low) and a brief explanation of each. Include competitive risk, execution risk, and macro/regulatory risk where relevant.

---

End with:
MODEL SIGNAL: POSITIVE SIGNAL / NEUTRAL SIGNAL / NEGATIVE SIGNAL — Model Output — This is not investment advice

PLAIN-ENGLISH SUMMARY: One paragraph summarizing the key findings for a non-specialist.

DISCLAIMER: This is an AI classification model for educational purposes only. It is not financial advice."""

        print(f"[HypergrowthGrader] Running HYPERGROWTH analysis for {ticker}...")
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
            "classification": "HYPERGROWTH",
            "report": report,
            "recommendation": recommendation,
            "summary": summary
        }

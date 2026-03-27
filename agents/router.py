from .stock_grader import StockGrader
from .hypergrowth_grader import HypergrowthGrader


def run_valuation(ticker: str, company_name: str, classification: str, primary_reason: str) -> dict:
    if classification == "HYPERGROWTH":
        agent = HypergrowthGrader()
    else:
        agent = StockGrader()
    return agent.analyze(ticker, company_name, primary_reason)

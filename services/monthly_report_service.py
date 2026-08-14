# services/monthly_report_service.py
import json
from datetime import datetime, timedelta

from crud_db import get_monthly_pnl, insert_monthly_pnl
from monthly_ledger import get_monthly_ledger
from monthly_performance import calculate_monthly_performance, calculate_monthly_dividends
from services.portfolio_service import get_portfolio_holdings_json


def build_monthly_report(year_month: str | None = None) -> dict:
    if not year_month:
        year_month = datetime.now().strftime("%Y-%m")

    # Portfolio holdings (JSON string -> dict)
    holdings = json.loads(get_portfolio_holdings_json(print_html=False))

    # Monthly performance
    monthly_perf = calculate_monthly_performance(year_month, print_table=False)
    if not monthly_perf:
        raise Exception(f"Monthly performance is empty. Missing snapshot for previous month of {year_month}.")

    # Ledger (JSON string -> dict)
    ledger = json.loads(get_monthly_ledger(year_month))

    # Dividends total
    dividends_total = float(calculate_monthly_dividends(year_month))

    # Open balance from previous month close
    last_month = (datetime.strptime(year_month, "%Y-%m") - timedelta(days=1)).strftime("%Y-%m")
    last_month_rows = get_monthly_pnl(year_month=last_month)
    open_bal = float(last_month_rows[0]["close_bal"]) if last_month_rows else 0.0

    income = float(ledger.get("Total_Income", 0.0))
    expenses = float(ledger.get("Total_Expense", 0.0))
    stock_pnl = float(monthly_perf["totals"]["total_net_diff"])

    # Insert/update current month PnL
    insert_monthly_pnl(
        year_month=year_month,
        open_bal=open_bal,
        income=income,
        expenses=expenses,
        stock_pnl=stock_pnl,
        dividend=dividends_total,
    )

    # Read back computed columns
    current_rows = get_monthly_pnl(year_month=year_month)
    current_pnl = current_rows[0] if current_rows else {}

    # Round floats for clean output
    for k, v in list(current_pnl.items()):
        if isinstance(v, float):
            current_pnl[k] = round(v, 2)

    return {
        "year_month": year_month,
        "previous_month": last_month,
        "portfolio_performance": holdings,
        "monthly_performance": monthly_perf,
        "monthly_ledger": ledger,
        "dividends_total": round(dividends_total, 2),
        "monthly_pnl": current_pnl,
    }
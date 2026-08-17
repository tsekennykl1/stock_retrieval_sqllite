from datetime import datetime, timedelta
from crud_db import get_dividends


def calculate_monthly_dividends(year_month,print_table=False):
    """Calculate total dividends received for the given month."""

    dividends = get_dividends(year_month=year_month)
    total_dividends = 0.0
    if print_table:
        print(f"Retrieved {len(dividends)} dividend records for {year_month}.")
        print(f"\n💰 Dividend Report for {year_month}")
        print("=" * 50)
        print(f"{'Symbol':<10} | {'Dividend':<10}")
        print("-" * 50)

    for d in dividends:
        # Use .get() to prevent KeyError if keys are slightly different
        symbol = d.get('symbol', 'UNKNOWN')
        # Fallback to other common key names if 'amount' is not found
        amount = d.get('total_dividend', 0.0)
        
        total_dividends += float(amount)
        if print_table:
            print(f"{symbol:<10} | {amount:<10.2f}")
    if print_table:
        print("-" * 50)
        print(f"{'TOTAL':<10} | {total_dividends:<10.2f}")
        print("=" * 50 + "\n")

    return total_dividends
if __name__ == "__main__":
    current_month = datetime.now().strftime('%Y-%m')
    calculate_monthly_dividends(current_month, True)
import json
from datetime import datetime, timedelta
from crud_db import get_dividends


def calculate_monthly_dividends(year_month, print_table=False):
    """Calculate total dividends received for the given month and return as a dictionary."""

    dividends = get_dividends(year_month=year_month)
    total_dividends = 0.0
    dividend_details = []

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

        amount_per_share = float(d.get('amount_per_share', 0.0))
        quantity = float(d.get('quantity', 0.0))
        dividend_amount = float(d.get('total_dividend', 0.0))
        payment_date = d.get('payment_date', 'N/A')
        total_dividends += dividend_amount
        
        dividend_details.append({
            "symbol": symbol,
            "amount_per_share": round(amount_per_share, 4),
            "quantity": round(quantity, 2),
            "divident_amount": round(dividend_amount, 2),
            "payment_date": payment_date
        })

        if print_table:
            print(f"{symbol:<10} | {amount_per_share:<10.2f}| {quantity:<10.2f}| {dividend_amount:<10.2f}| {payment_date}")
            
    if print_table:
        print("-" * 50)
        print(f"{'TOTAL':<10} | {total_dividends:<10.2f}")
        print("=" * 50 + "\n")

    # ✅ Return structured data
    return {
        "year_month": year_month,
        "dividends": dividend_details,
        "total_dividends": round(total_dividends, 2)
    }

if __name__ == "__main__":
    current_month = datetime.now().strftime('%Y-%m')
    result = calculate_monthly_dividends(current_month, print_table=False)
    print("JSON Output:")
    print(json.dumps(result, indent=4))
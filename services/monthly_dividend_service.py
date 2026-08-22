# services/monthly_dividend_service.py
import json
from datetime import datetime, timedelta
from crud_db import get_dividends, normalize_date


def calculate_monthly_dividends(year_month, print_table=False):
    """Calculate total dividends received for the given month and return as a dictionary."""

    dividends = get_dividends(year_month=year_month)
    total_dividends = 0.0
    dividend_details = []

    if print_table:
        print(f"Retrieved {len(dividends)} dividend records for {year_month}.")
        print(f"\n💰 Dividend Report for {year_month}")
        print("=" * 80)
        print(f"{'Symbol':<10} | {'Per Share':<10} | {'Qty':<10} | {'Amount':<10} | {'Ex-Div Date':<12} | {'Payment Date':<12}")
        print("-" * 80)

    for d in dividends:
        symbol = d.get('symbol', 'UNKNOWN')
        stock_name = d.get('stock_name', '')    
        amount_per_share = float(d.get('amount_per_share', 0.0))
        quantity = float(d.get('quantity', 0.0))
        dividend_amount = float(d.get('total_dividend', 0.0))
        payment_date = d.get('payment_date')
        ex_dividend_date = d.get('ex_dividend_date', '')

        total_dividends += dividend_amount

        dividend_details.append({
            "symbol": symbol,
            "stock_name": stock_name,
            "amount_per_share": round(amount_per_share, 4),
            "quantity": round(quantity, 2),
            "dividend_amount": round(dividend_amount, 2),
            "payment_date": normalize_date(payment_date),
            "ex_dividend_date": normalize_date(ex_dividend_date) if ex_dividend_date else "",
        })

        if print_table:
            ex_div_str = normalize_date(ex_dividend_date) if ex_dividend_date else "N/A"
            pay_str = normalize_date(payment_date) if payment_date else "N/A"
            print(f"{symbol:<10} | {amount_per_share:<10.4f} | {quantity:<10.2f} | {dividend_amount:<10.2f} | {ex_div_str:<12} | {pay_str:<12}")

    if print_table:
        print("-" * 80)
        print(f"{'TOTAL':<10} | {'':<10} | {'':<10} | {total_dividends:<10.2f}")
        print("=" * 80 + "\n")

    # Return structured data
    return {
        "year_month": year_month,
        "dividends": dividend_details,
        "total_dividends": round(total_dividends, 2)
    }


if __name__ == "__main__":
    current_month = datetime.now().strftime('%Y-%m')
    result = calculate_monthly_dividends(current_month, print_table=True)
    print("\nJSON Output:")
    print(json.dumps(result, indent=4))
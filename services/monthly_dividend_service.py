import json
from datetime import datetime, timedelta
from crud_db import get_dividends, get_all_dividends_from, normalize_date


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


def calculate_all_dividends_from(year_month, symbol=None, print_table=False):
    """
    Calculate all dividends received from the given month onwards (inclusive).
    
    Args:
        year_month: Starting month in 'YYYY-MM' format.
        symbol: Optional stock symbol filter.
        print_table: Whether to print a formatted table to console.
    
    Returns:
        Dictionary containing:
            - total_dividend: Total dividend for the specified year_month only.
            - total_all_dividend: Cumulative total of all dividends from year_month onwards
              (current month + all future receivable).
            - dividends: All dividend detail records from year_month onwards.
            - monthly_breakdown: Per-month totals.
    """

    dividends = get_all_dividends_from(year_month, symbol=symbol)
    total_dividend = 0.0        # Only the specified year_month
    total_all_dividend = 0.0    # All from year_month onwards (current + future)
    dividend_details = []
    monthly_breakdown = {}

    if print_table:
        print(f"Retrieved {len(dividends)} dividend records from {year_month} onwards.")
        filter_str = f" (Symbol: {symbol.upper()})" if symbol else ""
        print(f"\n💰 Cumulative Dividend Report from {year_month}{filter_str}")
        print("=" * 95)
        print(f"{'Symbol':<10} | {'Name':<15} | {'Per Share':<10} | {'Qty':<10} | {'Amount':<10} | {'Ex-Div Date':<12} | {'Payment Date':<12}")
        print("-" * 95)

    for d in dividends:
        sym = d.get('symbol', 'UNKNOWN')
        stock_name = d.get('stock_name', '')
        amount_per_share = float(d.get('amount_per_share', 0.0))
        quantity = float(d.get('quantity', 0.0))
        dividend_amount = float(d.get('total_dividend', 0.0))
        payment_date = d.get('payment_date')
        payment_month = d.get('payment_month_str', '')
        ex_dividend_date = d.get('ex_dividend_date', '')

        # Accumulate total for all months (current + future)
        total_all_dividend += dividend_amount

        # Accumulate total for the specified year_month only
        if payment_month == year_month:
            total_dividend += dividend_amount

        # Accumulate monthly breakdown
        if payment_month not in monthly_breakdown:
            monthly_breakdown[payment_month] = {
                "year_month": payment_month,
                "total": 0.0,
                "count": 0
            }
        monthly_breakdown[payment_month]["total"] += dividend_amount
        monthly_breakdown[payment_month]["total"] = round(monthly_breakdown[payment_month]["total"], 2)
        monthly_breakdown[payment_month]["count"] += 1

        dividend_details.append({
            "symbol": sym,
            "stock_name": stock_name,
            "amount_per_share": round(amount_per_share, 4),
            "quantity": round(quantity, 2),
            "dividend_amount": round(dividend_amount, 2),
            "payment_date": normalize_date(payment_date),
            "payment_month_str": payment_month,
            "ex_dividend_date": normalize_date(ex_dividend_date) if ex_dividend_date else "",
        })

        if print_table:
            ex_div_str = normalize_date(ex_dividend_date) if ex_dividend_date else "N/A"
            pay_str = normalize_date(payment_date) if payment_date else "N/A"
            name_short = (stock_name[:13] + "..") if len(stock_name) > 15 else stock_name
            marker = " *" if payment_month == year_month else ""
            print(f"{sym:<10} | {name_short:<15} | {amount_per_share:<10.4f} | {quantity:<10.2f} | {dividend_amount:<10.2f} | {ex_div_str:<12} | {pay_str:<12}{marker}")

    if print_table:
        print("-" * 95)
        print(f"{'TOTAL':<10} | {'':<15} | {'':<10} | {'':<10} | {total_all_dividend:<10.2f}")
        print("=" * 95)

        # Print monthly breakdown
        print(f"\n📊 Monthly Breakdown (from {year_month}):")
        print("-" * 45)
        print(f"{'Month':<12} | {'Count':<8} | {'Total':<12} | {'Note'}")
        print("-" * 45)
        for month_key in sorted(monthly_breakdown.keys()):
            m = monthly_breakdown[month_key]
            note = "<-- current" if month_key == year_month else ""
            print(f"{m['year_month']:<12} | {m['count']:<8} | {m['total']:<12.2f} | {note}")
        print("-" * 45)
        print(f"{'THIS MONTH':<12} | {'':<8} | {total_dividend:<12.2f} | total_dividend")
        print(f"{'ALL (>=)':<12} | {len(dividend_details):<8} | {total_all_dividend:<12.2f} | total_all_dividend")
        print("=" * 45 + "\n")

    # Return structured data
    return {
        "from_year_month": year_month,
        "symbol_filter": symbol.upper() if symbol else None,
        "dividends": dividend_details,
        "monthly_breakdown": sorted(monthly_breakdown.values(), key=lambda x: x["year_month"]),
        "total_records": len(dividend_details),
        "total_dividend": round(total_dividend, 2),
        "total_all_dividend": round(total_all_dividend, 2)
    }


if __name__ == "__main__":
    current_month = datetime.now().strftime('%Y-%m')

    # Monthly report for current month
    print("=" * 95)
    print("  MONTHLY DIVIDEND REPORT")
    print("=" * 95)
    result = calculate_monthly_dividends(current_month, print_table=True)
    print("\nJSON Output (Monthly):")
    print(json.dumps(result, indent=4))

    # Cumulative report from current month onwards (current + future receivable)
    print("\n" + "=" * 95)
    print("  DIVIDEND REPORT: CURRENT + FUTURE RECEIVABLE")
    print("=" * 95)
    result_from = calculate_all_dividends_from(current_month, print_table=True)
    print("\nJSON Output (From {} onwards):".format(current_month))
    print(json.dumps(result_from, indent=4))
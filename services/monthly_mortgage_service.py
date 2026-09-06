import json
from datetime import datetime
from crud_db import get_mortgage_monthly


def calculate_monthly_mortgage(year_month, print_table=False):
    """Retrieve and format mortgage payments for a given month and return as a dictionary."""
    records = get_mortgage_monthly(year_month=year_month)

    if not records:
        return {
            "year_month": year_month,
            "principal": 0.0,
            "interest": 0.0,
            "total_payment": 0.0,
            "remaining_balance": 0.0,
            "period": None
        }

    # Extract the first matching record
    rec = records[0]
    principal = float(rec.get("principal", 0.0))
    interest = float(rec.get("interest", 0.0))
    total_payment = principal + interest
    remaining_balance = float(rec.get("remaining_balance", 0.0))
    period = rec.get("period")

    if print_table:
        print(f"\n🏠 Mortgage Report for {year_month}")
        print("=" * 50)
        print(f"{'Field':<25} | {'Amount ($)':<15}")
        print("-" * 50)
        print(f"{'Period/Installment':<25} | {period if period is not None else 'N/A'}")
        print(f"{'Principal Paid':<25} | {principal:<15.2f}")
        print(f"{'Interest Paid':<25} | {interest:<15.2f}")
        print(f"{'Total Payment':<25} | {total_payment:<15.2f}")
        print(f"{'Remaining Balance':<25} | {remaining_balance:<15.2f}")
        print("=" * 50 + "\n")

    return {
        "year_month": year_month,
        "period": period,
        "principal": round(principal, 2),
        "interest": round(interest, 2),
        "total_payment": round(total_payment, 2),
        "remaining_balance": round(remaining_balance, 2)
    }


def calculate_mortgage_history(start_month=None, print_table=False):
    """
    Retrieve all mortgage history, optionally starting from a specific month.
    
    Returns:
        Dictionary containing historical summary and a monthly list.
    """
    all_records = get_mortgage_monthly()
    
    if start_month:
        # Filter records to keep only those from start_month onwards
        all_records = [r for r in all_records if r.get("year_month", "") >= start_month]

    # Sort forward from oldest to newest month
    all_records = sorted(all_records, key=lambda x: x.get("year_month", ""))

    history_details = []
    total_principal_paid = 0.0
    total_interest_paid = 0.0

    if print_table:
        print(f"\n📈 Cumulative Mortgage Payments History" + (f" (From {start_month})" if start_month else ""))
        print("=" * 80)
        print(f"{'Month':<10} | {'Period':<8} | {'Principal Paid':<15} | {'Interest Paid':<15} | {'Total Paid':<15}")
        print("-" * 80)

    for rec in all_records:
        month = rec.get("year_month", "UNKNOWN")
        period = rec.get("period")
        p = float(rec.get("principal", 0.0))
        i = float(rec.get("interest", 0.0))
        tot = p + i
        
        total_principal_paid += p
        total_interest_paid += i

        history_details.append({
            "year_month": month,
            "period": period,
            "principal": round(p, 2),
            "interest": round(i, 2),
            "total_payment": round(tot, 2),
            "remaining_balance": round(float(rec.get("remaining_balance", 0.0)), 2)
        })

        if print_table:
            print(f"{month:<10} | {str(period) if period is not None else 'N/A':<8} | {p:<15.2f} | {i:<15.2f} | {tot:<15.2f}")

    total_paid_cumulative = total_principal_paid + total_interest_paid

    if print_table and history_details:
        print("-" * 80)
        print(f"{'CUMULATIVE':<10} | {'':<8} | {total_principal_paid:<15.2f} | {total_interest_paid:<15.2f} | {total_paid_cumulative:<15.2f}")
        print("=" * 80 + "\n")

    return {
        "start_month": start_month,
        "history": history_details,
        "total_records": len(history_details),
        "cumulative_principal_paid": round(total_principal_paid, 2),
        "cumulative_interest_paid": round(total_interest_paid, 2),
        "cumulative_total_paid": round(total_paid_cumulative, 2)
    }


if __name__ == "__main__":
    current_month = datetime.now().strftime('%Y-%m')

    # Fetch ledger data for current month
    print("=" * 80)
    print("  MONTHLY MORTGAGE REPORT")
    print("=" * 80)
    result = calculate_monthly_mortgage(current_month, print_table=True)
    print("JSON Output (Monthly):")
    print(json.dumps(result, indent=4))

    # Fetch historical schedules
    print("\n" + "=" * 80)
    print("  MORTGAGE STATS HISTORY")
    print("=" * 80)
    history_result = calculate_mortgage_history(start_month="2023-01", print_table=True)
    print("JSON Output (Cumulative History):")
    print(json.dumps(history_result, indent=4))
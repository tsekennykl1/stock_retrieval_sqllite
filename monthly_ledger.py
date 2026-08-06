import json
from crud_db import get_ledger_entries
from datetime import datetime

def get_monthly_ledger(year_month):

    if isinstance(year_month, str):
        try:
            year_month = datetime.strptime(year_month, "%Y-%m").strftime("%Y-%m")
        except ValueError:
            if "-" in year_month:
                parts = year_month.split("-")
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    year, month = int(parts[0]), int(parts[1])
                    if 1 <= month <= 12:
                        year_month = f"{year:04d}-{month:02d}"
                    else:
                        raise ValueError("Invalid month in year_month string.")
                else:
                    raise ValueError("Invalid year_month format.")
            else:
                raise ValueError("Invalid year_month string format.")
    elif isinstance(year_month, datetime):
        year_month = year_month.strftime("%Y-%m")
    else:
        raise TypeError("year_month must be a string or a datetime object.")

   
    ledger_entries = get_ledger_entries(month_str=year_month)
    income_ledger = [entry for entry in ledger_entries if entry["type"] == "I"]
    expense_ledger = [entry for entry in ledger_entries if entry["type"] == "E"]

    total_income = sum(entry["amount"] for entry in income_ledger)
    total_expense = sum(entry["amount"] for entry in expense_ledger)

    monthly_ledger = {
        "Income": income_ledger,
        "Expense": expense_ledger,
        "Total_Income": total_income,
        "Total_Expense": total_expense
    }

    return json.dumps(monthly_ledger, indent=4)



# Example usage:
print(get_monthly_ledger("2026-08"))
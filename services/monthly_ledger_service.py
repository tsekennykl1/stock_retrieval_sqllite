import json
from datetime import datetime
from crud_db import get_ledger_entries, normalize_date

def retrieve_monthly_ledger(start_date):
    """
    Retrieve monthly Ledger data from the start_date up to the latest month.
    :param start_date: The starting date in 'YYYY-MM' or 'YYYY-MM-DD' format.
    :return: JSON object containing the monthly Ledger data.
    """
    try:

        # Retrieve all monthly ledger entries from the database
        #ledger = get_ledger_entries(start_date=start_date_obj.strftime('%Y-%m-01 00:00:00'))   
        ledger = get_ledger_entries(month_str=start_date)
        #chage the date format to 'YYYY-MM-DD' for each entry and sort the ledger by date   
        ledger = sorted([{
            "date": normalize_date(entry['date']),
            "type": entry['type'],
            "amount": entry['amount'],
            "description": entry['description']
        } for entry in ledger], key=lambda x: x['date'])
        
        #calculate the total income and expenses for the month
        income_total = sum(entry['amount'] for entry in ledger if entry['type'] == 'I')
        expenses_total = sum(entry['amount'] for entry in ledger if entry['type'] == 'E')
        #Add the totals to the output JSON
        output_json = json.dumps({
            "Ledger_entries": ledger,
            "Income_total": income_total,
            "Expenses_total": expenses_total
        }, indent=4)

        return output_json

    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    current_month = datetime.now().strftime('%Y-%m')
    #print(json.dumps(build_monthly_report(current_month)["all_monthly_pnl"][0]))
    print(json.dumps(retrieve_monthly_ledger(current_month), indent=4))




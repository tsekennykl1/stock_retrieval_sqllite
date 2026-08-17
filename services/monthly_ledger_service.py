import json
from datetime import datetime
from crud_db import get_monthly_pnl

def retrieve_monthly_pnl(start_date):
    """
    Retrieve monthly P&L data from the start_date up to the latest month.
    :param start_date: The starting date in 'YYYY-MM' or 'YYYY-MM-DD' format.
    :return: JSON object containing the monthly P&L data.
    """
    try:
        # ✅ Handle both YYYY-MM and YYYY-MM-DD formats safely
        if len(start_date) > 7:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
        else:
            start_date_obj = datetime.strptime(start_date, '%Y-%m')
        
        # Retrieve all monthly P&L entries from the database
        monthly_pnl_data = get_monthly_pnl(pnl_date=start_date_obj.strftime('%Y-%m-01 00:00:00'))   

        filtered_pnl_data = [
            entry for entry in monthly_pnl_data
            if datetime.strptime(entry['year_month'], '%Y-%m') >= start_date_obj
        ]
        # Convert the data to JSON format
        output_json = json.dumps(filtered_pnl_data, indent=4)
        return output_json

    except Exception as e:
        return json.dumps({"error": str(e)})





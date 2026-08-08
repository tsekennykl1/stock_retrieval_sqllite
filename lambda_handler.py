import json
from crud_db import get_monthly_pnl

def lambda_handler(event, context):
    """
    AWS Lambda handler to retrieve monthly PnL for a given date range.
    """
    try:
        # Extract start_date and end_date from the event
        start_date = event.get("start_date")
        end_date = event.get("end_date")

        if not start_date or not end_date:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "start_date and end_date are required"})
            }

        # Retrieve monthly PnL data
        pnl_data = get_monthly_pnl()
        filtered_pnl = [
            entry for entry in pnl_data
            if start_date <= entry["year_month"] <= end_date
        ]

        return {
            "statusCode": 200,
            "body": json.dumps(filtered_pnl)
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }

import json
from datetime import datetime
from crud_db import get_monthly_pnl

def retrieve_monthly_pnl(start_date):
    """
    Retrieve monthly P&L data from the start_date up to the latest month.
    :param start_date: The starting date in 'YYYY-MM' format.
    :return: JSON object containing the monthly P&L data.
    """
    try:
        # Parse the start_date and calculate the current month
        start_date_obj = datetime.strptime(start_date, '%Y-%m')
        current_month = datetime.now().strftime('%Y-%m')

        # Retrieve all monthly P&L entries from the database
        monthly_pnl_data = []
        while start_date_obj.strftime('%Y-%m') <= current_month:
            year_month = start_date_obj.strftime('%Y-%m')
            pnl_data = get_monthly_pnl(year_month=year_month)
            if pnl_data:
                monthly_pnl_data.extend(pnl_data)
            # Increment to the next month
            next_month = start_date_obj.month % 12 + 1
            next_year = start_date_obj.year + (start_date_obj.month // 12)
            start_date_obj = datetime(next_year, next_month, 1)

        # Convert the data to JSON format
        output_json = json.dumps(monthly_pnl_data, indent=4)
        return output_json

    except Exception as e:
        return json.dumps({"error": str(e)})


def lambda_handler(event, context):
    """
    AWS Lambda entry point.
    Expects 'start_date' in query string (?start_date=YYYY-MM) for GET via API Gateway,
    or in the event body for POST, or directly in the event for console testing.
    """

    # 1. Try query string parameters (GET request via API Gateway)
    params = event.get('queryStringParameters') or {}
    start_date = params.get('start_date')

    # 2. Try JSON body (POST request via API Gateway)
    if not start_date:
        body = event.get('body')
        if body:
            try:
                body_json = json.loads(body) if isinstance(body, str) else body
                start_date = body_json.get('start_date')
            except (json.JSONDecodeError, AttributeError):
                pass

    # 3. Try direct event payload (Lambda console testing)
    if not start_date:
        start_date = event.get('start_date')

    # Validate
    if not start_date:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing 'start_date' in the request."})
        }

    result = retrieve_monthly_pnl(start_date)
    return {
        "statusCode": 200,
        "body": result
    }


if __name__ == "__main__":
    # For local testing
    start_date = "2023-01"  # Example start date
    result = retrieve_monthly_pnl(start_date)
    print(result)

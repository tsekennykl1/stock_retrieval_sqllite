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
            
        print(f"Parsed start_date: {start_date_obj.strftime('%Y-%m')}")
        
        # Retrieve all monthly P&L entries from the database
        monthly_pnl_data = get_monthly_pnl(pnl_date=start_date_obj.strftime('%Y-%m-01 00:00:00'))   

        print(f"Retrieved {len(monthly_pnl_data)} entries from the database.")
        filtered_pnl_data = [
            entry for entry in monthly_pnl_data
            if datetime.strptime(entry['year_month'], '%Y-%m') >= start_date_obj
        ]
        print(f"Filtered down to {len(filtered_pnl_data)} entries starting from {start_date}.")
        # Convert the data to JSON format
        output_json = json.dumps(filtered_pnl_data, indent=4)
        return output_json

    except Exception as e:
        return json.dumps({"error": str(e)})


def lambda_handler(event, context):
    """
    AWS Lambda entry point.
    Expects 'start_date' in query string (?start_date=YYYY-MM) for GET via API Gateway,
    or in the event body for POST, or directly in the event for console testing.
    """
    print(f"Received event: {json.dumps(event)}")
    # 1. Try query string parameters (GET request via API Gateway)
    params = event.get('queryStringParameters') or {}
    start_date = params.get('start_date')
    print(f"Extracted start_date from query parameters: {start_date}")
    # 2. Try JSON body (POST request via API Gateway)
    if not start_date:
        body = event.get('body')
        if body:
            try:
                body_json = json.loads(body) if isinstance(body, str) else body
                start_date = body_json.get('start_date')
            except (json.JSONDecodeError, AttributeError):
                pass
    print(f"Extracted start_date from body: {start_date}")
    # 3. Try direct event payload (Lambda console testing)
    if not start_date:
        start_date = event.get('start_date')
    print(f"Extracted start_date from event payload: {start_date}")
    # Validate
    if not start_date:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing 'start_date' in the request."})
        }
    print(f"Final start_date to use: {start_date}")
    result = retrieve_monthly_pnl(start_date)
    print(f"Returning result: {result}")
    return {
        "statusCode": 200,
        "body": result
    }

# ✅ Replaced the commented-out block with a proper local testing simulator
if __name__ == "__main__":
    print("🚀 Running lambda_monthly_pnl locally...")
    
    # Simulating an event payload from another Lambda or API Gateway
    mock_event = {
        "start_date": "2026-08" # or "2026-08-01"
    }
    
    # Invoke the handler
    response = lambda_handler(mock_event, None)
    
    print("\n--- Execution Result ---")
    print(f"Status Code: {response.get('statusCode')}")
    print(f"Body: {response.get('body')}")
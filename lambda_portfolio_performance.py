import json
from services.portfolio_service import get_portfolio_holdings_json

def lambda_handler(event, context):
    try:
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": get_portfolio_holdings_json(print_html=False),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }
import json
from portfolio_performance import get_portfolio_performance_json

def lambda_handler(event, context):
    """AWS Lambda handler to retrieve portfolio performance."""
    try:
        # Call the function to get portfolio performance
        performance_data = get_portfolio_performance_json(print_html=False)
        return {
            "statusCode": 200,
            "body": performance_data,
            "headers": {
                "Content-Type": "application/json"
            }
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
            "headers": {
                "Content-Type": "application/json"
            }
        }

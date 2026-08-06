from lambda_portfolio import lambda_handler
import json

def run_local_tests():
    # 1. Simulate a GET request
    get_event = {
        "httpMethod": "GET",
        "body": None,
        "queryStringParameters": None
    }
    
    print("--- Testing GET ---")
    response = lambda_handler(get_event, None)
    print(json.dumps(response, indent=2))

    # 2. Simulate a POST request (uncomment to test)
    # post_event = {
    #     "httpMethod": "POST",
    #     "body": json.dumps({"symbol": "AAPL", "quantity": 10, "avg_buy_price": 150.0}),
    #     "queryStringParameters": None
    # }
    # print("\n--- Testing POST ---")
    # response = lambda_handler(post_event, None)
    # print(json.dumps(response, indent=2))

if __name__ == "__main__":
    run_local_tests()
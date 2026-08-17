# services/price_service.py
import json
import os
import time
import random
import requests

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

STOCK_RETRIEVAL_FUNCTION_NAME = os.environ.get("STOCK_RETRIEVAL_FUNCTION_NAME", "stock-price-retrieval")
AWS_REGION = os.environ.get("AWS_REGION")  # let Lambda default if not set

_lambda_client = boto3.client(
    "lambda",
    region_name=AWS_REGION,
    config=Config(retries={"max_attempts": 0, "mode": "standard"})
)

RETRYABLE_CODES = {
    "TooManyRequestsException",
    "ThrottlingException",
    "ServiceException",
    "EC2ThrottledException",
    "RequestTimeout",
    "RequestTimeoutException",
}


def fetch_current_prices_lambda(symbols: list[str], max_retries: int = 1) -> dict:
    """
    Invokes stock_retrieval_lambda and returns a dict keyed by symbol.
    Expected return shape per symbol: dict with fields like price, shortName_en, etc.
    """
    if not symbols:
        return {}

    payload = {"queryStringParameters": {"stocks": ",".join(symbols)}}

    for attempt in range(max_retries):
        try:
            resp = _lambda_client.invoke(
                FunctionName=STOCK_RETRIEVAL_FUNCTION_NAME,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload).encode("utf-8"),
            )
            raw = json.loads(resp["Payload"].read() or "{}")

            if resp.get("FunctionError"):
                raise Exception(f"{STOCK_RETRIEVAL_FUNCTION_NAME} error: {raw}")

            # unwrap API Gateway format if present
            if isinstance(raw, dict) and "body" in raw:
                body = raw["body"]
                return json.loads(body) if isinstance(body, str) else body

            return raw

        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code not in RETRYABLE_CODES or attempt == max_retries - 1:
                raise

            sleep_s = min(2 ** attempt, 10) + random.random()
            print(f"fetch_quotes retry {attempt+1}/{max_retries} after {sleep_s:.2f}s due to {code}")
            time.sleep(sleep_s)


#### filepath: /Users/kwokleungtse/Documents/AWS/stock_retrieval_sqllite/monthly_performance.py
# ...existing code...
API_URL = "https://z35lnmmzgi.execute-api.ap-east-1.amazonaws.com/prod/stock?stocks="

def fetch_current_prices(symbols) -> dict:
    """Fetch current stock prices from the API."""
    if not symbols: return {}
    
    try:
        response = requests.get(f"{API_URL}{','.join(symbols)}", timeout=(3, 10))
        
        if response.status_code == 200:
            data = response.json()

        return data
    except requests.RequestException as e:
        print(f"Error fetching prices: {e}")
        return {}


if __name__ == "__main__":
    # Example test for fetch_current_prices and fetch_current_prices_lambda
    test_symbols = ["0700.HK", "9988.HK", "0005.HK"]
    try:
        print("=======================")
        quotes = fetch_current_prices_lambda(test_symbols, max_retries=1)
        print("Fetched quotes:", quotes)
        print("=======================")
        prices = fetch_current_prices(test_symbols)
        print("Get prices:", prices)
        print("=======================")
    except Exception as e:
        print("Error fetching quotes:", e)

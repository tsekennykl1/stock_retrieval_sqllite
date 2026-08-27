# services/price_service.py
import json
import os
import time
import random
import requests
from datetime import datetime, timedelta, timezone

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

TIMEZONE_GMT8 = timezone(timedelta(hours=8))

STOCK_RETRIEVAL_FUNCTION_NAME = os.environ.get("STOCK_RETRIEVAL_FUNCTION_NAME", "yfinance-lambda")
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

RETRIEVAL_DATETIME_FORMAT = "%Y-%m-%d %H:%M"

def _extract_retrieval_datetime(data: dict) -> str:
    """
    Extract retrieval_datetime from the API/Lambda response and convert to GMT+8.
    Looks for common field names that might contain the retrieval timestamp.
    If not found, returns current datetime (GMT+8) formatted as 'YYYY-MM-DD HH:MM'.
    """
    if not isinstance(data, dict):
        return datetime.now(TIMEZONE_GMT8).strftime(RETRIEVAL_DATETIME_FORMAT)

    # Check top-level fields that might hold retrieval datetime
    for key in ("retrieval_datetime", "retrievalDatetime", "retrieval_date",
                "timestamp", "retrieved_at", "lastUpdated", "last_updated"):
        if key in data and data[key]:
            raw_val = str(data[key]).strip()
            # Try to parse and re-format to ensure consistent output
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S",
                        "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f",
                        "%Y-%m-%dT%H:%M:%S.%fZ"):
                try:
                    parsed = datetime.strptime(raw_val, fmt)
                    # If naive (no timezone info), assume it's already UTC
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    # Convert to GMT+8
                    parsed_gmt8 = parsed.astimezone(TIMEZONE_GMT8)
                    return parsed_gmt8.strftime(RETRIEVAL_DATETIME_FORMAT)
                except ValueError:
                    continue
            # Try timezone-aware format separately
            try:
                parsed = datetime.strptime(raw_val, "%Y-%m-%dT%H:%M:%S%z")
                parsed_gmt8 = parsed.astimezone(TIMEZONE_GMT8)
                return parsed_gmt8.strftime(RETRIEVAL_DATETIME_FORMAT)
            except ValueError:
                pass
            # If parsing fails but value looks reasonable, return truncated
            if len(raw_val) >= 16:
                return raw_val[:16]
            return raw_val
    # Fallback: use current datetime in GMT+8
    return datetime.now(TIMEZONE_GMT8).strftime(RETRIEVAL_DATETIME_FORMAT)

def fetch_current_prices_lambda(symbols: list[str], max_retries: int = 1) -> dict:
    """
    Invokes yfinance-lambda and returns a dict keyed by symbol.
    Includes 'retrieval_datetime' (YYYY-MM-DD HH:MM) at the top level.
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
                data = json.loads(body) if isinstance(body, str) else body
            else:
                data = raw

            # Extract retrieval_datetime from response, fallback to now
            retrieval_dt = _extract_retrieval_datetime(data)

            # Ensure data is a dict and inject retrieval_datetime at the top
            if isinstance(data, dict):
                result = {"retrieval_datetime": retrieval_dt}
                result.update(data)
                # Remove the original retrieval key if it existed under a different name
                # to avoid duplication (keep only our standardized key)
                for key in ("retrievalDatetime", "retrieval_date", "timestamp",
                            "retrieved_at", "lastUpdated", "last_updated"):
                    result.pop(key, None)
                return result
            else:
                return {"retrieval_datetime": retrieval_dt}

        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code not in RETRYABLE_CODES or attempt == max_retries - 1:
                raise

            sleep_s = min(2 ** attempt, 10) + random.random()
            print(f"fetch_quotes retry {attempt+1}/{max_retries} after {sleep_s:.2f}s due to {code}")
            time.sleep(sleep_s)


API_URL = "https://z35lnmmzgi.execute-api.ap-east-1.amazonaws.com/prod/stock?stocks="


def fetch_current_prices(symbols) -> dict:
    """
    Fetch current stock prices from the API.
    Includes 'retrieval_datetime' (YYYY-MM-DD HH:MM) at the top level.
    """
    if not symbols:
        return {}

    try:
        response = requests.get(f"{API_URL}{','.join(symbols)}", timeout=(3, 10))

        if response.status_code == 200:
            data = response.json()

            # Extract retrieval_datetime from response, fallback to now
            retrieval_dt = _extract_retrieval_datetime(data)

            # Inject retrieval_datetime at the top of the response
            if isinstance(data, dict):
                result = {"retrieval_datetime": retrieval_dt}
                result.update(data)
                # Remove original retrieval keys to avoid duplication
                for key in ("retrievalDatetime", "retrieval_date", "timestamp",
                            "retrieved_at", "lastUpdated", "last_updated"):
                    result.pop(key, None)
                return result

            return {"retrieval_datetime": retrieval_dt}

        print(f"⚠️  API returned status {response.status_code}")
        return {"retrieval_datetime": datetime.now().strftime(RETRIEVAL_DATETIME_FORMAT)}

    except requests.RequestException as e:
        print(f"Error fetching prices: {e}")
        return {"retrieval_datetime": datetime.now().strftime(RETRIEVAL_DATETIME_FORMAT)}


# ══════════════════════════════════════════════════════════════
#  Stock info retrieval for auto-creating stock records
# ══════════════════════════════════════════════════════════════

def get_stock_info(symbol: str) -> dict | None:
    """
    Fetch stock metadata from the price API for a single symbol.
    Used by transaction_service to auto-create stocks that aren't in the DB yet.

    Tries the HTTP API first (simpler, no AWS credentials needed locally),
    falls back to Lambda invocation.

    Args:
        symbol: Stock symbol, e.g. "0700.HK"

    Returns:
        dict like:
        {
            "symbol": "0700.HK",
            "name": "TENCENT",
            "sector": "Communication Services",
            "currency": "HKD",
        }
        or None if the symbol is unrecognized or fetch fails.
    """
    # Ensure symbol has exchange suffix for the API
    lookup_symbol = symbol if "." in symbol else f"{symbol}.HK"

    try:
        # Try HTTP API first
        data = fetch_current_prices([lookup_symbol])

        if not data or lookup_symbol not in data:
            # Fallback: try Lambda
            data = fetch_current_prices_lambda([lookup_symbol], max_retries=2)

        if not data or lookup_symbol not in data:
            print(f"⚠️  No data returned for symbol '{lookup_symbol}'")
            return None

        stock_data = data[lookup_symbol]

        return {
            "symbol": symbol.upper(),
            "name": stock_data.get("shortName_en") or stock_data.get("shortName") or stock_data.get("name") or symbol,
            "sector": stock_data.get("sector"),
            "currency": stock_data.get("currency", "HKD"),
        }

    except Exception as e:
        print(f"⚠️  Error fetching stock info for '{symbol}': {e}")
        return None


if __name__ == "__main__":
    # Example test for fetch_current_prices and fetch_current_prices_lambda
    test_symbols = ["0700.HK", "9988.HK", "0005.HK"]
    try:
        print("=======================")
        quotes = fetch_current_prices_lambda(test_symbols, max_retries=1)
        print("Fetched quotes:", json.dumps(quotes, indent=2))
        print("=======================")
        prices = fetch_current_prices(test_symbols)
        print("Get prices:", json.dumps(prices, indent=2))
        print("=======================")

        # Test new get_stock_info
        print("--- get_stock_info ---")
        info = get_stock_info("0700.HK")
        print("Stock info:", info)
        print("=======================")
    except Exception as e:
        print("Error fetching quotes:", e)
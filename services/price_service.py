# services/price_service.py
import json
import os
import time
import random

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

STOCK_RETRIEVAL_FUNCTION_NAME = os.environ.get("STOCK_RETRIEVAL_FUNCTION_NAME", "stock_retrieval_lambda")
AWS_REGION = os.environ.get("AWS_REGION")  # let Lambda default if not set

_lambda_client = boto3.client(
    "lambda",
    region_name=AWS_REGION,
    config=Config(retries={"max_attempts": 3, "mode": "standard"})
)

RETRYABLE_CODES = {
    "TooManyRequestsException",
    "ThrottlingException",
    "ServiceException",
    "EC2ThrottledException",
    "RequestTimeout",
    "RequestTimeoutException",
}


def fetch_quotes_via_lambda(symbols: list[str], max_retries: int = 5) -> dict:
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
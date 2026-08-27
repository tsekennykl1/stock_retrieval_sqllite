import json
import os

os.environ.setdefault("AWS_REGION", "ap-east-1")
os.environ.setdefault("STOCK_RETRIEVAL_FUNCTION_NAME", "getStockData")

from lambda_consolidated_monthly_report import lambda_handler

if __name__ == "__main__":
    print("Running lambda_consolidated_monthly_report locally...")
    # ✅ Added start_date and end_date to satisfy the PnL payload requirements
    event = {
        "year_month": "2026-08",
        "start_date": "2026-08-01",
        "end_date": "2026-08-31"
    }
    resp = lambda_handler(event, None)
    print("statusCode:", resp["statusCode"])
    print(resp["body"])
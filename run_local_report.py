import os
import json

# If you want to force a DB path (optional):
# os.environ["DB_PATH"] = "/Users/you/path/mystocks.db"

# Required for boto3 invoke:
os.environ.setdefault("AWS_REGION", "ap-east-1")
os.environ.setdefault("STOCK_RETRIEVAL_FUNCTION_NAME", "getStockData")

from services.monthly_report_service import build_monthly_report

if __name__ == "__main__":
    # test a specific month or default to current month
    report = build_monthly_report("2026-08")
    print(json.dumps(report, indent=2))
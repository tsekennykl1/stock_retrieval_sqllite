import json
import os
import calendar
from datetime import datetime, timezone
from crud_db import get_monthly_pnl
from services.monthly_report_service import build_monthly_report

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": os.environ.get(
        "ALLOWED_ORIGIN", "https://staging.d37gylpwhasobk.amplifyapp.com"
    ),
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
}


def lambda_handler(event, context):
    event = event or {}

    # ── Handle CORS preflight ────────────────────────────────
    http_method = event.get("requestContext", {}).get("http", {}).get("method") \
               or event.get("httpMethod") \
               or ""
    if http_method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({"message": "CORS preflight OK"}),
        }

    # ── Optional override: "2026-08". If not provided, default to current UTC month. ──
    # Support both direct invocation and API Gateway (query string / body)
    year_month = event.get("year_month")

    # If invoked via API Gateway, check queryStringParameters
    if not year_month:
        year_month = (event.get("queryStringParameters") or {}).get("year_month")

    # If still not provided, default to current UTC month
    if not year_month:
        year_month = datetime.now(timezone.utc).strftime("%Y-%m")

    try:
        report = build_monthly_report(year_month=year_month)

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps(report, indent=2, default=str),
        }

    except Exception as e:
        print(f"consolidated_monthly_report error: {e}")
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": str(e)}),
        }
# lambda_consolidated_monthly_report.py
import json
import os
import boto3
from datetime import datetime, timezone
from s3_db_sync import s3_db_wrapper
from services.monthly_report_service import build_monthly_report


LOCAL_DEV = os.environ.get("LOCAL_DEV") == "1"

if LOCAL_DEV:
    report = build_monthly_report(year_month=year_month)
else:
    with s3_db_wrapper():
        report = build_monthly_report(year_month=year_month)


lambda_client = boto3.client("lambda")

def get_current_month_pnl():
    fn = os.environ.get("MONTHLY_PNL_FUNCTION_NAME", "lambda_monthly_pnl")

    # Use UTC for deterministic behavior; change if you use a business timezone.
    now = datetime.now(timezone.utc)
    year = now.year
    month = now.month

    payload = {"year": year, "month": month}

    resp = lambda_client.invoke(
        FunctionName=fn,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode("utf-8"),
    )

    raw = resp["Payload"].read()
    data = json.loads(raw.decode("utf-8")) if raw else {}

    # If lambda_monthly_pnl returns API Gateway style {statusCode, body}
    if isinstance(data, dict) and "body" in data:
        body = data["body"]
        if isinstance(body, str):
            body = json.loads(body) if body else {}
        return body

    return data


import json
from datetime import datetime, timezone

def lambda_handler(event, context):
    event = event or {}
    year_month = event.get("year_month")  # optional override: "2026-08"

    try:
        with s3_db_wrapper():
            report = build_monthly_report(year_month=year_month)

            # Enhance response: include current month's month_pnl
            try:
                now = datetime.now(timezone.utc)
                report["current_month"] = {
                    "year": now.year,
                    "month": now.month,
                    "month_pnl": get_current_month_pnl(),
                }
            except Exception as e:
                # Don't fail the whole report if month_pnl fails
                report["current_month"] = {"error": str(e)}

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(report, indent=2, default=str),
        }

    except Exception as e:
        print(f"consolidated_monthly_report error: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }
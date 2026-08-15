import json
import os
import calendar
from datetime import datetime, timezone
from crud_db import get_monthly_pnl

from s3_db_sync import s3_db_wrapper
from services.monthly_report_service import build_monthly_report

LOCAL_DEV = os.environ.get("LOCAL_DEV") == "1"


def lambda_handler(event, context):
    event = event or {}

    # Optional override: "2026-08". If not provided, default to current UTC month.
    year_month = event.get("year_month")
    if not year_month:
        year_month = datetime.now(timezone.utc).strftime("%Y-%m")

    try:
        # Only use the S3<->EFS wrapper in Lambda; allow local dev to run without it.
        if LOCAL_DEV:
            report = build_monthly_report(year_month=year_month)
        else:
            with s3_db_wrapper():
                report = build_monthly_report(year_month=year_month)

 


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
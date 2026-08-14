# lambda_consolidated_monthly_report.py
import json

from s3_db_sync import s3_db_wrapper
from services.monthly_report_service import build_monthly_report


def lambda_handler(event, context):
    event = event or {}
    year_month = event.get("year_month")  # optional override: "2026-08"

    try:
        with s3_db_wrapper():
            report = build_monthly_report(year_month=year_month)

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(report, indent=2),
        }

    except Exception as e:
        print(f"consolidated_monthly_report error: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }
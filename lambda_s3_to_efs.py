import json
from s3_db_sync import sync_s3_to_efs, sync_efs_to_s3


def lambda_handler(event, context):
    """
    Lambda that copies mystocks.db between S3 and EFS.

    Event payload:
      - {"direction": "s3_to_efs"}  (default) — download from S3 to EFS
      - {"direction": "efs_to_s3"}            — upload from EFS to S3

    Triggered by:
      - GitHub Actions (after deploying new schema)
      - Manual invocation from AWS Console
      - Scheduled EventBridge rule (optional)
    """
    direction = event.get("direction", "s3_to_efs") if event else "s3_to_efs"

    try:
        if direction == "efs_to_s3":
            result = sync_efs_to_s3()
            message = "✅ mystocks.db copied from EFS to S3"
        else:
            result = sync_s3_to_efs()
            message = "✅ mystocks.db copied from S3 to EFS"

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": message,
                "direction": direction,
                **result,
            })
        }

    except FileNotFoundError as e:
        print(f"❌ Sync failed (file not found): {e}")
        return {
            "statusCode": 404,
            "body": json.dumps({"error": str(e), "direction": direction})
        }

    except Exception as e:
        print(f"❌ Sync failed: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e), "direction": direction})
        }
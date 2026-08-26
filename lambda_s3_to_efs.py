import json
from s3_db_sync import sync_s3_to_efs


def lambda_handler(event, context):
    """
    Lambda that copies mystocks.db from S3 to EFS.
    
    Triggered by:
      - GitHub Actions (after deploying new schema)
      - Manual invocation from AWS Console
      - Scheduled EventBridge rule (optional)
    """
    try:
        result = sync_s3_to_efs()

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "✅ mystocks.db copied from S3 to EFS",
                "destination": result["destination"],
                "size_bytes": result["size_bytes"],
            })
        }

    except Exception as e:
        print(f"❌ S3-to-EFS sync failed: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
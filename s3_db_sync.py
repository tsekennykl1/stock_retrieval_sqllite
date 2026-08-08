import boto3
import os
from contextlib import contextmanager

BUCKET_NAME = "s3general-148535751717-ap-east-1-an"
S3_KEY = "mystocks.db"
LOCAL_DB_PATH = f"/tmp/{S3_KEY}"

# Force SQLite functions to use the /tmp path when this is imported
os.environ["DB_PATH"] = LOCAL_DB_PATH

@contextmanager
def s3_db_wrapper():
    """Context manager to sync SQLite DB from/to S3 for Lambda."""
    
    # Check if we are actually running inside AWS Lambda
    is_lambda = "AWS_LAMBDA_FUNCTION_NAME" in os.environ
    
    if is_lambda:
        s3_client = boto3.client("s3", region_name="ap-east-1")
        print(f"⬇️ Downloading {S3_KEY} from S3...")
        try:
            s3_client.download_file(BUCKET_NAME, S3_KEY, LOCAL_DB_PATH)
        except Exception as e:
            print(f"⚠️ S3 Download failed (might be a new DB): {e}")

    try:
        # Yield control back to the main lambda handler to execute all CRUD functions
        yield 
        
    finally:
        # Upload the modified DB back to S3 after the CRUD functions finish
        if is_lambda and os.path.exists(LOCAL_DB_PATH):
            print(f"⬆️ Uploading {S3_KEY} back to S3...")
            s3_client.upload_file(LOCAL_DB_PATH, BUCKET_NAME, S3_KEY)
import boto3
import os

S3_KEY = "mystocks.db"

def sync_s3_to_efs():
    """Download mystocks.db from S3 to EFS mount."""
    bucket = os.environ.get("S3_BUCKET_NAME","s3general-148535751717-ap-east-1-an"))
    efs_path = os.environ.get("EFS_PATH", "/mnt/efs")

    if not bucket:
        raise ValueError("S3_BUCKET_NAME environment variable not set")

    dest = os.path.join(efs_path, S3_KEY)
    s3_client = boto3.client("s3")

    print(f"⬇️ Downloading s3://{bucket}/{S3_KEY} → {dest}")
    s3_client.download_file(bucket, S3_KEY, dest)
    print(f"✅ Database synced to EFS: {dest}")

    # Return file size for confirmation
    file_size = os.path.getsize(dest)
    return {"destination": dest, "size_bytes": file_size}
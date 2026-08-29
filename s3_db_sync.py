import boto3
import os

S3_KEY = "mystocks.db"


def sync_s3_to_efs():
    """Download mystocks.db from S3 to EFS mount."""
    bucket = os.environ.get("S3_BUCKET_NAME", "s3general-148535751717-ap-east-1-an")
    efs_path = os.environ.get("EFS_PATH", "/mnt/efs")

    if not bucket:
        raise ValueError("S3_BUCKET_NAME environment variable not set")

    dest = os.path.join(efs_path, S3_KEY)
    s3_client = boto3.client("s3")

    print(f"⬇️ Downloading s3://{bucket}/{S3_KEY} → {dest}")
    s3_client.download_file(bucket, S3_KEY, dest)
    print(f"✅ Database synced to EFS: {dest}")

    file_size = os.path.getsize(dest)
    return {"destination": dest, "size_bytes": file_size}


def sync_efs_to_s3():
    """Upload mystocks.db from EFS mount to S3."""
    bucket = os.environ.get("S3_BUCKET_NAME", "s3general-148535751717-ap-east-1-an")
    efs_path = os.environ.get("EFS_PATH", "/mnt/efs")

    if not bucket:
        raise ValueError("S3_BUCKET_NAME environment variable not set")

    source = os.path.join(efs_path, S3_KEY)

    if not os.path.exists(source):
        raise FileNotFoundError(f"Database not found at {source}")

    file_size = os.path.getsize(source)
    s3_client = boto3.client("s3")

    print(f"⬆️ Uploading {source} → s3://{bucket}/{S3_KEY}")
    s3_client.upload_file(source, bucket, S3_KEY)
    print(f"✅ Database synced to S3: s3://{bucket}/{S3_KEY}")

    return {"source": source, "bucket": bucket, "key": S3_KEY, "size_bytes": file_size}
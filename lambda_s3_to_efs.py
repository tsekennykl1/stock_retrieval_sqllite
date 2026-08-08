import boto3
import os
import shutil

S3_BUCKET = os.environ.get("S3_BUCKET_NAME")
EFS_PATH = "/mnt/efs"

def lambda_handler(event, context):
    s3 = boto3.client("s3")

    files_to_copy = [
        "mystocks.db",
        "crud_db.py",
    ]

    for filename in files_to_copy:
        local_path = f"/tmp/{filename}"
        efs_path = f"{EFS_PATH}/{filename}"

        print(f"Downloading s3://{S3_BUCKET}/{filename} → {local_path}")
        s3.download_file(S3_BUCKET, filename, local_path)

        print(f"Copying {local_path} → {efs_path}")
        shutil.copy2(local_path, efs_path)

        print(f"✅ {filename} copied to EFS")

    return {
        "statusCode": 200,
        "body": "Files copied from S3 to EFS successfully"
    }

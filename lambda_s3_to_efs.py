import boto3
import os
import shutil

s3 = boto3.client('s3')

S3_BUCKET = os.environ['S3_BUCKET_NAME']
EFS_PATH  = os.environ['EFS_PATH']          # /mnt/efs

def lambda_handler(event, context):
    filename  = event.get('filename', 'mystocks.db')
    tmp_path  = f'/tmp/{filename}'           # Lambda always has write access here
    efs_path  = f'{EFS_PATH}/{filename}'     # /mnt/efs/mystocks.db

    print(f"⬇️  Downloading s3://{S3_BUCKET}/{filename} → {tmp_path}")
    s3.download_file(S3_BUCKET, filename, tmp_path)

    print(f"📁 Copying {tmp_path} → {efs_path}")
    # Ensure target directory exists
    os.makedirs(os.path.dirname(efs_path), exist_ok=True)

    # Use os.replace for atomic write (safer than shutil.copy2)
    shutil.copy2(tmp_path, efs_path)
    os.chmod(efs_path, 0o644)               # rw-r--r--

    # Clean up tmp
    os.remove(tmp_path)

    print(f"✅ Successfully copied {filename} to EFS at {efs_path}")
    return {
        'statusCode': 200,
        'body': f'Successfully copied {filename} to {efs_path}'
    }

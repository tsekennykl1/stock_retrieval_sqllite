import boto3
import os
import shutil
import stat

s3 = boto3.client('s3')

S3_BUCKET = "s3general-148535751717-ap-east-1-an"
EFS_PATH  = "/mnt/efs"  # /mnt/efs

def lambda_handler(event, context):

    # ── One-time init: fix directory ownership ──────────────────────────
    if event.get('init'):
        print(f"🔧 Init mode: fixing permissions on {EFS_PATH}")
        try:
            os.makedirs(EFS_PATH, exist_ok=True)
            os.chmod(EFS_PATH, 0o777)
            print(f"✅ chmod 777 applied to {EFS_PATH}")
            stat_info = os.stat(EFS_PATH)
            print(f"   UID={stat_info.st_uid} GID={stat_info.st_gid} mode={oct(stat_info.st_mode)}")
        except Exception as e:
            print(f"⚠️  chmod failed (may need root): {e}")
        return {'statusCode': 200, 'body': 'Init complete'}

    # ── Normal mode: copy file from S3 to EFS ───────────────────────────
    filename  = event.get('filename', 'mystocks.db')
    tmp_path  = f'/tmp/{filename}'
    efs_path  = f'{EFS_PATH}/{filename}'

    print(f"⬇️  Downloading s3://{S3_BUCKET}/{filename} → {tmp_path}")
    s3.download_file(S3_BUCKET, filename, tmp_path)

    print(f"📁 EFS mount stat: {os.stat(EFS_PATH)}")
    print(f"📁 Copying {tmp_path} → {efs_path}")

    shutil.copy2(tmp_path, efs_path)
    os.chmod(efs_path, 0o644)
    os.remove(tmp_path)

    print(f"✅ Successfully copied {filename} to {efs_path}")
    return {
        'statusCode': 200,
        'body': f'Successfully copied {filename} to {efs_path}'
    }
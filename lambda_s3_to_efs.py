import boto3
import os
import shutil
import stat

s3 = boto3.client('s3')

S3_BUCKET = os.environ['S3_BUCKET_NAME']
EFS_PATH  = os.environ['EFS_PATH']   # /mnt/efs

def lambda_handler(event, context):

    # ── Diagnostics: always print EFS mount state ────────────────────
    print(f"🔍 Lambda UID={os.getuid()} GID={os.getgid()}")
    print(f"🔍 EFS_PATH={EFS_PATH} exists={os.path.exists(EFS_PATH)}")

    if os.path.exists(EFS_PATH):
        st = os.stat(EFS_PATH)
        print(f"🔍 EFS dir → UID={st.st_uid} GID={st.st_gid} mode={oct(st.st_mode)}")
        print(f"🔍 Contents: {os.listdir(EFS_PATH)}")
    else:
        print("⚠️  EFS_PATH does not exist yet")

    # ── Init mode: fix ownership ──────────────────────────────────────
    if event.get('init'):
        print(f"🔧 Init: attempting chown + chmod on {EFS_PATH}")
        try:
            os.chown(EFS_PATH, 1000, 1000)
            os.chmod(EFS_PATH, 0o777)
            st = os.stat(EFS_PATH)
            print(f"✅ After fix → UID={st.st_uid} GID={st.st_gid} mode={oct(st.st_mode)}")
        except Exception as e:
            print(f"❌ chown/chmod failed: {e}")
        return {'statusCode': 200, 'body': 'Init complete'}

    # ── Normal mode: copy file from S3 to EFS ────────────────────────
    filename  = event.get('filename', 'mystocks.db')
    tmp_path  = f'/tmp/{filename}'
    efs_path  = f'{EFS_PATH}/{filename}'

    print(f"⬇️  Downloading s3://{S3_BUCKET}/{filename} → {tmp_path}")
    s3.download_file(S3_BUCKET, filename, tmp_path)
    print(f"✅ Downloaded to {tmp_path}, size={os.path.getsize(tmp_path)}")

    print(f"📁 Copying {tmp_path} → {efs_path}")
    shutil.copy2(tmp_path, efs_path)
    os.chmod(efs_path, 0o644)
    os.remove(tmp_path)

    print(f"✅ Successfully copied {filename} to {efs_path}")
    return {
        'statusCode': 200,
        'body': f'Successfully copied {filename} to {efs_path}'
    }

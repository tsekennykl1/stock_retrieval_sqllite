import boto3
import os
import shutil

s3 = boto3.client("s3")

def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} environment variable is required")
    return value

def lambda_handler(event, context):
    # Read env vars at runtime (not import time)
    s3_bucket = _require_env("S3_BUCKET_NAME")
    efs_base  = _require_env("EFS_PATH")  # e.g. /mnt/efs

    # ── Diagnostics: always print EFS mount state ────────────────────
    print(f"🔍 Lambda UID={os.getuid()} GID={os.getgid()}")
    print(f"🔍 EFS_PATH={efs_base} exists={os.path.exists(efs_base)}")

    if os.path.exists(efs_base):
        st = os.stat(efs_base)
        print(f"🔍 EFS dir → UID={st.st_uid} GID={st.st_gid} mode={oct(st.st_mode)}")
        print(f"🔍 Contents: {os.listdir(efs_base)}")
    else:
        print("⚠️  EFS_PATH does not exist yet")

    # ── Init mode: fix ownership ─────────────────────────────────────
    if event.get("init"):
        print(f"🔧 Init: attempting chown + chmod on {efs_base}")
        try:
            os.chown(efs_base, 1000, 1000)
            os.chmod(efs_base, 0o777)
            st = os.stat(efs_base)
            print(f"✅ After fix → UID={st.st_uid} GID={st.st_gid} mode={oct(st.st_mode)}")
        except Exception as e:
            print(f"❌ chown/chmod failed: {e}")
        return {"statusCode": 200, "body": "Init complete"}

    # ── Normal mode: copy file from S3 to EFS ────────────────────────
    filename = event.get("filename", "mystocks.db")
    tmp_path = f"/tmp/{filename}"
    efs_path = f"{efs_base.rstrip('/')}/{filename}"

    print(f"⬇️  Downloading s3://{s3_bucket}/{filename} → {tmp_path}")
    s3.download_file(s3_bucket, filename, tmp_path)
    print(f"✅ Downloaded to {tmp_path}, size={os.path.getsize(tmp_path)}")

    print(f"📁 Copying {tmp_path} → {efs_path}")
    shutil.copy2(tmp_path, efs_path)
    os.chmod(efs_path, 0o644)
    os.remove(tmp_path)

    print(f"✅ Successfully copied {filename} to {efs_path}")
    return {"statusCode": 200, "body": f"Successfully copied {filename} to {efs_path}"}
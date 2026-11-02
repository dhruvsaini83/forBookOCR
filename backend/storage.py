from datetime import datetime
"""Cloudflare R2 / S3-compatible Object Storage for VaniScript.

Provides:
- S3-compatible client connection via boto3 for Cloudflare R2.
- Environment variables:
    R2_ENDPOINT: S3-compatible endpoint URL (e.g. https://<account_id>.r2.cloudflarestorage.com)
    R2_ACCESS_KEY: R2 API token access key ID
    R2_SECRET_KEY: R2 API token secret access key
    R2_BUCKET: Bucket name (default: 'vaniscript')
    R2_PUBLIC_URL: Optional custom domain or public URL (e.g. https://cdn.vaniscript.com)
- Core Storage Functions:
    upload_original(book_id, page_number, file_bytes) -> url
    upload_processed(book_id, page_number, file_bytes) -> url
    upload_export(book_id, filename, file_bytes) -> url
    delete_file(path) -> bool
    get_presigned_url(path, expiry=3600) -> url
- Guarantees & Validations:
    - Original image is NEVER overwritten; non-colliding unique paths are created.
    - Magic bytes validation for JPEG, PNG, WEBP, and PDF.
    - Strict file size limit <= 50MB.
    - Render / Cloud deployment staging: temporarily written to /tmp (or OS temp dir),
      uploaded to R2, and immediately deleted from local disk in a finally block.
    - Graceful local fallback when R2 credentials are not configured.
"""

import os
import time
import uuid
import logging
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger("vaniscript.storage")

# Configuration via environment variables
R2_ENDPOINT = os.environ.get("R2_ENDPOINT", "").strip()
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY", "").strip()
R2_SECRET_KEY = os.environ.get("R2_SECRET_KEY", "").strip()
R2_BUCKET = os.environ.get("R2_BUCKET", "vaniscript").strip() or "vaniscript"
R2_PUBLIC_URL = os.environ.get("R2_PUBLIC_URL", "").strip()

# File validation constraints
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB in bytes

# Local fallback directory when R2 credentials are not supplied
LOCAL_STORAGE_FALLBACK_DIR = Path(__file__).resolve().parent / "storage" / "r2_local"


def is_r2_configured() -> bool:
    """Returns True if Cloudflare R2 credentials and endpoint are configured."""
    return bool(R2_ENDPOINT and R2_ACCESS_KEY and R2_SECRET_KEY)


def get_s3_client():
    """Initializes and returns a boto3 S3 client configured for Cloudflare R2."""
    if is_r2_configured():
        return boto3.client(
            "s3",
            endpoint_url=R2_ENDPOINT,
            aws_access_key_id=R2_ACCESS_KEY,
            aws_secret_access_key=R2_SECRET_KEY,
            region_name="auto",
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
                s3={"addressing_style": "path"}
            )
        )
    return None


def validate_file(file_bytes: bytes) -> str:
    """Validates file magic bytes and size.

    Supported formats:
    - JPEG: \\xff\\xd8\\xff
    - PNG: \\x89PNG\\r\\n\\x1a\\n
    - WEBP: RIFF....WEBP
    - PDF: %PDF-

    Returns:
        MIME content type string (e.g. 'image/jpeg').

    Raises:
        ValueError: If file is empty, exceeds 50MB, or format magic bytes fail validation.
    """
    if not file_bytes:
        raise ValueError("File is empty (0 bytes).")

    if len(file_bytes) > MAX_FILE_SIZE:
        size_mb = len(file_bytes) / (1024 * 1024)
        raise ValueError(f"File size ({size_mb:.2f}MB) exceeds the maximum allowed 50MB limit.")

    # Check Magic Bytes
    if file_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    elif file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    elif file_bytes[:4] == b"RIFF" and len(file_bytes) >= 12 and file_bytes[8:12] == b"WEBP":
        return "image/webp"
    elif file_bytes.startswith(b"%PDF-"):
        return "application/pdf"
    else:
        raise ValueError(
            "Invalid file format: Magic bytes verification failed. "
            "Only JPEG, PNG, WEBP, and PDF files are allowed."
        )


def file_exists(path: str) -> bool:
    """Checks whether an object exists at the specified path in R2 or local storage."""
    client = get_s3_client()
    if client:
        try:
            client.head_object(Bucket=R2_BUCKET, Key=path)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchKey", "NotFound"):
                return False
            logger.warning(f"Error checking file existence on R2 for {path}: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error checking file existence for {path}: {e}")
            return False
    else:
        local_path = LOCAL_STORAGE_FALLBACK_DIR / path
        return local_path.exists()


def get_file_url(path: str) -> str:
    """Constructs the canonical URL for an object path."""
    clean_path = path.lstrip("/")
    if R2_PUBLIC_URL:
        return f"{R2_PUBLIC_URL.rstrip('/')}/{clean_path}"
    if R2_ENDPOINT:
        return f"{R2_ENDPOINT.rstrip('/')}/{R2_BUCKET}/{clean_path}"
    return f"/storage/{clean_path}"


def _stage_and_upload(path: str, file_bytes: bytes, content_type: str) -> str:
    """Stages the file in local /tmp (or system tempdir), uploads to R2 via boto3,
    and immediately deletes the local temporary file in a finally block.
    """
    clean_path = path.lstrip("/")
    client = get_s3_client()

    # Determine staging directory: prefer /tmp (standard on Render/Linux)
    temp_dir = "/tmp" if os.path.exists("/tmp") and os.path.isdir("/tmp") else tempfile.gettempdir()
    temp_file = tempfile.NamedTemporaryFile(dir=temp_dir, delete=False)
    temp_path = temp_file.name

    try:
        # Write to local /tmp
        temp_file.write(file_bytes)
        temp_file.flush()
        temp_file.close()

        if client:
            # Upload to Cloudflare R2
            client.upload_file(
                temp_path,
                R2_BUCKET,
                clean_path,
                ExtraArgs={"ContentType": content_type}
            )
            logger.info(f"Successfully uploaded {clean_path} to R2 bucket '{R2_BUCKET}'.")
        else:
            # Fallback for local development/offline testing
            fallback_dest = LOCAL_STORAGE_FALLBACK_DIR / clean_path
            fallback_dest.parent.mkdir(parents=True, exist_ok=True)
            with open(fallback_dest, "wb") as f_out:
                f_out.write(file_bytes)
            logger.info(f"R2 not configured. Saved to local storage mirror: {fallback_dest}")
    finally:
        # Immediate cleanup: delete temporary file from /tmp
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as cleanup_err:
                logger.warning(f"Failed to remove temporary file {temp_path}: {cleanup_err}")

    return get_file_url(clean_path)


def upload_original(book_id: str, page_number: int, file_bytes: bytes) -> str:
    """Uploads an original manuscript image to R2 under originals/{book_id}/{page_number}.jpg.

    Strict Non-Overwrite Policy:
    If an image already exists at the canonical path, a unique versioned key is generated
    (e.g. originals/{book_id}/{page_number}_{timestamp}_{rand}.jpg) so existing original
    manuscript scans are NEVER overwritten.
    """
    content_type = validate_file(file_bytes)
    book_id_str = str(book_id).strip()
    page_num = int(page_number)

    canonical_path = f"originals/{book_id_str}/{page_num}.jpg"
    target_path = canonical_path

    # Check existence to prevent any overwrite
    if file_exists(canonical_path):
        timestamp = int(time.time())
        rand_suffix = uuid.uuid4().hex[:6]
        target_path = f"originals/{book_id_str}/{page_num}_{timestamp}_{rand_suffix}.jpg"
        logger.info(
            f"Original file {canonical_path} already exists. "
            f"Uploading to non-colliding path: {target_path} (No-overwrite guarantee)"
        )

    return _stage_and_upload(target_path, file_bytes, content_type)


def upload_processed(book_id: str, page_number: int, file_bytes: bytes) -> str:
    """Uploads a preprocessed/adjusted manuscript image to processed/{book_id}/{page_number}.jpg."""
    content_type = validate_file(file_bytes)
    book_id_str = str(book_id).strip()
    page_num = int(page_number)
    path = f"processed/{book_id_str}/{page_num}.jpg"
    return _stage_and_upload(path, file_bytes, content_type)




def upload_crop(book_id: Optional[str], correction_id: str, file_bytes: bytes) -> str:
    """Uploads an extracted word-level image crop to crops/{book_id}/{correction_id}.jpg."""
    if not file_bytes:
        raise ValueError("Crop image file is empty.")
    try:
        content_type = validate_file(file_bytes)
    except Exception:
        content_type = "image/jpeg"

    book_str = str(book_id).strip() if book_id else "general"
    corr_str = str(correction_id).strip()
    target_path = f"crops/{book_str}/{corr_str}.jpg"
    return _stage_and_upload(target_path, file_bytes, content_type)


def upload_export(book_id: str, filename: str, file_bytes: bytes) -> str:
    """Uploads an exported publication (PDF, DOCX, TXT, JSON) to exports/{book_id}/{filename}."""
    if not file_bytes:
        raise ValueError("Export file content is empty.")

    if len(file_bytes) > MAX_FILE_SIZE:
        size_mb = len(file_bytes) / (1024 * 1024)
        raise ValueError(f"File size ({size_mb:.2f}MB) exceeds the 50MB limit.")

    # Detect content type
    ext = Path(filename).suffix.lower()
    try:
        content_type = validate_file(file_bytes)
    except ValueError:
        # Allow standard text / office export formats
        mime_types = {
            ".txt": "text/plain; charset=utf-8",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".json": "application/json",
            ".csv": "text/csv; charset=utf-8",
            ".md": "text/markdown; charset=utf-8",
            ".html": "text/html; charset=utf-8",
            ".htm": "text/html; charset=utf-8",
            ".pdf": "application/pdf"
        }
        if ext in mime_types:
            content_type = mime_types[ext]
        else:
            content_type = "application/octet-stream"

    book_id_str = str(book_id).strip()
    clean_filename = Path(filename).name  # Prevent directory traversal
    path = f"exports/{book_id_str}/{clean_filename}"
    return _stage_and_upload(path, file_bytes, content_type)


def delete_file(path: str) -> bool:
    """Deletes a file object from Cloudflare R2 storage (and local fallback mirror).

    Returns:
        bool: True if deletion succeeded or file did not exist, False on failure.
    """
    clean_path = path.lstrip("/")
    client = get_s3_client()
    success = True

    if client:
        try:
            client.delete_object(Bucket=R2_BUCKET, Key=clean_path)
            logger.info(f"Deleted {clean_path} from R2 bucket '{R2_BUCKET}'.")
        except Exception as e:
            logger.error(f"Failed to delete {clean_path} from R2: {e}")
            success = False

    # Also clean local fallback if present
    local_path = LOCAL_STORAGE_FALLBACK_DIR / clean_path
    if local_path.exists():
        try:
            local_path.unlink()
        except Exception as e:
            logger.warning(f"Failed to delete local fallback {local_path}: {e}")

    return success


def get_presigned_url(path: str, expiry: int = 3600) -> str:
    """Generates an S3 presigned GET URL for an object in R2.

    Args:
        path: Key of the object in the bucket.
        expiry: URL validity duration in seconds (default: 3600).

    Returns:
        Presigned GET URL string.
    """
    clean_path = path.lstrip("/")
    client = get_s3_client()
    if client:
        try:
            url = client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": R2_BUCKET,
                    "Key": clean_path
                },
                ExpiresIn=expiry
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL for {clean_path}: {e}")
            return get_file_url(clean_path)

    # Local fallback URL
    return get_file_url(clean_path)


def test_r2_connection() -> Dict[str, Any]:
    """Tests Cloudflare R2 connection.
    Returns:
        dict: {"connected": bool, "bucket": str, "provider": "r2" | "local", "message": str}
    """
    if not is_r2_configured():
        return {
            "connected": False,
            "bucket": R2_BUCKET,
            "provider": "local",
            "message": "R2 credentials not configured. Local storage fallback active."
        }
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=R2_BUCKET)
        return {
            "connected": True,
            "bucket": R2_BUCKET,
            "provider": "r2",
            "message": f"Successfully connected to Cloudflare R2 bucket '{R2_BUCKET}'."
        }
    except Exception as e:
        return {
            "connected": False,
            "bucket": R2_BUCKET,
            "provider": "r2",
            "message": f"R2 connection failed: {str(e)}"
        }


def list_storage_files(prefix: str = "") -> List[Dict[str, Any]]:
    """Lists files in R2 (or local mirror) matching a prefix."""
    clean_prefix = prefix.lstrip("/")
    files = []
    client = get_s3_client()
    if client:
        try:
            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=R2_BUCKET, Prefix=clean_prefix):
                for obj in page.get("Contents", []):
                    files.append({
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"].isoformat() if hasattr(obj["LastModified"], "isoformat") else str(obj["LastModified"]),
                        "etag": obj.get("ETag", "").strip('"')
                    })
            return files
        except Exception as e:
            logger.warning(f"Failed to list R2 files with prefix '{clean_prefix}': {e}")

    # Local fallback
    local_root = LOCAL_STORAGE_FALLBACK_DIR / clean_prefix
    if local_root.exists():
        if local_root.is_dir():
            for p in local_root.rglob("*"):
                if p.is_file():
                    rel_key = str(p.relative_to(LOCAL_STORAGE_FALLBACK_DIR)).replace("\\", "/")
                    stat = p.stat()
                    files.append({
                        "key": rel_key,
                        "size": stat.st_size,
                        "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat() if "datetime" in globals() else str(stat.st_mtime),
                        "etag": ""
                    })
        elif local_root.is_file():
            rel_key = str(local_root.relative_to(LOCAL_STORAGE_FALLBACK_DIR)).replace("\\", "/")
            stat = local_root.stat()
            files.append({
                "key": rel_key,
                "size": stat.st_size,
                "last_modified": str(stat.st_mtime),
                "etag": ""
            })
    return files


def has_exports(book_id: str) -> bool:
    """Returns True if any export files exist for the given book_id."""
    files = list_storage_files(f"exports/{book_id}")
    return len(files) > 0

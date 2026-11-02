"""Unit and integration tests for Cloudflare R2 / S3 Storage module (backend/storage.py).

Tests:
1. File validation with magic bytes: JPEG, PNG, WEBP, PDF.
2. File validation rejections: Invalid magic bytes, empty bytes, size > 50MB.
3. upload_original canonical path and non-overwrite guarantee.
4. upload_processed pathing.
5. upload_export with PDF and document formats.
6. delete_file cleanup.
7. get_presigned_url generation.
8. Local /tmp temp file cleanup in finally block.
9. Boto3 S3 client interaction with mocked S3.
"""

import sys
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError
import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import storage

# Sample valid byte headers
SAMPLE_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100
SAMPLE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
SAMPLE_WEBP = b"RIFF\x20\x00\x00\x00WEBPVP8 " + b"\x00" * 100
SAMPLE_PDF = b"%PDF-1.4\n%header\n" + b"\x00" * 100


@pytest.fixture(autouse=True)
def cleanup_local_fallback():
    """Cleans up local fallback test directory before and after each test."""
    test_dir = storage.LOCAL_STORAGE_FALLBACK_DIR
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)
    yield
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)


def test_file_validation_valid_formats():
    """Tests that JPEG, PNG, WEBP, and PDF pass magic bytes check."""
    assert storage.validate_file(SAMPLE_JPEG) == "image/jpeg"
    assert storage.validate_file(SAMPLE_PNG) == "image/png"
    assert storage.validate_file(SAMPLE_WEBP) == "image/webp"
    assert storage.validate_file(SAMPLE_PDF) == "application/pdf"


def test_file_validation_empty_bytes():
    """Tests that empty file raises ValueError."""
    with pytest.raises(ValueError, match="empty"):
        storage.validate_file(b"")


def test_file_validation_invalid_magic_bytes():
    """Tests that arbitrary or corrupt bytes raise ValueError."""
    invalid_bytes = b"This is plain ASCII text not an image"
    with pytest.raises(ValueError, match="Magic bytes verification failed"):
        storage.validate_file(invalid_bytes)

    exe_bytes = b"MZ\x90\x00\x03\x00\x00\x00"
    with pytest.raises(ValueError, match="Magic bytes verification failed"):
        storage.validate_file(exe_bytes)


def test_file_validation_size_limit():
    """Tests that files larger than 50MB are rejected."""
    oversized = b"\xff\xd8\xff" + b"0" * (50 * 1024 * 1024 + 10)
    with pytest.raises(ValueError, match="exceeds the maximum allowed 50MB limit"):
        storage.validate_file(oversized)


def test_upload_original_canonical_path():
    """Tests uploading an original image generates the canonical path."""
    book_id = "book_101"
    page_number = 1
    url = storage.upload_original(book_id, page_number, SAMPLE_JPEG)
    
    assert f"originals/{book_id}/{page_number}.jpg" in url
    assert storage.file_exists(f"originals/{book_id}/{page_number}.jpg") is True


def test_upload_original_never_overwrites():
    """CRITICAL: Tests that an existing original image is NEVER overwritten.
    A new upload for the same page generates a unique versioned path.
    """
    book_id = "book_protect"
    page_num = 5

    # First upload
    url_1 = storage.upload_original(book_id, page_num, SAMPLE_JPEG)
    assert url_1.endswith(f"originals/{book_id}/{page_num}.jpg")

    # Second upload for identical book_id and page_num
    url_2 = storage.upload_original(book_id, page_num, SAMPLE_JPEG)
    
    # Must NOT overwrite original path; must have unique version suffix
    assert url_2 != url_1
    assert f"originals/{book_id}/{page_num}_" in url_2
    assert url_2.endswith(".jpg")

    # Both files must coexist
    assert storage.file_exists(f"originals/{book_id}/{page_num}.jpg") is True
    path_2 = url_2.split("/storage/")[-1]
    assert storage.file_exists(path_2) is True


def test_upload_processed():
    """Tests upload_processed pathing."""
    book_id = "book_202"
    page_num = 2
    url = storage.upload_processed(book_id, page_num, SAMPLE_PNG)

    assert f"processed/{book_id}/{page_num}.jpg" in url
    assert storage.file_exists(f"processed/{book_id}/{page_num}.jpg") is True


def test_upload_export():
    """Tests upload_export with PDF and text exports."""
    book_id = "book_303"
    
    pdf_url = storage.upload_export(book_id, "ramcharitmanas_vol1.pdf", SAMPLE_PDF)
    assert f"exports/{book_id}/ramcharitmanas_vol1.pdf" in pdf_url
    assert storage.file_exists(f"exports/{book_id}/ramcharitmanas_vol1.pdf") is True

    txt_bytes = "श्री गणेशाय नमः\nसंपूर्ण ग्रंथ पाठ".encode("utf-8")
    txt_url = storage.upload_export(book_id, "book_text.txt", txt_bytes)
    assert f"exports/{book_id}/book_text.txt" in txt_url
    assert storage.file_exists(f"exports/{book_id}/book_text.txt") is True


def test_delete_file():
    """Tests delete_file successfully removes stored object."""
    book_id = "book_del"
    url = storage.upload_processed(book_id, 1, SAMPLE_PNG)
    path = f"processed/{book_id}/1.jpg"

    assert storage.file_exists(path) is True
    deleted = storage.delete_file(path)
    assert deleted is True
    assert storage.file_exists(path) is False


def test_staging_in_temp_and_immediate_cleanup():
    """Tests that local temp file is deleted immediately after upload."""
    temp_dir = tempfile.gettempdir()
    before_files = set(os.listdir(temp_dir))

    storage.upload_original("temp_check_book", 1, SAMPLE_JPEG)

    after_files = set(os.listdir(temp_dir))
    new_files = after_files - before_files
    lingering_temps = [f for f in new_files if f.startswith("tmp")]
    assert len(lingering_temps) == 0


def test_boto3_r2_mock_upload():
    """Tests interaction with boto3 client when R2 is configured."""
    mock_s3 = MagicMock()
    # Simulate head_object 404 (file does not exist initially)
    mock_s3.head_object.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
    )

    with patch.object(storage, "is_r2_configured", return_value=True), \
         patch.object(storage, "get_s3_client", return_value=mock_s3), \
         patch.object(storage, "R2_ENDPOINT", "https://mock-account.r2.cloudflarestorage.com"), \
         patch.object(storage, "R2_BUCKET", "vaniscript"), \
         patch.object(storage, "R2_PUBLIC_URL", "https://cdn.vaniscript.com"):

        # 1. upload_original
        url = storage.upload_original("boto_book", 10, SAMPLE_JPEG)
        assert url == "https://cdn.vaniscript.com/originals/boto_book/10.jpg"
        mock_s3.upload_file.assert_called_once()
        args, kwargs = mock_s3.upload_file.call_args
        assert args[1] == "vaniscript"
        assert args[2] == "originals/boto_book/10.jpg"
        assert kwargs["ExtraArgs"]["ContentType"] == "image/jpeg"

        # 2. get_presigned_url
        mock_s3.generate_presigned_url.return_value = "https://mock-presigned-url.com?token=xyz"
        presigned = storage.get_presigned_url("originals/boto_book/10.jpg", expiry=1800)
        assert presigned == "https://mock-presigned-url.com?token=xyz"
        mock_s3.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "vaniscript", "Key": "originals/boto_book/10.jpg"},
            ExpiresIn=1800
        )

        # 3. delete_file
        deleted = storage.delete_file("originals/boto_book/10.jpg")
        assert deleted is True
        mock_s3.delete_object.assert_called_once_with(
            Bucket="vaniscript",
            Key="originals/boto_book/10.jpg"
        )

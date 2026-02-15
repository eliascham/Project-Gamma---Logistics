import os
import uuid

import aiofiles
from fastapi import UploadFile

from app.config import Settings


async def save_upload(file: UploadFile, settings: Settings) -> tuple[str, str]:
    """Save an uploaded file to disk.

    Returns (stored_filename, full_file_path).
    """
    ext = os.path.splitext(file.filename or "upload")[1]
    stored_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(settings.upload_dir, stored_filename)

    os.makedirs(settings.upload_dir, exist_ok=True)

    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    return stored_filename, file_path


async def get_document_text(file_path: str) -> str:
    """Read document text from a file.

    For Phase 1, this does a simple text read. Future phases will add
    PDF parsing and OCR for scanned documents.
    """
    async with aiofiles.open(file_path, "r", errors="replace") as f:
        return await f.read()


def get_file_extension(filename: str) -> str:
    """Extract the file extension without the dot, lowercased."""
    _, ext = os.path.splitext(filename)
    return ext.lstrip(".").lower()


def get_mime_type(filename: str) -> str:
    """Map file extension to MIME type."""
    ext = get_file_extension(filename)
    mime_map = {
        "pdf": "application/pdf",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "tiff": "image/tiff",
        "tif": "image/tiff",
        "csv": "text/csv",
    }
    return mime_map.get(ext, "application/octet-stream")

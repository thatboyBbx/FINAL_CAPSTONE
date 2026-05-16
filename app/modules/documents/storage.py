import re
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile


BASE_STORAGE_DIR = Path("storage/documents")


def ensure_storage_dir() -> None:
    BASE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_filename(filename: str) -> str:
    sanitized = filename.strip().replace(" ", "_")
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "", sanitized)
    return sanitized or "document"


def generate_stored_filename(original_filename: str) -> str:
    safe_name = sanitize_filename(original_filename)
    path = Path(safe_name)
    stem = path.stem or "document"
    suffix = path.suffix or ""
    unique_id = uuid4().hex
    return f"{stem}_{unique_id}{suffix}"


def build_file_path(stored_filename: str) -> Path:
    ensure_storage_dir()
    return BASE_STORAGE_DIR / stored_filename


async def save_upload_file(file: UploadFile) -> dict:
    ensure_storage_dir()

    original_filename = file.filename or "document"
    stored_filename = generate_stored_filename(original_filename)
    file_path = build_file_path(stored_filename)

    content = await file.read()
    file_path.write_bytes(content)

    return {
        "original_filename": original_filename,
        "stored_filename": stored_filename,
        "file_path": str(file_path).replace("\\", "/"),
        "mime_type": file.content_type or "application/octet-stream",
        "file_size": len(content),
    }
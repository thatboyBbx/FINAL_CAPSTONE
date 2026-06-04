"""
app/modules/documents/file_store.py
=====================================
Production-safe file storage.

Responsibilities
----------------
- SHA-256 hashing for content identity and duplicate detection
- Magic-byte MIME validation (no external library required)
- Upload staging: files land in storage/staging/ before any DB write
- Atomic promotion to deterministic content-addressed final path
- Duplicate-on-disk detection (same hash → reuse existing file)

Path scheme
-----------
  storage/documents/{sha256[0:2]}/{sha256}{ext}   ← permanent, deterministic
  storage/staging/{uuid4}{ext}                    ← temporary

Do NOT import AI-pipeline modules from here.
"""
from __future__ import annotations

import hashlib
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Storage roots (relative to CWD, matching the convention in storage.py)
# ---------------------------------------------------------------------------

DOCUMENTS_ROOT = Path("storage/documents")
STAGING_ROOT = Path("storage/staging")

# ---------------------------------------------------------------------------
# MIME validation tables
# ---------------------------------------------------------------------------

# (magic prefix, canonical MIME produced by sniffing)
_MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"%PDF",                               "application/pdf"),
    (b"\xff\xd8\xff",                       "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n",                  "image/png"),
    (b"II*\x00",                            "image/tiff"),
    (b"MM\x00*",                            "image/tiff"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",  "application/msword"),  # OLE2 compound
    (b"PK\x03\x04",                         "application/zip"),     # DOCX/XLSX/etc.
    (b"PK\x05\x06",                         "application/zip"),
    (b"PK\x07\x08",                         "application/zip"),
]

# MIME types accepted for permanent storage.
ALLOWED_MIMES: frozenset[str] = frozenset({
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "text/csv",
    "image/jpeg",
    "image/png",
    "image/tiff",
})

# Office Open XML formats are ZIP archives; declared MIME identifies the subtype.
_ZIP_BASED_MIMES: frozenset[str] = frozenset({
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/zip",
})

# OLE2 compound document covers DOC, XLS, PPT (legacy binary formats).
_OLE2_MIMES: frozenset[str] = frozenset({
    "application/msword",
    "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
})

# Plain-text types carry no reliable magic bytes.
_TEXT_MIMES: frozenset[str] = frozenset({"text/plain", "text/csv"})


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class MimeValidationError(ValueError):
    """Raised when uploaded content fails MIME type validation."""


class DuplicateFileError(Exception):
    """Raised when the uploaded content is already stored under a Document record."""

    def __init__(self, existing_document_id: int, sha256: str) -> None:
        self.existing_document_id = existing_document_id
        self.sha256 = sha256
        super().__init__(
            f"Duplicate upload: document {existing_document_id} already contains "
            f"this content (sha256={sha256[:16]}…)"
        )


# ---------------------------------------------------------------------------
# Data transfer object for a staged file
# ---------------------------------------------------------------------------

@dataclass
class StagedFile:
    staging_path: Path
    original_filename: str
    sha256: str
    mime_type: str    # validated canonical MIME
    file_size: int
    extension: str    # e.g. ".pdf"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_dirs() -> None:
    DOCUMENTS_ROOT.mkdir(parents=True, exist_ok=True)
    STAGING_ROOT.mkdir(parents=True, exist_ok=True)


def _sniff_mime(content: bytes) -> str | None:
    """Return a canonical MIME type by inspecting magic bytes, or None."""
    for prefix, mime in _MAGIC_SIGNATURES:
        if content[: len(prefix)] == prefix:
            return mime
    return None


def _canonical_ext(original_filename: str) -> str:
    """Return lowercase file extension with leading dot, defaulting to '.bin'."""
    ext = Path(original_filename).suffix.lower()
    return ext if ext else ".bin"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def guess_mime_from_filename(filename: str) -> str:
    """Return a best-effort MIME type from the file extension. Falls back to application/octet-stream."""
    ext = Path(filename).suffix.lower()
    _EXT_MAP = {
        ".pdf":  "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc":  "application/msword",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls":  "application/vnd.ms-excel",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".ppt":  "application/vnd.ms-powerpoint",
        ".txt":  "text/plain",
        ".csv":  "text/csv",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png":  "image/png",
        ".tif":  "image/tiff",
        ".tiff": "image/tiff",
    }
    return _EXT_MAP.get(ext, "application/octet-stream")


def sanitize_filename(filename: str) -> str:
    """Return a filesystem-safe version of a filename, stripping path components."""
    import re
    name = Path(filename).name.strip().replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9._-]", "", name) or "document"


def compute_sha256(content: bytes) -> str:
    """Return the hex SHA-256 digest of content."""
    return hashlib.sha256(content).hexdigest()


def deterministic_path(sha256: str, extension: str) -> Path:
    """
    Return the canonical permanent path for a file identified by its content hash.

    Uses a two-character bucket prefix so no single directory exceeds ~16 million
    entries even with 4 billion files (4B / 256 = ~16M per bucket).
    """
    return DOCUMENTS_ROOT / sha256[:2] / f"{sha256}{extension}"


def resolve_existing_document_path(
    file_path: str | Path,
    *,
    stored_filename: str | None = None,
    original_filename: str | None = None,
    file_size: int | None = None,
) -> Path:
    """
    Return an existing path for a stored document.

    Older development uploads were saved directly under ``storage/documents``
    with a title-based filename. Newer rows point at deterministic hash bucket
    paths. This resolver lets legacy rows recover when the DB path is stale but
    the uploaded file is still present in the storage root.
    """
    path = Path(file_path)
    if path.exists():
        return path

    candidates: list[Path] = []
    if stored_filename:
        candidates.append(DOCUMENTS_ROOT / stored_filename)
        candidates.extend(DOCUMENTS_ROOT.glob(f"*/{stored_filename}"))

    if original_filename:
        stem = sanitize_filename(Path(original_filename).stem)
        ext = Path(original_filename).suffix.lower()
        if ext:
            candidates.extend(DOCUMENTS_ROOT.glob(f"{stem}_*{ext}"))
            candidates.extend(DOCUMENTS_ROOT.glob(f"*/{stem}_*{ext}"))

    if file_size:
        candidates.extend(p for p in DOCUMENTS_ROOT.glob("**/*") if p.is_file() and p.stat().st_size == file_size)

    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if candidate.exists() and candidate.is_file():
            if file_size is not None and candidate.stat().st_size != file_size:
                continue
            return candidate

    return path


def validate_mime(content: bytes, declared_mime: str) -> str:
    """
    Confirm that *content* is consistent with *declared_mime* and that the
    type is in the allowed set.

    Returns the normalised canonical MIME to store.
    Raises MimeValidationError on rejection.
    """
    declared = declared_mime.strip().lower().split(";")[0].strip()

    # Text types have no reliable magic bytes — trust the declaration.
    if declared in _TEXT_MIMES:
        return declared

    if declared not in ALLOWED_MIMES:
        raise MimeValidationError(
            f"MIME type '{declared}' is not accepted. "
            f"Allowed types: {', '.join(sorted(ALLOWED_MIMES))}"
        )

    sniffed = _sniff_mime(content)
    if sniffed is None:
        raise MimeValidationError(
            f"File content does not match any recognised format signature "
            f"(declared MIME: {declared})."
        )

    # ZIP container declared as a non-Office type → reject
    if sniffed == "application/zip" and declared not in _ZIP_BASED_MIMES:
        raise MimeValidationError(
            f"File is a ZIP archive but declared MIME '{declared}' is not a "
            "supported Office Open XML format."
        )

    # OLE2 compound document declared as a non-legacy type → reject
    if sniffed == "application/msword" and declared not in _OLE2_MIMES:
        raise MimeValidationError(
            f"File is an OLE2 compound document but declared MIME '{declared}' "
            "is not a supported legacy Office type."
        )

    # For all other types the sniffed family must match
    if sniffed not in ("application/zip", "application/msword") and sniffed != declared:
        raise MimeValidationError(
            f"File content was identified as '{sniffed}' but declared MIME is '{declared}'."
        )

    return declared


async def stage_upload(file: UploadFile) -> StagedFile:
    """
    Read *file*, validate its MIME type, hash its content, and write to staging.

    The caller MUST subsequently call either:
      - commit_staged(staged) → promote to permanent location
      - abort_staged(staged)  → delete staging file on failure
    """
    _ensure_dirs()

    original_filename = (file.filename or "document").strip() or "document"
    declared_mime = (file.content_type or "application/octet-stream").strip()

    content = await file.read()
    if not content:
        raise MimeValidationError("Uploaded file is empty.")

    canonical_mime = validate_mime(content, declared_mime)
    sha256 = compute_sha256(content)
    extension = _canonical_ext(original_filename)

    staging_path = STAGING_ROOT / f"{uuid4().hex}{extension}"
    staging_path.write_bytes(content)

    logger.debug(
        "stage_upload: staged '%s' → %s  sha256=%s  mime=%s  size=%d",
        original_filename, staging_path.name, sha256[:12], canonical_mime, len(content),
    )

    return StagedFile(
        staging_path=staging_path,
        original_filename=original_filename,
        sha256=sha256,
        mime_type=canonical_mime,
        file_size=len(content),
        extension=extension,
    )


def commit_staged(staged: StagedFile) -> Path:
    """
    Promote a staged file to its deterministic permanent location.

    If a file with the same content hash already exists on disk, the staging
    copy is discarded and the existing path is returned — content is never
    stored twice.

    Returns the final Path where the content lives.
    """
    dest = deterministic_path(staged.sha256, staged.extension)
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        try:
            staged.staging_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("commit_staged: could not remove staging file %s: %s", staged.staging_path, exc)
        logger.debug("commit_staged: dedup hit sha256=%s → %s", staged.sha256[:12], dest)
        return dest

    try:
        staged.staging_path.rename(dest)
    except OSError:
        # Cross-device rename: fall back to copy + delete
        shutil.copy2(staged.staging_path, dest)
        try:
            staged.staging_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("commit_staged: could not remove staging file after copy: %s", exc)

    logger.info("commit_staged: %s → %s", staged.staging_path.name, dest)
    return dest


def abort_staged(staged: StagedFile) -> None:
    """Remove a staged file without promoting it (cleanup on validation or DB failure)."""
    try:
        staged.staging_path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("abort_staged: could not remove staging file %s: %s", staged.staging_path, exc)

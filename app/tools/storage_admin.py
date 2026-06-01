"""
app/tools/storage_admin.py
===========================
Recovery and maintenance CLI for the file storage layer.

Usage (run from the EXPERIMENT/ directory):

    python -m app.tools.storage_admin verify
    python -m app.tools.storage_admin orphans
    python -m app.tools.storage_admin clean-orphans [--confirm]
    python -m app.tools.storage_admin clean-staging [--max-age-hours 24] [--confirm]
    python -m app.tools.storage_admin recover <file_path> --title "My Doc" --user-id 1

Commands
--------
verify
    Re-hash every Document that has a sha256_hash and confirm the stored file
    still matches.  Reports mismatches and missing files without altering anything.

orphans
    Walk storage/documents/ and storage/staging/ and list files that have no
    corresponding Document row.  Read-only; combine with clean-orphans to act.

clean-orphans
    Remove (or quarantine to storage/quarantine/) orphaned files found in
    storage/documents/.  Requires --confirm to delete; dry-run by default.

clean-staging
    Remove staging files older than --max-age-hours (default 24) hours.
    These are uploads that were never committed (process crashed mid-upload).
    Requires --confirm to delete; dry-run by default.

recover
    Register a file already on disk into the documents table.  Useful after a
    DB restore where files exist but their rows are gone.
    Computes the SHA-256, checks for an existing row, then inserts a new record.

Exit codes: 0 = OK, 1 = one or more issues found / errors, 2 = argument error.
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _db_file_paths(db) -> set[str]:
    """Return all file_path values stored in the documents table (normalised)."""
    from app.modules.documents.model import Document
    rows = db.query(Document.file_path).all()
    return {r[0].replace("\\", "/") for r in rows}


def _documents_root() -> Path:
    from app.modules.documents.file_store import DOCUMENTS_ROOT
    return DOCUMENTS_ROOT


def _staging_root() -> Path:
    from app.modules.documents.file_store import STAGING_ROOT
    return STAGING_ROOT


# ---------------------------------------------------------------------------
# Command: verify
# ---------------------------------------------------------------------------

def cmd_verify(args: argparse.Namespace) -> int:
    from app.core.db import SessionLocal
    from app.modules.documents.model import Document

    db = SessionLocal()
    try:
        docs = (
            db.query(Document)
            .filter(Document.sha256_hash.isnot(None))
            .all()
        )
    finally:
        db.close()

    if not docs:
        print("No documents with sha256_hash found — nothing to verify.")
        return 0

    issues = 0
    for doc in docs:
        path = Path(doc.file_path)
        if not path.exists():
            print(f"MISSING  id={doc.id}  path={doc.file_path}")
            issues += 1
            continue

        actual = _compute_sha256(path)
        if actual != doc.sha256_hash:
            print(
                f"MISMATCH id={doc.id}  path={doc.file_path}\n"
                f"         stored={doc.sha256_hash}\n"
                f"         actual={actual}"
            )
            issues += 1
        else:
            if args.verbose:
                print(f"OK       id={doc.id}  sha256={doc.sha256_hash[:16]}…")

    total = len(docs)
    ok = total - issues
    print(f"\nVerified {total} document(s): {ok} OK, {issues} issue(s).")
    return 1 if issues else 0


# ---------------------------------------------------------------------------
# Command: orphans
# ---------------------------------------------------------------------------

def cmd_orphans(args: argparse.Namespace) -> int:
    from app.core.db import SessionLocal

    db = SessionLocal()
    try:
        known_paths = _db_file_paths(db)
    finally:
        db.close()

    docs_root = _documents_root()
    orphans: list[Path] = []

    if docs_root.exists():
        for p in docs_root.rglob("*"):
            if p.is_file():
                normalised = str(p).replace("\\", "/")
                if normalised not in known_paths:
                    orphans.append(p)

    if not orphans:
        print("No orphaned files found in storage/documents/.")
        return 0

    print(f"Found {len(orphans)} orphaned file(s):")
    for p in orphans:
        print(f"  {p}  ({p.stat().st_size} bytes)")

    print(
        "\nRun  python -m app.tools.storage_admin clean-orphans --confirm"
        "  to remove them."
    )
    return 1


# ---------------------------------------------------------------------------
# Command: clean-orphans
# ---------------------------------------------------------------------------

def cmd_clean_orphans(args: argparse.Namespace) -> int:
    from app.core.db import SessionLocal

    db = SessionLocal()
    try:
        known_paths = _db_file_paths(db)
    finally:
        db.close()

    docs_root = _documents_root()
    quarantine_root = Path("storage/quarantine")

    orphans: list[Path] = []
    if docs_root.exists():
        for p in docs_root.rglob("*"):
            if p.is_file():
                normalised = str(p).replace("\\", "/")
                if normalised not in known_paths:
                    orphans.append(p)

    if not orphans:
        print("No orphaned files found — nothing to clean.")
        return 0

    print(f"Found {len(orphans)} orphaned file(s).")

    if not args.confirm:
        for p in orphans:
            print(f"  [dry-run] would remove {p}")
        print("\nAdd --confirm to actually remove files.")
        return 0

    quarantine_root.mkdir(parents=True, exist_ok=True)
    removed = 0
    for p in orphans:
        dest = quarantine_root / p.name
        try:
            p.rename(dest)
            print(f"  quarantined → {dest}")
            removed += 1
        except OSError as exc:
            print(f"  ERROR moving {p}: {exc}")

    print(f"\nQuarantined {removed}/{len(orphans)} file(s) to {quarantine_root}.")
    return 0


# ---------------------------------------------------------------------------
# Command: clean-staging
# ---------------------------------------------------------------------------

def cmd_clean_staging(args: argparse.Namespace) -> int:
    staging_root = _staging_root()
    if not staging_root.exists():
        print("Staging directory does not exist — nothing to clean.")
        return 0

    max_age_seconds = args.max_age_hours * 3600
    now = time.time()
    stale: list[Path] = []

    for p in staging_root.iterdir():
        if p.is_file():
            age = now - p.stat().st_mtime
            if age > max_age_seconds:
                stale.append(p)

    if not stale:
        print(f"No staging files older than {args.max_age_hours}h found.")
        return 0

    print(f"Found {len(stale)} stale staging file(s).")

    if not args.confirm:
        for p in stale:
            age_h = (now - p.stat().st_mtime) / 3600
            print(f"  [dry-run] would remove {p}  (age {age_h:.1f}h)")
        print("\nAdd --confirm to actually remove files.")
        return 0

    removed = 0
    for p in stale:
        try:
            p.unlink()
            print(f"  removed {p}")
            removed += 1
        except OSError as exc:
            print(f"  ERROR removing {p}: {exc}")

    print(f"\nRemoved {removed}/{len(stale)} stale staging file(s).")
    return 0


# ---------------------------------------------------------------------------
# Command: recover
# ---------------------------------------------------------------------------

def cmd_recover(args: argparse.Namespace) -> int:
    from app.core.db import SessionLocal
    from app.modules.documents.model import Document
    from app.modules.documents.schemas import DocumentCreate
    from app.modules.documents import repo

    file_path = Path(args.file_path)
    if not file_path.exists():
        print(f"ERROR: file not found: {file_path}")
        return 1

    sha256 = _compute_sha256(file_path)
    print(f"SHA-256: {sha256}")

    db = SessionLocal()
    try:
        existing = repo.get_document_by_sha256(db, sha256)
        if existing is not None:
            print(
                f"File is already registered as Document id={existing.id} "
                f"('{existing.title}'). No action taken."
            )
            return 0

        # Also check by file_path
        normalised_path = str(file_path).replace("\\", "/")
        by_path = (
            db.query(Document)
            .filter(Document.file_path == normalised_path)
            .first()
        )
        if by_path is not None:
            print(
                f"A Document (id={by_path.id}) already references this path but "
                f"has a different sha256_hash. Updating the hash."
            )
            by_path.sha256_hash = sha256
            db.commit()
            print("sha256_hash updated.")
            return 0

        # Infer MIME from extension (best-effort)
        ext = file_path.suffix.lower()
        ext_mime_map = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".doc": "application/msword",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xls": "application/vnd.ms-excel",
            ".txt": "text/plain",
            ".csv": "text/csv",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".tif": "image/tiff",
            ".tiff": "image/tiff",
        }
        mime = ext_mime_map.get(ext, "application/octet-stream")

        payload = DocumentCreate(
            title=args.title,
            original_filename=file_path.name,
            stored_filename=file_path.name,
            file_path=normalised_path,
            mime_type=mime,
            file_size=file_path.stat().st_size,
            status="uploaded",
            uploaded_by_user_id=args.user_id,
            sha256_hash=sha256,
        )

        doc = repo.create_document(db, payload)
        print(f"Recovered: Document id={doc.id} created for '{file_path}'.")
        return 0

    finally:
        db.close()


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.tools.storage_admin",
        description="InsureIntel file-storage recovery and maintenance CLI.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # verify
    p_verify = sub.add_parser("verify", help="Re-hash stored files and compare with DB records.")
    p_verify.add_argument("--verbose", "-v", action="store_true", help="Print OK lines too.")

    # orphans
    sub.add_parser("orphans", help="List files on disk with no Document row.")

    # clean-orphans
    p_co = sub.add_parser("clean-orphans", help="Move orphaned files to storage/quarantine/.")
    p_co.add_argument("--confirm", action="store_true", help="Actually move files (default: dry-run).")

    # clean-staging
    p_cs = sub.add_parser("clean-staging", help="Remove stale staging files.")
    p_cs.add_argument(
        "--max-age-hours", type=float, default=24.0,
        metavar="N", help="Remove staging files older than N hours (default: 24).",
    )
    p_cs.add_argument("--confirm", action="store_true", help="Actually remove files (default: dry-run).")

    # recover
    p_rec = sub.add_parser("recover", help="Register an on-disk file into the documents table.")
    p_rec.add_argument("file_path", help="Path to the file to register.")
    p_rec.add_argument("--title", required=True, help="Document title to store.")
    p_rec.add_argument("--user-id", type=int, required=True, help="uploaded_by_user_id to set.")

    return parser


_COMMANDS = {
    "verify":        cmd_verify,
    "orphans":       cmd_orphans,
    "clean-orphans": cmd_clean_orphans,
    "clean-staging": cmd_clean_staging,
    "recover":       cmd_recover,
}


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    fn = _COMMANDS[args.command]
    return fn(args)


if __name__ == "__main__":
    sys.exit(main())

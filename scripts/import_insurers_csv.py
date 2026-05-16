#!/usr/bin/env python3
"""
scripts/import_insurers_csv.py — CLI tool for importing insurers from CSV.

Usage:
    python scripts/import_insurers_csv.py path/to/insurers.csv

Reads the CSV and upserts insurer records using the same logic as
POST /insurers/import-csv — with a direct database connection instead
of going through the HTTP API.

Columns expected (matches the IPEC regulated-entities export):
    Entity Name, Insurance Category, Insurance Type,
    Physical Address, Email, Telephone, Source

Exit codes:
    0 — success
    1 — usage error or fatal DB error
"""
from __future__ import annotations

import csv
import logging
import sys
from pathlib import Path

# ── Bootstrap project paths ──────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from app.core.db import SessionLocal                     # noqa: E402
from app.modules.insurers.model import Insurer          # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Category map (mirrors the one in insurers/router.py) ────────────────────
_CAT_MAP: dict[str, str] = {
    "life assurer":         "life_assurance",
    "life assurance":       "life_assurance",
    "short-term insurer":   "short_term",
    "short term insurer":   "short_term",
    "reinsurer":            "reinsurer",
    "life reassurer":       "reinsurer",
    "funeral assurer":      "funeral_assurer",
    "funeral":              "funeral_assurer",
    "micro-insurer":        "microinsurer",
    "microinsurer":         "microinsurer",
    "broker":               "broker",
    "multiple agent":       "multiple_agent",
    "underwriting agent":   "underwriting_agent",
}

_COL_ALIASES: dict[str, list[str]] = {
    "name":     ["Entity Name", "entity_name", "Name", "name"],
    "category": ["Insurance Category", "insurance_category", "Category"],
    "type":     ["Insurance Type", "insurance_type", "Type"],
    "address":  ["Physical Address", "physical_address", "Address"],
    "email":    ["Email", "email"],
    "phone":    ["Telephone", "telephone", "Phone"],
}


def _get(row: dict, field: str) -> str:
    """Extract field from a CSV row using known aliases."""
    for alias in _COL_ALIASES.get(field, [field]):
        if alias in row:
            return (row[alias] or "").strip()
    return ""


def import_csv(csv_path: str) -> dict:
    """
    Import insurers from a CSV file into the database.

    Args:
        csv_path: Absolute or relative path to the CSV file.

    Returns:
        dict with keys: imported, updated, errors (list of strings).
    """
    path = Path(csv_path)
    if not path.exists():
        logger.error("File not found: %s", csv_path)
        sys.exit(1)

    imported = 0
    updated  = 0
    errors: list[str] = []

    db = SessionLocal()
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row_num, row in enumerate(reader, start=2):
                name = _get(row, "name")
                if not name:
                    errors.append(f"Row {row_num}: missing Entity Name — skipped")
                    continue

                raw_cat  = _get(row, "category").lower().strip()
                category = _CAT_MAP.get(raw_cat)

                try:
                    existing = (
                        db.query(Insurer)
                        .filter(Insurer.name.ilike(name))
                        .first()
                    )
                    if existing:
                        if category:               existing.category            = category
                        if _get(row, "address"):   existing.head_office_address = _get(row, "address")
                        if _get(row, "email"):     existing.email               = _get(row, "email")
                        if _get(row, "phone"):     existing.phone               = _get(row, "phone")
                        updated += 1
                    else:
                        new_ins = Insurer(
                            name                = name,
                            category            = category,
                            industry_segment    = _get(row, "type"),
                            head_office_address = _get(row, "address"),
                            email               = _get(row, "email"),
                            phone               = _get(row, "phone"),
                        )
                        db.add(new_ins)
                        imported += 1
                except Exception as exc:
                    errors.append(f"Row {row_num} ({name!r}): {exc}")
                    db.rollback()
                    continue

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Fatal DB error: %s", exc)
        sys.exit(1)
    finally:
        db.close()

    return {"imported": imported, "updated": updated, "errors": errors}


def main() -> None:
    """Entry point for CLI usage."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_insurers_csv.py <path_to_csv>", file=sys.stderr)
        sys.exit(1)

    csv_path = sys.argv[1]
    result   = import_csv(csv_path)

    logger.info("Import complete.")
    logger.info("  Imported : %d", result["imported"])
    logger.info("  Updated  : %d", result["updated"])
    logger.info("  Errors   : %d", len(result["errors"]))

    if result["errors"]:
        logger.warning("Errors:")
        for err in result["errors"]:
            logger.warning("  %s", err)


if __name__ == "__main__":
    main()

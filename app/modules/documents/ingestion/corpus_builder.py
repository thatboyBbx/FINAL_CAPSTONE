"""
Scan source directories, extract text from every supported document,
build a labelled JSON corpus, and save it to disk using parallel processing.
"""
import json
import logging
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from app.modules.documents.ingestion.pdf_extractor import extract_text_from_pdf
from app.modules.documents.ingestion.feature_extractor import extract_features

logger = logging.getLogger(__name__)

SUPPORTED = {".pdf", ".xlsx", ".xls"}


def _extract_xlsx_text(path: Path) -> str:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        parts: list[str] = []
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                row_text = " ".join(str(v) for v in row if v is not None)
                if row_text.strip():
                    parts.append(row_text)
        return "\n".join(parts)
    except ImportError:
        return ""
    except Exception as e:
        logger.warning("xlsx extraction failed for %s: %s", path.name, e)
        return ""


def _collect_files(directory: Path) -> list[Path]:
    files: list[Path] = []
    for ext in SUPPORTED:
        files.extend(directory.rglob(f"*{ext}"))
    return files


def _process_single_file_worker(args: tuple[Path, str]) -> dict[str, Any] | None:
    """Worker function that runs in a separate process."""
    file_path, label = args
    try:
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            text = extract_text_from_pdf(file_path, max_pages=5)
        elif suffix in {".xlsx", ".xls"}:
            text = _extract_xlsx_text(file_path)
        else:
            text = ""

        return extract_features(file_path, text, source_label=label)
    except Exception as e:
        # We print to stderr to ensure visibility in case logging isn't fully set up in child process
        import sys
        print(f"Failed to process {file_path.name}: {e}", file=sys.stderr)
        return None


def build_corpus(
    source_paths: list[dict],
    output_path: Path | None = None,
    max_docs: int = 10000,
    progress_cb=None,
) -> list[dict[str, Any]]:
    """
    Ingest all documents from source_paths in parallel.

    Args:
        source_paths: [{"path": "/some/dir", "label": "circulars"}, ...]
        output_path:  where to save the corpus JSON (optional)
        max_docs:     hard cap to prevent runaway
        progress_cb:  optional callable(current, total, filename) for progress

    Returns:
        list of feature dicts
    """
    corpus: list[dict] = []

    # Collect all files first so we can report total
    all_files: list[tuple[Path, str]] = []
    for src in source_paths:
        directory = Path(src["path"])
        label = src.get("label", "unknown")
        if not directory.exists():
            logger.warning("Source path does not exist: %s", directory)
            continue
        files = _collect_files(directory)
        logger.info("Found %d documents in %s", len(files), directory)
        all_files.extend((f, label) for f in files)

    total = min(len(all_files), max_docs)
    files_to_process = all_files[:max_docs]

    num_workers = min(os.cpu_count() or 4, 6)
    logger.info("Starting ProcessPoolExecutor with %d workers", num_workers)

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        # Use executor.map to map worker function over files, which preserves order
        results = executor.map(_process_single_file_worker, files_to_process)
        
        for idx, record in enumerate(results):
            file_path, _ = files_to_process[idx]
            if progress_cb:
                progress_cb(idx + 1, total, file_path.name)
            
            if record is not None:
                corpus.append(record)

    logger.info("Corpus complete: %d documents", len(corpus))

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(corpus, f, indent=2, ensure_ascii=False, default=str)
        logger.info("Corpus saved → %s", output_path)

    return corpus

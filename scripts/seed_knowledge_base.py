#!/usr/bin/env python3
"""
scripts/seed_knowledge_base.py

CLI tool to seed InsureIntel's ChromaDB knowledge base from a directory of PDF files.

Usage:
    python scripts/seed_knowledge_base.py --source-dir ./knowledge_pdfs/
    python scripts/seed_knowledge_base.py --source-dir ./knowledge_pdfs/ --dry-run
    python scripts/seed_knowledge_base.py --source-dir ./knowledge_pdfs/ --collection custom_collection

The source directory should contain:
    - Insurance Act Chapter 24:07 (PDF)
    - IPEC regulations and circulars (PDFs)
    - Standard insurance policy templates (PDFs)
    Any other PDF is also accepted and will be chunked and embedded.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    Split text into overlapping word-based chunks.

    Args:
        text:       Plain text to split.
        chunk_size: Maximum number of words per chunk.
        overlap:    Number of words to repeat from the previous chunk.

    Returns:
        List of text chunks. Returns empty list for empty input.
    """
    if not text or not text.strip():
        return []

    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    step = chunk_size - overlap  # advance this many words each iteration
    if step <= 0:
        step = chunk_size  # safety guard: avoid infinite loop if overlap >= chunk_size

    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == len(words):
            break
        start += step

    return chunks


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract plain text from a PDF file using pdfplumber.
    Returns empty string on failure.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Extracted text as a single string.
    """
    try:
        import pdfplumber

        pages: list[str] = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    pages.append(page_text)
        return "\n\n".join(pages)

    except Exception as exc:
        print(f"  [WARNING] Could not extract text from {pdf_path.name}: {exc}", file=sys.stderr)
        return ""


def infer_doc_type(filename: str) -> str:
    """
    Infer document type from filename for ChromaDB metadata.
    Returns a descriptive string like "insurance_act", "circular", "policy_wording".

    Args:
        filename: PDF filename (no path).

    Returns:
        Document type string.
    """
    name_lower = filename.lower()
    if "act" in name_lower or "chapter" in name_lower:
        return "insurance_act"
    if "circular" in name_lower:
        return "ipec_circular"
    if "guidance" in name_lower:
        return "ipec_guidance"
    if "motor" in name_lower:
        return "motor_policy"
    if "fire" in name_lower:
        return "fire_policy"
    if "life" in name_lower:
        return "life_policy"
    if "fsr" in name_lower or "financial" in name_lower:
        return "fsr_report"
    if "treaty" in name_lower or "reinsurance" in name_lower:
        return "reinsurance_treaty"
    return "insurance_document"


def seed_collection(
    source_dir: Path,
    collection_name: str,
    dry_run: bool,
    chunk_size: int = 500,
    overlap: int = 50,
) -> dict[str, int]:
    """
    Process all PDFs in source_dir and upsert chunks into ChromaDB.
    In dry_run mode, skips ChromaDB initialisation entirely.

    Args:
        source_dir:      Directory containing PDF files.
        collection_name: ChromaDB collection name to write to.
        dry_run:         If True, print actions only — no ChromaDB writes.
        chunk_size:      Words per chunk.
        overlap:         Word overlap between adjacent chunks.

    Returns:
        Dict with keys: files_processed, chunks_embedded, errors.
    """
    pdf_files = sorted(source_dir.glob("*.pdf"))

    stats: dict[str, int] = {"files_processed": 0, "chunks_embedded": 0, "errors": 0}

    if not pdf_files:
        print(f"No PDF files found in {source_dir}")
        return stats

    print(f"\nFound {len(pdf_files)} PDF file(s) in {source_dir}")

    # In dry_run mode we never connect to ChromaDB
    collection = None
    embed_model = None

    if not dry_run:
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer

            client = chromadb.Client()
            collection = client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            embed_model = SentenceTransformer("all-MiniLM-L6-v2")
            print(f"Connected to ChromaDB collection '{collection_name}'")

        except Exception as exc:
            print(f"[ERROR] Could not initialise ChromaDB: {exc}", file=sys.stderr)
            print("Tip: Run with --dry-run to verify without a ChromaDB connection.", file=sys.stderr)
            stats["errors"] += 1
            return stats

    for pdf_path in pdf_files:
        print(f"\nProcessing: {pdf_path.name}")

        text = extract_text_from_pdf(pdf_path)
        if not text.strip():
            print(f"  [SKIP] No text extracted from {pdf_path.name}")
            stats["errors"] += 1
            continue

        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        doc_type = infer_doc_type(pdf_path.name)

        print(f"  Extracted {len(text):,} characters → {len(chunks)} chunks (doc_type={doc_type})")

        if dry_run:
            print(f"  [dry_run] Would upsert {len(chunks)} chunks into collection '{collection_name}'")
            stats["files_processed"] += 1
            stats["chunks_embedded"] += len(chunks)
            continue

        # Embed and upsert each chunk into ChromaDB
        errors_this_file = 0
        for i, chunk in enumerate(chunks):
            try:
                embedding: list[float] = embed_model.encode(chunk).tolist()  # type: ignore[union-attr]
                doc_id = f"{pdf_path.stem}_chunk_{i}"
                collection.upsert(  # type: ignore[union-attr]
                    ids=[doc_id],
                    embeddings=[embedding],
                    documents=[chunk],
                    metadatas=[{
                        "source_file": pdf_path.name,
                        "chunk_index": i,
                        "doc_type": doc_type,
                    }],
                )
                stats["chunks_embedded"] += 1
            except Exception as exc:
                print(f"  [ERROR] Failed to upsert chunk {i} of {pdf_path.name}: {exc}", file=sys.stderr)
                errors_this_file += 1

        if errors_this_file == 0:
            print(f"  Upserted {len(chunks)} chunks successfully")
            stats["files_processed"] += 1
        else:
            print(f"  Completed with {errors_this_file} chunk error(s)")
            stats["files_processed"] += 1
            stats["errors"] += errors_this_file

    return stats


def main() -> None:
    """Entry point — parse CLI args and run the seeder."""
    parser = argparse.ArgumentParser(
        description="Seed InsureIntel's ChromaDB knowledge base from a directory of PDF files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/seed_knowledge_base.py --source-dir ./knowledge_pdfs/
  python scripts/seed_knowledge_base.py --source-dir ./knowledge_pdfs/ --dry-run
  python scripts/seed_knowledge_base.py --source-dir ./knowledge_pdfs/ --collection custom_collection
        """,
    )
    parser.add_argument(
        "--source-dir",
        required=True,
        type=Path,
        help="Directory containing PDF files to ingest.",
    )
    parser.add_argument(
        "--collection",
        default="insurance_knowledge",
        help="ChromaDB collection name (default: insurance_knowledge).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be ingested without writing to ChromaDB.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Words per chunk (default: 500).",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=50,
        help="Word overlap between adjacent chunks (default: 50).",
    )

    args = parser.parse_args()

    source_dir: Path = args.source_dir.resolve()
    if not source_dir.exists():
        print(f"[ERROR] Source directory not found: {source_dir}", file=sys.stderr)
        sys.exit(1)
    if not source_dir.is_dir():
        print(f"[ERROR] Not a directory: {source_dir}", file=sys.stderr)
        sys.exit(1)

    mode_label = "DRY RUN" if args.dry_run else "LIVE"
    print(f"\n{'=' * 60}")
    print(f"InsureIntel Knowledge Base Seeder [{mode_label}]")
    print(f"{'=' * 60}")
    print(f"Source directory : {source_dir}")
    print(f"Collection       : {args.collection}")
    print(f"Chunk size       : {args.chunk_size} words")
    print(f"Overlap          : {args.overlap} words")

    stats = seed_collection(
        source_dir=source_dir,
        collection_name=args.collection,
        dry_run=args.dry_run,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    )

    print(f"\n{'=' * 60}")
    print("SEEDER SUMMARY")
    print(f"{'=' * 60}")
    print(f"Files processed  : {stats['files_processed']}")
    print(f"Chunks embedded  : {stats['chunks_embedded']}")
    print(f"Errors           : {stats['errors']}")
    if args.dry_run:
        print("\n[dry_run] No data was written to ChromaDB.")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()

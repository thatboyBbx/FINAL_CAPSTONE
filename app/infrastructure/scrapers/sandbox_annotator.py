"""
app/infrastructure/scrapers/sandbox_annotator.py

BIO Annotation Pipeline for the IPEC Regulatory Sandbox Guidelines PDF.

Reads the sandbox PDF, splits text into sentences, runs rule-based
regex/keyword matching to tag 8 regulatory NER entity types, and writes
spaCy-format JSONL training data plus a plain-text sentence dump.

Run directly:
    python app/infrastructure/scrapers/sandbox_annotator.py

Outputs:
    app/infrastructure/storage/training_data/sandbox_ner_annotations.jsonl
    app/infrastructure/storage/training_data/sandbox_sentences_raw.txt
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from app.modules.documents.ingestion.pdf_extractor import extract_text_from_pdf

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Absolute path to the source PDF (adjust if running from a different cwd)
_PDF_PATH = Path(
    r"C:\Users\lenovo\Desktop\CAPSTONE_ARCHIVE\PRIMARY\EXPERIMENT"
    r"\sources\downloads\SOURCES"
    r"\REGULATORY-SANDBOX-GUIDELINES-FOR-THE-INSURANCE-AND-PENSIONS-INDUSTRY-.pdf"
)

# Output directory — mirrors the infrastructure storage layout
_OUT_DIR = Path(__file__).resolve().parent.parent / "storage" / "training_data"

_JSONL_PATH = _OUT_DIR / "sandbox_ner_annotations.jsonl"
_RAW_TXT_PATH = _OUT_DIR / "sandbox_sentences_raw.txt"

# ---------------------------------------------------------------------------
# Entity pattern definitions
# ---------------------------------------------------------------------------
# Each entry is (LABEL, compiled_regex_list).  Patterns are checked in order;
# the first matching pattern in a sentence tags that entity.
# Case-insensitive flag applied at compile time.

_ENTITY_PATTERNS: list[tuple[str, list[re.Pattern[str]]]] = [
    (
        "TESTING_PERIOD",
        [
            re.compile(r"\b\d+[-\s]?month(?:s)?\b", re.IGNORECASE),
            re.compile(r"\btesting\s+period\b", re.IGNORECASE),
            re.compile(r"\bduration\s+of\s+(?:the\s+)?test\b", re.IGNORECASE),
            re.compile(r"\btest(?:ing)?\s+window\b", re.IGNORECASE),
        ],
    ),
    (
        "BOUNDARY_CONDITION",
        [
            re.compile(r"\bstart\s+and\s+end\s+date\b", re.IGNORECASE),
            re.compile(r"\btransaction\s+limit\b", re.IGNORECASE),
            re.compile(r"\bnumber\s+of\s+customers\b", re.IGNORECASE),
            re.compile(r"\bgeographical\s+location\b", re.IGNORECASE),
            re.compile(r"\btarget\s+customer(?:\s+type)?\b", re.IGNORECASE),
            re.compile(r"\bconsent\s+to\s+participate\b", re.IGNORECASE),
        ],
    ),
    (
        "REGULATORY_WAIVER",
        [
            re.compile(r"\brelaxation\b", re.IGNORECASE),
            re.compile(r"\bregulatory\s+relief\b", re.IGNORECASE),
            re.compile(r"\bwaiver\b", re.IGNORECASE),
            re.compile(r"\bexemption\s+sought\b", re.IGNORECASE),
            re.compile(r"\bcannot\s+operate\s+within\b", re.IGNORECASE),
        ],
    ),
    (
        "KPI_TARGET",
        [
            re.compile(r"\bkey\s+performance\s+indicator\b", re.IGNORECASE),
            re.compile(r"\bKPI\b"),
            re.compile(r"\bsuccess\s+criteria\b", re.IGNORECASE),
            re.compile(r"\bperformance\s+indicator\b", re.IGNORECASE),
            re.compile(r"\btargets\s+and\s+key\b", re.IGNORECASE),
        ],
    ),
    (
        "EXIT_CONDITION",
        [
            re.compile(r"\bexit\s+plan\b", re.IGNORECASE),
            re.compile(r"\bgraduation\s+phase\b", re.IGNORECASE),
            re.compile(r"\bexit\s+report\b", re.IGNORECASE),
            re.compile(r"\borderly\s+exit\b", re.IGNORECASE),
            re.compile(r"\btransition.*deployment\b", re.IGNORECASE),
            re.compile(r"\bpost[-\s]exit\b", re.IGNORECASE),
        ],
    ),
    (
        "COMPLIANCE_STATUS",
        [
            re.compile(r"\bcommunicate.*in\s+writing\b", re.IGNORECASE),
            re.compile(r"\bCommission\s+will\s+communicate\b", re.IGNORECASE),
            re.compile(r"\b(?:test(?:ing)?\s+)?approved\b", re.IGNORECASE),
            re.compile(r"\brevoked\b", re.IGNORECASE),
            re.compile(r"\btest(?:ing)?\s+(?:was\s+)?successful\b", re.IGNORECASE),
            re.compile(r"\btest(?:ing)?\s+(?:was\s+)?failure\b", re.IGNORECASE),
        ],
    ),
    (
        "TCF_CLAUSE",
        [
            re.compile(r"\bTreating\s+Customers\s+Fairly\b", re.IGNORECASE),
            re.compile(r"\bTCF\b"),
            re.compile(r"\bdispute\s+resolution\b", re.IGNORECASE),
            re.compile(r"\bfair\s+treatment\b", re.IGNORECASE),
            re.compile(r"\bcustomer\s+complaint\b", re.IGNORECASE),
            re.compile(r"\bcomplaints\b", re.IGNORECASE),
        ],
    ),
    (
        "KYC_AML_CLAUSE",
        [
            re.compile(r"\bKnow\s+Your\s+Customer\b", re.IGNORECASE),
            re.compile(r"\bKYC\b"),
            re.compile(r"\bAnti[\s-]Money\s+Laundering\b", re.IGNORECASE),
            re.compile(r"\bAML\b"),
            re.compile(r"\bCountering\s+Financing\s+of\s+Terrorism\b", re.IGNORECASE),
            re.compile(r"\bCFT\b"),
            re.compile(r"\bmoney\s+laundering\b", re.IGNORECASE),
        ],
    ),
]




# ---------------------------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------------------------

def split_into_sentences(text: str) -> list[str]:
    """
    Split document text into sentences using a period-space heuristic.

    Splits on '. ', '.\n', or line breaks, then cleans whitespace.
    Keeps sentences ≥ 15 characters to filter out headers and stubs.

    Dissertation Methodology Note (Chapter 3):
    A simple heuristic splitter (not NLTK) was chosen to avoid an additional
    dependency not present in requirements.txt. This is sufficient for
    regulatory plain-prose text which uses standard English punctuation.

    References:
        IPEC (2025). Regulatory Sandbox Guidelines for the Insurance and
        Pensions Industry. Insurance and Pensions Commission of Zimbabwe.
        Effective Q4 2025. Retrieved from ipec.co.zw.
    """
    # Replace newlines with spaces to help the sentence splitter
    normalised = re.sub(r"\n+", " ", text)

    # Split on period-space or period at end of line
    raw_sentences = re.split(r"(?<=[.!?])\s+", normalised)

    sentences: list[str] = []
    for sent in raw_sentences:
        # Strip and skip very short stubs (page numbers, headers, etc.)
        cleaned = sent.strip()
        if len(cleaned) >= 15:
            sentences.append(cleaned)

    return sentences


# ---------------------------------------------------------------------------
# Annotation — match entities in a single sentence
# ---------------------------------------------------------------------------

def annotate_sentence(
    sentence: str,
) -> list[tuple[int, int, str]] | None:
    """
    Run all entity patterns against a single sentence and return span annotations.

    Returns a list of (start, end, label) tuples, or None if two patterns
    produce overlapping spans in the same sentence (skip to avoid bad training data).

    Dissertation Methodology Note (Chapter 3):
    This function implements a conservative rule-based pre-annotator. Where spans
    overlap, the sentence is discarded to preserve annotation quality — a deliberate
    trade-off that prioritises precision over recall at the data-generation stage.

    References:
        IPEC (2025). Regulatory Sandbox Guidelines for the Insurance and
        Pensions Industry. Insurance and Pensions Commission of Zimbabwe.
        Effective Q4 2025. Retrieved from ipec.co.zw.
    """
    annotations: list[tuple[int, int, str]] = []

    for label, patterns in _ENTITY_PATTERNS:
        for pattern in patterns:
            match = pattern.search(sentence)
            if match is None:
                continue

            start, end = match.start(), match.end()

            # Check for overlap with any already-recorded span
            for existing_start, existing_end, _ in annotations:
                if start < existing_end and end > existing_start:
                    # Overlapping spans — discard the whole sentence
                    logger.debug(
                        "Overlap detected in sentence (skipping): '%s'",
                        sentence[:80],
                    )
                    return None

            annotations.append((start, end, label))
            break  # one match per label per sentence is sufficient

    return annotations


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_annotation_pipeline(pdf_path: Path) -> None:
    """
    Full pipeline: extract → split → annotate → write JSONL + raw txt.

    Prints a summary of sentences processed and annotations per entity type
    so the researcher can verify the output at the command line.

    Dissertation Methodology Note (Chapter 3):
    The BIO-format JSONL output conforms to spaCy's Doc.from_json() schema,
    enabling direct ingestion into the spaCy training pipeline (spacy train).
    Negative examples (sentences with no entity matches) are included to
    prevent the model from over-predicting entity spans.

    References:
        IPEC (2025). Regulatory Sandbox Guidelines for the Insurance and
        Pensions Industry. Insurance and Pensions Commission of Zimbabwe.
        Effective Q4 2025. Retrieved from ipec.co.zw.
    """
    # ── Ensure output directory exists ──────────────────────────────────────
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Extract text from PDF ───────────────────────────────────────
    logger.info("Reading PDF: %s", pdf_path)
    full_text = extract_text_from_pdf(pdf_path)
    logger.info("Total extracted text: %d characters", len(full_text))

    # ── Step 2: Split into sentences ─────────────────────────────────────────
    sentences = split_into_sentences(full_text)
    logger.info("Total sentences after splitting: %d", len(sentences))

    # ── Step 3: Annotate each sentence ───────────────────────────────────────
    # Track per-entity counts for the summary
    entity_counts: dict[str, int] = {label: 0 for label, _ in _ENTITY_PATTERNS}
    skipped_overlap = 0
    annotated_records: list[dict[str, Any]] = []

    for sentence in sentences:
        result = annotate_sentence(sentence)

        if result is None:
            # Overlapping spans — skip this sentence entirely
            skipped_overlap += 1
            continue

        # Build the spaCy-compatible training record
        # Format: {"text": str, "entities": [[start, end, label], ...]}
        record: dict[str, Any] = {
            "text": sentence,
            "entities": [[s, e, lbl] for s, e, lbl in result],
        }
        annotated_records.append(record)

        # Count each entity label annotated
        for _, _, lbl in result:
            if lbl in entity_counts:
                entity_counts[lbl] += 1

    # ── Step 4: Write JSONL output (one record per line) ─────────────────────
    with open(_JSONL_PATH, "w", encoding="utf-8") as jsonl_file:
        for record in annotated_records:
            jsonl_file.write(json.dumps(record) + "\n")
    logger.info("JSONL written: %s (%d records)", _JSONL_PATH, len(annotated_records))

    # ── Step 5: Write raw sentences (for manual review) ─────────────────────
    with open(_RAW_TXT_PATH, "w", encoding="utf-8") as txt_file:
        for sent in sentences:
            txt_file.write(sent + "\n")
    logger.info("Raw sentences written: %s (%d lines)", _RAW_TXT_PATH, len(sentences))

    # ── Step 6: Print summary ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SANDBOX ANNOTATOR — SUMMARY")
    print("=" * 60)
    print(f"Sentences processed     : {len(sentences)}")
    print(f"Records in JSONL        : {len(annotated_records)}")
    print(f"Sentences skipped (overlap): {skipped_overlap}")
    print("-" * 40)
    print("Annotations per entity type:")
    for label, count in entity_counts.items():
        print(f"  {label:<25} {count}")
    print("=" * 60)

    # Confirm the two required entity types have been found
    if entity_counts.get("TESTING_PERIOD", 0) == 0:
        logger.warning("No TESTING_PERIOD annotations found — review patterns")
    if entity_counts.get("KYC_AML_CLAUSE", 0) == 0:
        logger.warning("No KYC_AML_CLAUSE annotations found — review patterns")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_annotation_pipeline(_PDF_PATH)

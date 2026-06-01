from app.modules.documents.ingestion.pdf_extractor import (
    extract_text_from_pdf,
    extract_text_from_pdf_bytes,
)


def extract_text(file_path: str) -> str:
    """Compatibility wrapper used by report and ingestion callers."""
    return extract_text_from_pdf(file_path)


__all__ = ["extract_text", "extract_text_from_pdf", "extract_text_from_pdf_bytes"]

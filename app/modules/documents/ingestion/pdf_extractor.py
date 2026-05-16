"""
PDF text extraction.

Priority order:
  1. pdfplumber  — best quality, handles tables, encoded fonts
  2. FlateDecode stream decompression  — works on most modern PDFs
  3. Raw BT/ET byte scanning  — last resort for uncompressed PDFs
"""
import re
import zlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decode_pdf_string(raw: bytes) -> str:
    """Best-effort decode of PDF string bytes → unicode."""
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return raw.decode(enc, errors="ignore")
        except Exception:
            pass
    return ""


def _parse_text_from_stream(stream_bytes: bytes) -> str:
    """
    Parse visible text from a decompressed PDF content stream.
    Handles Tj, TJ, ' and \" operators.
    """
    parts: list[str] = []

    # TJ array: [(string) spacing (string) ...]
    for arr_match in re.finditer(rb'\[([^\]]{1,4096})\]', stream_bytes):
        arr = arr_match.group(1)
        for s in re.finditer(rb'\(([^)]{0,300})\)', arr):
            decoded = _decode_pdf_string(s.group(1))
            printable = sum(1 for c in decoded if c.isprintable() and c != '\x00')
            if printable > len(decoded) * 0.6 and printable > 2:
                parts.append(decoded)

    # Tj single string: (string) Tj
    for m in re.finditer(rb'\(([^)]{0,300})\)\s*Tj', stream_bytes):
        decoded = _decode_pdf_string(m.group(1))
        printable = sum(1 for c in decoded if c.isprintable() and c != '\x00')
        if printable > len(decoded) * 0.6 and printable > 2:
            parts.append(decoded)

    return " ".join(parts)


def _extract_via_deflate(raw: bytes) -> str:
    """
    Decompress all FlateDecode content streams in the PDF
    and parse text from them.
    """
    text_parts: list[str] = []

    # Find every stream...endstream block
    for m in re.finditer(rb'stream\r?\n(.*?)endstream', raw, re.DOTALL):
        stream_data = m.group(1)
        if len(stream_data) < 4:
            continue
        # Try zlib decompression (FlateDecode)
        try:
            decompressed = zlib.decompress(stream_data)
            chunk = _parse_text_from_stream(decompressed)
            if chunk.strip():
                text_parts.append(chunk)
        except zlib.error:
            pass
        except Exception:
            pass

    return "\n".join(text_parts)


def _extract_raw_bt_et(raw: bytes) -> str:
    """Last-resort: scan uncompressed BT...ET blocks."""
    parts: list[str] = []
    for chunk in re.findall(rb'BT(.{0,2048}?)ET', raw, re.DOTALL):
        for s in re.finditer(rb'\(([^)]{0,300})\)', chunk):
            decoded = _decode_pdf_string(s.group(1))
            printable = sum(1 for c in decoded if c.isprintable() and c != '\x00')
            if printable > len(decoded) * 0.65 and printable > 3:
                parts.append(decoded)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_text_from_pdf(pdf_path: str | Path) -> str:
    """
    Extract all visible text from a PDF.
    Returns empty string on complete failure.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return ""

    # 1 — pdfplumber (best)
    try:
        import pdfplumber
        pages: list[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    pages.append(t)
        if pages:
            return "\n".join(pages)
    except ImportError:
        pass
    except Exception as e:
        logger.debug("pdfplumber failed for %s: %s", pdf_path.name, e)

    # 2 — FlateDecode decompression
    try:
        raw = pdf_path.read_bytes()
        text = _extract_via_deflate(raw)
        if len(text.split()) > 20:
            return text
    except Exception as e:
        logger.debug("FlateDecode extraction failed for %s: %s", pdf_path.name, e)

    # 3 — raw BT/ET scan
    try:
        raw = pdf_path.read_bytes()
        return _extract_raw_bt_et(raw)
    except Exception as e:
        logger.debug("BT/ET scan failed for %s: %s", pdf_path.name, e)

    return ""

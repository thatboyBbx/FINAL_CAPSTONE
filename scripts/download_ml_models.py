#!/usr/bin/env python3
"""
scripts/download_ml_models.py

Downloads and caches all ML models required by InsureIntel Zimbabwe.
Run this script ONCE after initial setup, before starting the application.

Models downloaded:
    1. SentenceTransformer: all-MiniLM-L6-v2 (embeddings for RAG + ChromaDB)
    2. MarianMT: Helsinki-NLP/opus-mt-en-sn (English -> Shona translation)  ~300MB
    3. spaCy: en_core_web_sm (base English NLP model for NER pipeline)      ~12MB

Usage:
    python scripts/download_ml_models.py
    python scripts/download_ml_models.py --skip-marian   # skip MarianMT if HF is slow
    python scripts/download_ml_models.py --verify-only   # check already-downloaded models
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from typing import Callable


# ── Result tracking ───────────────────────────────────────────────────────────

class ModelResult:
    """Tracks the download/verification outcome of a single model."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.ok = False
        self.message = ""

    def passed(self, msg: str) -> None:
        self.ok = True
        self.message = msg

    def failed(self, msg: str) -> None:
        self.ok = False
        self.message = msg


# ── Model functions ───────────────────────────────────────────────────────────

def download_sentence_transformer(verify_only: bool) -> ModelResult:
    """
    Download (or verify) the sentence-transformers/all-MiniLM-L6-v2 model.
    The SentenceTransformer library caches the model automatically in ~/.cache/torch/sentence_transformers.
    """
    result = ModelResult("SentenceTransformer: all-MiniLM-L6-v2")
    model_name = "all-MiniLM-L6-v2"

    try:
        from sentence_transformers import SentenceTransformer

        action = "Verifying" if verify_only else "Downloading"
        print(f"  {action} {model_name} ... (~90MB, uses local disk cache)")

        model = SentenceTransformer(model_name)

        # Verify by running a test embedding
        test_embedding = model.encode("insurance policy test")
        assert len(test_embedding) == 384, f"Expected embedding dim 384, got {len(test_embedding)}"

        result.passed(f"OK — embedding dim={len(test_embedding)}")

    except ImportError as exc:
        result.failed(f"sentence-transformers not installed: {exc}. Run: pip install sentence-transformers")
    except Exception as exc:
        result.failed(str(exc))

    return result


def download_marian_mt(verify_only: bool) -> ModelResult:
    """
    Download (or verify) the Helsinki-NLP/opus-mt-en-sn MarianMT model.
    WARNING: ~300MB download. The model is cached in ~/.cache/huggingface/transformers.
    """
    result = ModelResult("MarianMT: Helsinki-NLP/opus-mt-en-sn")
    model_name = "Helsinki-NLP/opus-mt-en-sn"

    print("  WARNING: MarianMT download is ~300MB. This may take several minutes.")
    print(f"  Cache location: ~/.cache/huggingface/transformers/")

    try:
        from transformers import MarianMTModel, MarianTokenizer

        action = "Verifying" if verify_only else "Downloading"
        print(f"  {action} tokenizer ...")
        tokenizer = MarianTokenizer.from_pretrained(model_name)

        print(f"  {action} model weights (~300MB) ...")
        model = MarianMTModel.from_pretrained(model_name)

        # Verify by translating a test phrase
        print("  Running test translation: 'insurance policy' -> Shona ...")
        inputs = tokenizer(["insurance policy"], return_tensors="pt", padding=True)
        translated = model.generate(**inputs)
        output_text = tokenizer.decode(translated[0], skip_special_tokens=True)

        result.passed(f"OK — test translation: '{output_text}'")

    except OSError as exc:
        # Model not available — network may be restricted
        result.failed(
            f"MarianMT model unavailable in this environment: {exc}\n"
            "  Download manually from: https://huggingface.co/Helsinki-NLP/opus-mt-en-sn\n"
            "  Place in ~/.cache/huggingface/transformers/"
        )
    except ImportError as exc:
        result.failed(f"transformers not installed: {exc}. Run: pip install transformers sentencepiece sacremoses")
    except Exception as exc:
        result.failed(str(exc))

    return result


def download_spacy_model(verify_only: bool) -> ModelResult:
    """
    Download (or verify) the spaCy en_core_web_sm model via subprocess.
    This is ~12MB and downloads quickly.
    """
    result = ModelResult("spaCy: en_core_web_sm")

    try:
        import spacy

        # Check if already installed
        try:
            nlp = spacy.load("en_core_web_sm")
            test_doc = nlp("The insurance policy covers fire damage.")
            result.passed(f"Already installed — {len(list(test_doc.ents))} entities in test doc")
            return result
        except OSError:
            pass  # Model not installed yet

        if verify_only:
            result.failed("en_core_web_sm not installed. Run without --verify-only to download.")
            return result

        print("  Downloading en_core_web_sm (~12MB) via spacy download ...")
        proc = subprocess.run(
            [sys.executable, "-m", "spacy", "download", "en_core_web_sm"],
            capture_output=True,
            text=True,
        )

        if proc.returncode == 0:
            nlp = spacy.load("en_core_web_sm")
            result.passed("Downloaded and verified successfully")
        else:
            result.failed(f"spacy download failed (exit={proc.returncode}): {proc.stderr.strip()}")

    except ImportError as exc:
        result.failed(f"spaCy not installed: {exc}. Run: pip install spacy")
    except Exception as exc:
        result.failed(str(exc))

    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    """Parse args and run model downloads/verification."""
    parser = argparse.ArgumentParser(
        description="Download and cache all ML models for InsureIntel Zimbabwe.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--skip-marian",
        action="store_true",
        help="Skip the MarianMT download (useful when HuggingFace Hub is slow or unavailable).",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify that models are already downloaded — do not download anything.",
    )

    args = parser.parse_args()

    mode = "VERIFY" if args.verify_only else "DOWNLOAD"
    print(f"\n{'=' * 60}")
    print(f"InsureIntel ML Model Setup [{mode}]")
    print(f"{'=' * 60}")

    results: list[ModelResult] = []

    # 1. SentenceTransformer
    print("\n[1/3] SentenceTransformer (all-MiniLM-L6-v2)")
    results.append(download_sentence_transformer(verify_only=args.verify_only))

    # 2. MarianMT
    if args.skip_marian:
        skipped = ModelResult("MarianMT: Helsinki-NLP/opus-mt-en-sn")
        skipped.ok = True
        skipped.message = "SKIPPED (--skip-marian flag)"
        results.append(skipped)
        print("\n[2/3] MarianMT — SKIPPED (--skip-marian)")
    else:
        print("\n[2/3] MarianMT (Helsinki-NLP/opus-mt-en-sn)")
        results.append(download_marian_mt(verify_only=args.verify_only))

    # 3. spaCy
    print("\n[3/3] spaCy (en_core_web_sm)")
    results.append(download_spacy_model(verify_only=args.verify_only))

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    all_ok = True
    for r in results:
        status = "PASS" if r.ok else "FAIL"
        print(f"  [{status}] {r.name}")
        print(f"         {r.message}")
        if not r.ok:
            all_ok = False

    print(f"{'=' * 60}")
    if all_ok:
        print("All models ready. You can now start InsureIntel Zimbabwe.\n")
        sys.exit(0)
    else:
        print("Some models failed. Review errors above before starting the application.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

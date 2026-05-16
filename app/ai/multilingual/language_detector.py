"""
LanguageDetector — detects Shona and other non-English segments in document text
and translates Shona segments to English using Helsinki-NLP MarianMT.

Models used (downloaded from HuggingFace Hub on first use):
  Language detection : papluca/xlm-roberta-base-language-detection
  Translation (sn→en): Helsinki-NLP/opus-mt-sn-en (MarianMT)

HuggingFace corpus reference:
  Shona-English parallel corpus: Helsinki-NLP/opus-100 ("en-sn" subset)
  load_dataset("Helsinki-NLP/opus-100", "en-sn")  — used for translation model training
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy-loaded singletons — models are heavy (~300MB each); only load on demand
# ---------------------------------------------------------------------------
_lang_pipeline = None
_marian_tokenizer = None
_marian_model = None


def _get_lang_pipeline():
    """Lazily load the xlm-roberta language detection pipeline."""
    global _lang_pipeline
    if _lang_pipeline is None:
        try:
            from transformers import pipeline as hf_pipeline
            _lang_pipeline = hf_pipeline(
                "text-classification",
                model="papluca/xlm-roberta-base-language-detection",
            )
            logger.info("Language detection model loaded.")
        except ImportError:
            raise ImportError(
                "transformers is required for language detection. "
                "Install with: pip install transformers torch sentencepiece sacremoses"
            )
    return _lang_pipeline


def _get_translator():
    """Lazily load the Shona→English MarianMT model."""
    global _marian_tokenizer, _marian_model
    if _marian_tokenizer is None:
        try:
            from transformers import MarianMTModel, MarianTokenizer
            model_name = "Helsinki-NLP/opus-mt-sn-en"
            _marian_tokenizer = MarianTokenizer.from_pretrained(model_name)
            _marian_model = MarianMTModel.from_pretrained(model_name)
            logger.info("MarianMT sn→en model loaded.")
        except ImportError:
            raise ImportError(
                "transformers, sentencepiece, and sacremoses are required. "
                "Install with: pip install transformers sentencepiece sacremoses torch"
            )
    return _marian_tokenizer, _marian_model


class LanguageDetector:
    """
    Detects Shona and mixed-language segments in document text.
    Translates Shona segments to English for downstream NLP.
    """

    def detect_language(self, text: str) -> Dict[str, Any]:
        """
        Detect the overall language of the text.
        Truncates to 512 characters for the model (model limit).
        Returns language code, name, confidence, and flags.
        """
        try:
            pipe = _get_lang_pipeline()
            result = pipe(text[:512], truncation=True)[0]
            lang_code = result["label"].lower()  # e.g. "sn", "en", "fr"
            confidence = float(result["score"])
        except Exception as exc:
            logger.warning("Language detection failed: %s", exc)
            return {
                "language_code": "en",
                "language_name": "English (default — detection failed)",
                "confidence": 0.0,
                "is_english": True,
                "is_shona": False,
            }

        # Language code to name mapping (subset)
        lang_names = {
            "en": "English", "sn": "Shona", "fr": "French",
            "pt": "Portuguese", "af": "Afrikaans", "sw": "Swahili",
            "nd": "Ndebele", "zu": "Zulu", "xh": "Xhosa",
        }
        return {
            "language_code": lang_code,
            "language_name": lang_names.get(lang_code, lang_code.upper()),
            "confidence": round(confidence, 4),
            "is_english": lang_code == "en",
            "is_shona": lang_code == "sn",
        }

    def detect_segments(
        self, full_text: str, segment_size: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Split full_text into segments and detect the language of each.
        Returns only non-English segments.
        """
        if not full_text:
            return []

        non_english = []
        char_pos = 0
        seg_idx = 0

        while char_pos < len(full_text):
            segment = full_text[char_pos: char_pos + segment_size]
            if not segment.strip():
                char_pos += segment_size
                seg_idx += 1
                continue

            try:
                detection = self.detect_language(segment)
                if not detection["is_english"] and detection["confidence"] > 0.5:
                    non_english.append({
                        "segment_index": seg_idx,
                        "text": segment,
                        "language_code": detection["language_code"],
                        "confidence": detection["confidence"],
                        "char_start": char_pos,
                        "char_end": char_pos + len(segment),
                    })
            except Exception as exc:
                logger.warning("Segment detection failed at pos %d: %s", char_pos, exc)

            char_pos += segment_size
            seg_idx += 1

        return non_english

    def translate_shona_segment(self, shona_text: str) -> Dict[str, Any]:
        """
        Translate a Shona text segment to English using MarianMT.
        """
        try:
            tokenizer, model = _get_translator()
            inputs = tokenizer(
                [shona_text], return_tensors="pt", padding=True, truncation=True, max_length=512
            )
            translated = model.generate(**inputs)
            translated_text = tokenizer.batch_decode(translated, skip_special_tokens=True)[0]
        except Exception as exc:
            logger.warning("Translation failed: %s", exc)
            translated_text = shona_text  # return original on failure

        return {
            "original": shona_text,
            "translated": translated_text,
            "source_lang": "sn",
            "target_lang": "en",
            "model": "Helsinki-NLP/opus-mt-sn-en",
        }

    def analyse_document_language(
        self,
        document_id: int,
        full_text: str,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Run full language analysis on a document:
        1. Detect overall language
        2. Find non-English segments
        3. Translate Shona segments
        4. Save results to document_language_analysis table
        """
        from app.modules.multilingual.model import DocumentLanguageAnalysis

        overall = self.detect_language(full_text)
        non_english_segments = self.detect_segments(full_text, segment_size=200)

        shona_segments = [s for s in non_english_segments if s["language_code"] == "sn"]
        translations = []
        for seg in shona_segments:
            result = self.translate_shona_segment(seg["text"])
            translations.append({**result, "segment_index": seg["segment_index"]})

        shona_pct = 0.0
        if full_text:
            shona_chars = sum(len(s["text"]) for s in shona_segments)
            shona_pct = round(shona_chars / len(full_text) * 100, 2)

        is_mixed = len(non_english_segments) > 0

        # Upsert the analysis row
        try:
            existing = (
                db.query(DocumentLanguageAnalysis)
                .filter(DocumentLanguageAnalysis.document_id == document_id)
                .first()
            )
            if existing:
                existing.primary_language = overall["language_code"]
                existing.is_mixed_language = is_mixed
                existing.shona_segment_count = len(shona_segments)
                existing.shona_pct = shona_pct
                existing.segments_json = non_english_segments
                existing.translations_json = translations
            else:
                row = DocumentLanguageAnalysis(
                    document_id=document_id,
                    primary_language=overall["language_code"],
                    is_mixed_language=is_mixed,
                    shona_segment_count=len(shona_segments),
                    shona_pct=shona_pct,
                    segments_json=non_english_segments,
                    translations_json=translations,
                )
                db.add(row)
            db.commit()
        except Exception as exc:
            logger.warning("Failed to save language analysis for doc %d: %s", document_id, exc)
            db.rollback()

        return {
            "document_id": document_id,
            "primary_language": overall["language_code"],
            "is_mixed_language": is_mixed,
            "shona_segment_count": len(shona_segments),
            "shona_pct_of_document": shona_pct,
            "segments": non_english_segments,
            "translated_segments": translations,
        }

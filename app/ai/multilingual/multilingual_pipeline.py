"""
MultilingualPipeline — replaces Shona segments with English translations
before passing text to the existing NLP pipeline.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Module-level imports allow tests to patch these names.
# Importing at the function level would make them invisible to unittest.mock.patch.
# When transformers is absent, stub classes are used so tests can still patch
# from_pretrained and trigger the OSError graceful-fallback path.
try:
    from transformers import MarianMTModel, MarianTokenizer  # type: ignore[import-untyped]
except ImportError:
    class _MarianStub:
        """Stand-in for a missing transformers class — lets tests patch from_pretrained."""
        @staticmethod
        def from_pretrained(*args: object, **kwargs: object) -> object:
            raise OSError(
                "transformers library not installed. "
                "Run: pip install transformers  (or: python scripts/download_ml_models.py)"
            )

    MarianMTModel = _MarianStub   # type: ignore[assignment,misc]
    MarianTokenizer = _MarianStub  # type: ignore[assignment,misc]


@dataclass
class TranslationResult:
    """Result of a translation attempt — always returned, never raises."""
    text: str                    # Translated text, or empty string if failed
    source_lang: str             # Input language code (e.g. "en")
    target_lang: str             # Output language code (e.g. "sn")
    success: bool                # True if translation succeeded
    error: str | None = None     # Error message if success is False
    model_available: bool = True # False if the model file is missing entirely


def translate_text(
    text: str,
    source_lang: str = "en",
    target_lang: str = "sn",
) -> TranslationResult:
    """
    Translate text using MarianMT (Helsinki-NLP/opus-mt-en-sn).
    Returns a TranslationResult — never raises an unhandled exception.
    If the model is not downloaded, returns success=False, model_available=False.
    """
    if not text.strip():
        return TranslationResult(text="", source_lang=source_lang, target_lang=target_lang, success=True)

    model_name = f"Helsinki-NLP/opus-mt-{source_lang}-{target_lang}"

    try:
        # MarianMTModel/MarianTokenizer are module-level names for testability.
        # When transformers is absent they are _MarianStub instances that raise
        # OSError on from_pretrained, which the except clause below handles.
        tokenizer = MarianTokenizer.from_pretrained(model_name)
        model = MarianMTModel.from_pretrained(model_name)

        inputs = tokenizer([text], return_tensors="pt", padding=True, truncation=True, max_length=512)
        translated_tokens = model.generate(**inputs)
        translated_text: str = tokenizer.decode(translated_tokens[0], skip_special_tokens=True)

        return TranslationResult(
            text=translated_text,
            source_lang=source_lang,
            target_lang=target_lang,
            success=True,
            model_available=True,
        )

    except (OSError, ImportError) as exc:
        # OSError = model files not downloaded yet; ImportError = transformers missing
        logger.warning("MarianMT model '%s' not available: %s", model_name, exc)
        return TranslationResult(
            text="",
            source_lang=source_lang,
            target_lang=target_lang,
            success=False,
            error=str(exc),
            model_available=False,
        )
    except Exception as exc:
        logger.error("translate_text failed unexpectedly: %s", exc, exc_info=True)
        return TranslationResult(
            text="",
            source_lang=source_lang,
            target_lang=target_lang,
            success=False,
            error=str(exc),
            model_available=True,
        )


class MultilingualPipeline:
    """
    Prepares mixed-language document text for the NLP pipeline by
    substituting translated Shona segments in-place.
    """

    def prepare_text_for_nlp(
        self,
        full_text: str,
        language_analysis: Dict[str, Any],
    ) -> str:
        """
        Replace Shona segments in full_text with their English translations.
        Marks substituted sections with '[TRANSLATED FROM SHONA]: ' prefix.
        Returns the modified text ready for the NLP pipeline.
        """
        if not language_analysis.get("is_mixed_language"):
            return full_text

        translated = language_analysis.get("translated_segments", [])
        segments   = language_analysis.get("segments", [])

        # Build a map from segment_index → translated text
        translation_map: Dict[int, str] = {}
        for t in translated:
            idx = t.get("segment_index")
            if idx is not None:
                translation_map[idx] = t.get("translated", "")

        # Build a map from segment_index → original segment text
        segment_map: Dict[int, Dict] = {s["segment_index"]: s for s in segments}

        if not translation_map:
            return full_text

        # Replace segments in the text, working from the end to preserve positions
        text = full_text
        for seg_idx in sorted(translation_map.keys(), reverse=True):
            seg = segment_map.get(seg_idx)
            if not seg:
                continue

            original = seg.get("text", "")
            translated_text = translation_map[seg_idx]
            if not original or not translated_text:
                continue

            replacement = f"[TRANSLATED FROM SHONA]: {translated_text}"
            # Replace the first occurrence of the original segment text
            text = text.replace(original, replacement, 1)

        return text

    def get_processing_notes(
        self, language_analysis: Dict[str, Any]
    ) -> List[str]:
        """
        Generate human-readable processing notes about language mixing.
        These notes are added to the analysis report.
        """
        notes = []
        if not language_analysis.get("is_mixed_language"):
            return notes

        shona_count = language_analysis.get("shona_segment_count", 0)
        shona_pct   = language_analysis.get("shona_pct_of_document", 0.0)
        primary     = language_analysis.get("primary_language", "en")

        if shona_count > 0:
            notes.append(
                f"Document contains {shona_count} Shona language segment(s) "
                f"(approximately {shona_pct:.1f}% of text). "
                "These have been automatically translated to English for analysis. "
                "Manual review of translated sections is recommended."
            )

        if primary not in ("en", "sn"):
            notes.append(
                f"Primary document language detected as '{primary}' — "
                "analysis quality may be reduced for non-English primary documents."
            )

        return notes

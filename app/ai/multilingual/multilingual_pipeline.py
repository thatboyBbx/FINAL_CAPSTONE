"""
MultilingualPipeline — replaces Shona segments with English translations
before passing text to the existing NLP pipeline.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


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

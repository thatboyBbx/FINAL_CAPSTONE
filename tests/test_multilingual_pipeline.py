"""
Tests for the multilingual translation pipeline.
Uses a mocked MarianMT model — no real model download needed for tests.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from app.ai.multilingual.multilingual_pipeline import translate_text, TranslationResult


class TestTranslationPipeline:
    """Test the translate_text function and TranslationResult dataclass."""

    def test_returns_translation_result_type(self) -> None:
        """translate_text must always return a TranslationResult, never raise."""
        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = {"input_ids": MagicMock(), "attention_mask": MagicMock()}
        mock_tokenizer.decode.return_value = "bima yemotokari"

        mock_model_instance = MagicMock()
        mock_model_instance.generate.return_value = [[1, 2, 3]]

        with patch("app.ai.multilingual.multilingual_pipeline.MarianTokenizer") as mock_tok_cls, \
             patch("app.ai.multilingual.multilingual_pipeline.MarianMTModel") as mock_model_cls:
            mock_tok_cls.from_pretrained.return_value = mock_tokenizer
            mock_model_cls.from_pretrained.return_value = mock_model_instance

            result = translate_text("insurance policy", source_lang="en", target_lang="sn")

        assert isinstance(result, TranslationResult)

    def test_returns_graceful_error_when_model_missing(self) -> None:
        """If the model file is absent, success must be False and model_available False."""
        with patch(
            "app.ai.multilingual.multilingual_pipeline.MarianMTModel.from_pretrained",
            side_effect=OSError("model files not found"),
        ), patch(
            "app.ai.multilingual.multilingual_pipeline.MarianTokenizer.from_pretrained",
            side_effect=OSError("tokenizer files not found"),
        ):
            result = translate_text("test insurance clause", source_lang="en", target_lang="sn")

        assert result.success is False
        assert result.model_available is False
        assert result.text == ""

    def test_empty_input_returns_empty_output(self) -> None:
        """Empty input string should return empty translation without crashing."""
        result = translate_text("", source_lang="en", target_lang="sn")
        assert result.text == ""
        assert result.success is True

    def test_whitespace_only_returns_empty(self) -> None:
        """Whitespace-only input should be treated as empty."""
        result = translate_text("   ", source_lang="en", target_lang="sn")
        assert result.text == ""
        assert result.success is True

    def test_translation_result_fields(self) -> None:
        """TranslationResult must have all required fields."""
        r = TranslationResult(
            text="test",
            source_lang="en",
            target_lang="sn",
            success=True,
        )
        assert hasattr(r, "text")
        assert hasattr(r, "source_lang")
        assert hasattr(r, "target_lang")
        assert hasattr(r, "success")
        assert hasattr(r, "error")
        assert hasattr(r, "model_available")

    def test_source_and_target_lang_preserved(self) -> None:
        """The result must carry the input source and target language codes."""
        with patch(
            "app.ai.multilingual.multilingual_pipeline.MarianTokenizer.from_pretrained",
            side_effect=OSError("not found"),
        ):
            result = translate_text("policy", source_lang="en", target_lang="sn")

        assert result.source_lang == "en"
        assert result.target_lang == "sn"

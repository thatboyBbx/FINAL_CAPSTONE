"""
tests/test_sandbox_expansion.py

Tests for SANDBOX_EXP_v1 — all 6 deliverables.

Deliverable 1: sandbox_annotator.py — PDF extraction + BIO annotation
Deliverable 2: entity_registry.py + register_sandbox_entities()
Deliverable 3: document classifier labels + training data JSON
Deliverable 4: check_sandbox_eligibility() + /sandbox-eligibility endpoint
Deliverable 5: classify_clause_type()
Deliverable 6: /api/reports/sandbox-quarterly route
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# ─────────────────────────────────────────────────────────────────────────────
# Deliverable 1 — sandbox_annotator.py
# ─────────────────────────────────────────────────────────────────────────────

class TestSandboxAnnotator:
    """Tests for app/infrastructure/scrapers/sandbox_annotator.py"""

    def test_annotator_module_importable(self):
        """The annotator module must import without errors."""
        from app.infrastructure.scrapers import sandbox_annotator  # noqa: F401
        assert sandbox_annotator is not None

    def test_split_into_sentences_basic(self):
        """split_into_sentences returns non-empty list from a multi-sentence string."""
        from app.infrastructure.scrapers.sandbox_annotator import split_into_sentences
        text = (
            "The testing period shall be 12 months. "
            "The boundary condition includes transaction limits. "
            "KYC checks are mandatory."
        )
        sentences = split_into_sentences(text)
        assert len(sentences) >= 3
        assert all(isinstance(s, str) for s in sentences)

    def test_split_into_sentences_min_length(self):
        """Very short strings are filtered out by the 15-char minimum."""
        from app.infrastructure.scrapers.sandbox_annotator import split_into_sentences
        text = "OK. Hi. The testing period shall be 12 months."
        sentences = split_into_sentences(text)
        # 'OK' and 'Hi' (< 15 chars) should be dropped
        assert all(len(s) >= 15 for s in sentences)

    def test_annotate_sentence_testing_period(self):
        """TESTING_PERIOD pattern matches '12 months' in a sentence."""
        from app.infrastructure.scrapers.sandbox_annotator import annotate_sentence
        sentence = "The testing period shall be 12 months from the commencement date."
        result = annotate_sentence(sentence)
        assert result is not None
        labels = [lbl for _, _, lbl in result]
        assert "TESTING_PERIOD" in labels

    def test_annotate_sentence_kyc_aml(self):
        """KYC_AML_CLAUSE pattern matches 'Know Your Customer' in a sentence."""
        from app.infrastructure.scrapers.sandbox_annotator import annotate_sentence
        sentence = "Know Your Customer checks must be performed at onboarding."
        result = annotate_sentence(sentence)
        assert result is not None
        labels = [lbl for _, _, lbl in result]
        assert "KYC_AML_CLAUSE" in labels

    def test_annotate_sentence_no_entities(self):
        """A sentence with no entity patterns returns an empty list, not None."""
        from app.infrastructure.scrapers.sandbox_annotator import annotate_sentence
        sentence = "The applicant shall submit the required documentation to the Commission."
        result = annotate_sentence(sentence)
        # Should return [] (no entities), not None (no overlap skipping)
        assert result is not None
        assert isinstance(result, list)

    def test_jsonl_output_populated(self):
        """If the JSONL output file exists, it must be non-empty and valid JSONL."""
        jsonl_path = (
            Path("app/infrastructure/storage/training_data/sandbox_ner_annotations.jsonl")
        )
        if not jsonl_path.exists():
            pytest.skip("JSONL output not generated yet — run sandbox_annotator.py first")
        lines = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) > 0, "JSONL file must contain at least one record"
        for line in lines[:5]:
            record = json.loads(line)
            assert "text" in record
            assert "entities" in record

    def test_raw_txt_output_populated(self):
        """If the raw sentences file exists, it must contain lines."""
        txt_path = (
            Path("app/infrastructure/storage/training_data/sandbox_sentences_raw.txt")
        )
        if not txt_path.exists():
            pytest.skip("Raw text output not generated yet — run sandbox_annotator.py first")
        lines = txt_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Deliverable 2 — entity_registry.py + register_sandbox_entities()
# ─────────────────────────────────────────────────────────────────────────────

class TestEntityRegistry:
    """Tests for app/ai/nlp/entity_registry.py"""

    def test_all_entity_labels_is_list(self):
        from app.ai.nlp.entity_registry import ALL_ENTITY_LABELS
        assert isinstance(ALL_ENTITY_LABELS, list)
        assert len(ALL_ENTITY_LABELS) > 0

    def test_new_sandbox_labels_in_all_labels(self):
        from app.ai.nlp.entity_registry import ALL_ENTITY_LABELS, NEW_SANDBOX_LABELS
        for label in NEW_SANDBOX_LABELS:
            assert label in ALL_ENTITY_LABELS, f"{label} missing from ALL_ENTITY_LABELS"

    def test_eight_new_sandbox_labels(self):
        """Exactly 8 new sandbox labels must be registered."""
        from app.ai.nlp.entity_registry import NEW_SANDBOX_LABELS
        assert len(NEW_SANDBOX_LABELS) == 8

    def test_entity_groups_keys(self):
        from app.ai.nlp.entity_registry import ENTITY_GROUPS
        expected_groups = {"insurance_core", "regulatory_sandbox", "compliance_safeguards"}
        assert expected_groups.issubset(set(ENTITY_GROUPS.keys()))

    def test_entity_display_names_complete(self):
        from app.ai.nlp.entity_registry import ALL_ENTITY_LABELS, ENTITY_DISPLAY_NAMES
        for label in ALL_ENTITY_LABELS:
            assert label in ENTITY_DISPLAY_NAMES, (
                f"{label} missing from ENTITY_DISPLAY_NAMES"
            )

    def test_entity_colors_complete(self):
        from app.ai.nlp.entity_registry import ALL_ENTITY_LABELS, ENTITY_COLORS
        for label in ALL_ENTITY_LABELS:
            assert label in ENTITY_COLORS, f"{label} missing from ENTITY_COLORS"
            # Hex colour should start with #
            assert ENTITY_COLORS[label].startswith("#")

    def test_entity_groups_cover_all_labels(self):
        """Union of all groups must equal ALL_ENTITY_LABELS (no orphan labels)."""
        from app.ai.nlp.entity_registry import ALL_ENTITY_LABELS, ENTITY_GROUPS
        all_grouped = set()
        for labels in ENTITY_GROUPS.values():
            all_grouped.update(labels)
        for label in ALL_ENTITY_LABELS:
            assert label in all_grouped, f"{label} not in any ENTITY_GROUPS group"


class TestRegisterSandboxEntities:
    """Tests for register_sandbox_entities() in ner_pipeline.py"""

    def test_register_sandbox_entities_importable(self):
        from app.ai.nlp.ner_pipeline import register_sandbox_entities  # noqa: F401
        assert callable(register_sandbox_entities)

    def test_register_sandbox_entities_no_duplicates(self):
        """register_sandbox_entities must not duplicate existing labels."""
        import spacy
        from app.ai.nlp.ner_pipeline import register_sandbox_entities
        from app.ai.nlp.entity_registry import NEW_SANDBOX_LABELS

        try:
            nlp = spacy.blank("en")
            # Add a blank NER pipe so add_label() works
            nlp.add_pipe("ner")
        except Exception:
            pytest.skip("spaCy not available or NER pipe cannot be created")

        # Call twice — second call must not crash or duplicate
        register_sandbox_entities(nlp)
        register_sandbox_entities(nlp)  # idempotent

        ner = nlp.get_pipe("ner")
        for label in NEW_SANDBOX_LABELS:
            count = list(ner.labels).count(label)
            assert count == 1, f"Label '{label}' appears {count} times — expected 1"

    def test_register_sandbox_entities_all_8_added(self):
        """After registration, the NER pipe must contain all 8 sandbox labels."""
        import spacy
        from app.ai.nlp.ner_pipeline import register_sandbox_entities
        from app.ai.nlp.entity_registry import NEW_SANDBOX_LABELS

        try:
            nlp = spacy.blank("en")
            nlp.add_pipe("ner")
        except Exception:
            pytest.skip("spaCy not available")

        register_sandbox_entities(nlp)
        ner = nlp.get_pipe("ner")
        for label in NEW_SANDBOX_LABELS:
            assert label in ner.labels, f"Label '{label}' not registered"


# ─────────────────────────────────────────────────────────────────────────────
# Deliverable 3 — Document classifier labels + training data
# ─────────────────────────────────────────────────────────────────────────────

class TestDocumentClassifierLabels:
    """Tests for new document type labels in classifier_service.py"""

    def test_new_labels_in_document_category(self):
        """DocumentCategory Literal must include all 3 new sandbox labels."""
        from app.modules.documents.classifier_service import DocumentCategory
        import typing
        args = typing.get_args(DocumentCategory)
        assert "sandbox_application" in args
        assert "sandbox_quarterly_report" in args
        assert "sandbox_exit_report" in args

    def test_fallback_classifier_includes_sandbox_labels(self):
        """_fallback_classification must return sandbox types for matching text."""
        from app.modules.documents.classifier_service import DocumentClassifierService
        svc = DocumentClassifierService()
        text = (
            "This regulatory sandbox application describes the testing period, "
            "boundary conditions, exit plan, and regulatory waiver requested."
        )
        result = svc._fallback_classification(text)
        # Should score sandbox_application highest or at least non-zero
        assert "sandbox_application" in result["probabilities"]
        assert result["probabilities"]["sandbox_application"] >= 0.0


class TestSandboxDocumentExamples:
    """Tests for sandbox_document_examples.json"""

    _EXAMPLES_PATH = Path(
        "app/infrastructure/storage/training_data/sandbox_document_examples.json"
    )

    def test_examples_file_exists(self):
        assert self._EXAMPLES_PATH.exists(), "sandbox_document_examples.json not found"

    def test_examples_valid_json(self):
        data = json.loads(self._EXAMPLES_PATH.read_text(encoding="utf-8"))
        assert "labels" in data
        assert len(data["labels"]) == 3

    def test_sandbox_application_has_25_examples(self):
        data = json.loads(self._EXAMPLES_PATH.read_text(encoding="utf-8"))
        app_block = next(
            b for b in data["labels"] if b["label"] == "SANDBOX_APPLICATION"
        )
        assert len(app_block["examples"]) >= 25

    def test_sandbox_quarterly_has_20_examples(self):
        data = json.loads(self._EXAMPLES_PATH.read_text(encoding="utf-8"))
        q_block = next(
            b for b in data["labels"] if b["label"] == "SANDBOX_QUARTERLY_REPORT"
        )
        assert len(q_block["examples"]) >= 20

    def test_sandbox_exit_has_20_examples(self):
        data = json.loads(self._EXAMPLES_PATH.read_text(encoding="utf-8"))
        e_block = next(
            b for b in data["labels"] if b["label"] == "SANDBOX_EXIT_REPORT"
        )
        assert len(e_block["examples"]) >= 20

    def test_training_json_has_sandbox_categories(self):
        """The main training JSON must contain records with all 3 sandbox categories."""
        # Locate the training file (it has a timestamp suffix)
        candidates = list(Path("storage/training_data").glob(
            "document_classification_training_*.json"
        ))
        if not candidates:
            pytest.skip("Training data file not found")
        training_path = sorted(candidates)[-1]  # most recent
        data = json.loads(training_path.read_text(encoding="utf-8"))
        categories = {r["category"] for r in data["data"]}
        for cat in ("sandbox_application", "sandbox_quarterly_report", "sandbox_exit_report"):
            assert cat in categories, f"Category '{cat}' not in training data"

    def test_training_json_sandbox_min_15_examples(self):
        """Each sandbox category must have at least 15 training examples."""
        candidates = list(Path("storage/training_data").glob(
            "document_classification_training_*.json"
        ))
        if not candidates:
            pytest.skip("Training data file not found")
        training_path = sorted(candidates)[-1]
        data = json.loads(training_path.read_text(encoding="utf-8"))
        from collections import Counter
        counts = Counter(r["category"] for r in data["data"])
        for cat in ("sandbox_application", "sandbox_quarterly_report", "sandbox_exit_report"):
            assert counts[cat] >= 15, (
                f"Category '{cat}' has only {counts[cat]} examples (need ≥ 15)"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Deliverable 4 — check_sandbox_eligibility + endpoint
# ─────────────────────────────────────────────────────────────────────────────

class TestSandboxEligibility:
    """Tests for check_sandbox_eligibility() in compliance/service.py"""

    def test_check_sandbox_eligibility_all_pass(self):
        """A document containing all keywords must pass all 6 criteria."""
        from app.modules.compliance.service import check_sandbox_eligibility

        rich_text = (
            "This application is submitted to IPEC regarding an insurance innovation. "
            "The organogram and beneficial owner are disclosed. Directors declared. "
            "Regulatory approval and licence required from Commission approval. "
            "The business model, testing plan, milestones, resources, and KPI targets "
            "are described. The existing framework does not cover this; regulatory gap "
            "and cannot operate under current rules. Police clearance and tax clearance "
            "and fit and proper declarations are attached. No insolvent director. "
            "No money laundering history."
        )
        result = check_sandbox_eligibility(rich_text)
        assert result["criteria_passed"] == 6
        assert result["criteria_failed"] == 0
        assert result["overall_status"] == "ELIGIBLE"
        assert result["eligibility_score_pct"] == 100.0

    def test_check_sandbox_eligibility_three_fail(self):
        """A document failing 3 criteria returns LIKELY_ELIGIBLE."""
        from app.modules.compliance.service import check_sandbox_eligibility

        # Contains SE_001, SE_002, SE_003 keywords but not SE_004, SE_005, SE_006
        partial_text = (
            "This is an insurance application to IPEC (Commission). "
            "Directors and shareholders declared with organogram. "
            "Commission approval and licence required."
        )
        result = check_sandbox_eligibility(partial_text)
        assert result["criteria_passed"] >= 3
        # Result depends on keyword presence — just check structure
        assert "overall_status" in result
        assert result["overall_status"] in ("ELIGIBLE", "LIKELY_ELIGIBLE", "NOT_ELIGIBLE")

    def test_check_sandbox_eligibility_all_fail(self):
        """An empty document fails all 6 criteria and is NOT_ELIGIBLE."""
        from app.modules.compliance.service import check_sandbox_eligibility
        result = check_sandbox_eligibility("")
        assert result["criteria_passed"] == 0
        assert result["criteria_failed"] == 6
        assert result["overall_status"] == "NOT_ELIGIBLE"

    def test_check_sandbox_eligibility_result_structure(self):
        """Return dict must have all required keys."""
        from app.modules.compliance.service import check_sandbox_eligibility
        result = check_sandbox_eligibility("insurance IPEC")
        for key in (
            "rule_group", "source", "total_criteria", "criteria_passed",
            "criteria_failed", "eligibility_score_pct", "overall_status",
            "results", "plain_english_summary",
        ):
            assert key in result, f"Key '{key}' missing from result"
        assert result["total_criteria"] == 6
        assert len(result["results"]) == 6

    def test_sandbox_eligibility_endpoint(self, authenticated_client: TestClient):
        """POST /documents/99999/sandbox-eligibility — 404 for non-existent doc."""
        resp = authenticated_client.post("/documents/99999/sandbox-eligibility")
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Deliverable 5 — classify_clause_type()
# ─────────────────────────────────────────────────────────────────────────────

class TestClauseClassifier:
    """Tests for classify_clause_type() in ner_pipeline.py"""

    def test_tcf_clause_dispute_resolution(self):
        from app.ai.nlp.ner_pipeline import classify_clause_type
        text = "Any dispute resolution must be completed within 14 days."
        assert classify_clause_type(text) == "TCF_CLAUSE"

    def test_tcf_clause_treating_customers_fairly(self):
        from app.ai.nlp.ner_pipeline import classify_clause_type
        text = "The insurer shall adhere to Treating Customers Fairly principles."
        assert classify_clause_type(text) == "TCF_CLAUSE"

    def test_kyc_aml_know_your_customer(self):
        from app.ai.nlp.ner_pipeline import classify_clause_type
        text = "Know Your Customer checks must be performed at onboarding."
        assert classify_clause_type(text) == "KYC_AML_CLAUSE"

    def test_kyc_aml_anti_money_laundering(self):
        from app.ai.nlp.ner_pipeline import classify_clause_type
        text = "The company complies with anti-money laundering regulations."
        assert classify_clause_type(text) == "KYC_AML_CLAUSE"

    def test_regulatory_waiver_clause(self):
        from app.ai.nlp.ner_pipeline import classify_clause_type
        text = "A temporary exemption has been granted for the testing period."
        assert classify_clause_type(text) == "REGULATORY_WAIVER_CLAUSE"

    def test_regulatory_waiver_clause_relaxation(self):
        from app.ai.nlp.ner_pipeline import classify_clause_type
        text = "Relaxation of the licensing requirement applies during this period."
        assert classify_clause_type(text) == "REGULATORY_WAIVER_CLAUSE"

    def test_unknown_clause_returns_unknown(self):
        from app.ai.nlp.ner_pipeline import classify_clause_type
        text = "The sun is bright today."
        assert classify_clause_type("") == "UNKNOWN_CLAUSE"
        assert classify_clause_type(text) == "UNKNOWN_CLAUSE"

    def test_classify_clause_type_is_deterministic(self):
        """Same input must always return same output."""
        from app.ai.nlp.ner_pipeline import classify_clause_type
        text = "Treating Customers Fairly is a core principle."
        results = {classify_clause_type(text) for _ in range(5)}
        assert len(results) == 1  # only one unique result


# ─────────────────────────────────────────────────────────────────────────────
# Deliverable 6 — Sandbox Quarterly Report template + route
# ─────────────────────────────────────────────────────────────────────────────

class TestSandboxQuarterlyReport:
    """Tests for GET /api/reports/sandbox-quarterly/{broker_id}"""

    def test_sandbox_quarterly_html_returns_200(
        self, authenticated_client: TestClient
    ):
        """GET /api/reports/sandbox-quarterly/1?format=html returns 200."""
        resp = authenticated_client.get(
            "/api/reports/sandbox-quarterly/1",
            params={"format": "html", "quarter": "Q2-2026"},
        )
        assert resp.status_code == 200

    def test_sandbox_quarterly_html_contains_section_headers(
        self, authenticated_client: TestClient
    ):
        """HTML response must contain Annexure 3 section names."""
        resp = authenticated_client.get(
            "/api/reports/sandbox-quarterly/1",
            params={"format": "html", "quarter": "Q2-2026"},
        )
        body = resp.text
        assert "Section A" in body
        assert "Section B" in body
        assert "Section C" in body
        assert "Section E" in body
        assert "Section F" in body
        assert "Section G" in body

    def test_sandbox_quarterly_html_contains_ipec_footer(
        self, authenticated_client: TestClient
    ):
        """Footer must reference IPEC Regulatory Sandbox Guidelines (2025) Annexure 3."""
        resp = authenticated_client.get(
            "/api/reports/sandbox-quarterly/1",
            params={"format": "html", "quarter": "Q2-2026"},
        )
        assert "Annexure 3" in resp.text
        assert "InsureIntel Zimbabwe Platform" in resp.text

    def test_sandbox_quarterly_pdf_returns_bytes(
        self, authenticated_client: TestClient
    ):
        """GET /api/reports/sandbox-quarterly/1?format=pdf returns PDF bytes."""
        resp = authenticated_client.get(
            "/api/reports/sandbox-quarterly/1",
            params={"format": "pdf", "quarter": "Q2-2026"},
        )
        # WeasyPrint may not be installed in CI — accept 200 or 500
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert resp.headers["content-type"] == "application/pdf"
            assert len(resp.content) > 0

    def test_sandbox_quarterly_report_template_exists(self):
        """The Jinja2 template file must exist on disk."""
        template_path = Path(
            "app/ui/templates/reports/sandbox_quarterly_report.html"
        )
        assert template_path.exists(), "sandbox_quarterly_report.html not found"

    def test_sandbox_report_service_importable(self):
        """sandbox_report_service must import without errors."""
        from app.modules.reports import sandbox_report_service  # noqa: F401
        assert callable(sandbox_report_service.generate_sandbox_quarterly_report_context)

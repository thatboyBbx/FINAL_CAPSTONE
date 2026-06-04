import io

from fastapi.testclient import TestClient


POLICY_TEXT = """
Insurance policy wording for ABC Manufacturing.
The policy includes premium, coverage limits, deductible, claims notification,
governing law, cancellation, and dispute resolution clauses. The insurer shall
comply with IPEC requirements and maintain appropriate claims settlement controls.
""" * 4


class _FakeClassifier:
    def classify(self, text: str) -> dict:
        return {
            "category": "policy_wording",
            "confidence": 0.91,
            "method": "test_stub",
            "probabilities": {"policy_wording": 0.91, "unknown": 0.09},
        }


class _FakeExtractor:
    def extract_entities(self, document_id: int, text: str, db) -> dict:
        return {
            "entities_found": 2,
            "entities_by_type": {"INSURED": 1, "INSURER": 1},
            "entities": [
                {"entity_type": "INSURED", "entity_value": "ABC Manufacturing"},
                {"entity_type": "INSURER", "entity_value": "Test Insurer"},
            ],
            "processing_time_ms": 3.5,
        }


class _FakeComplianceChecker:
    def check_compliance(self, document_text: str, document_type: str = "all") -> dict:
        return {
            "compliance_score": 92.0,
            "status": "compliant",
            "mandatory_clauses": {
                "total_required": 3,
                "found": 3,
                "missing": [],
                "present": ["cancellation", "claims_notification", "dispute_resolution"],
            },
            "prohibited_terms": {"found": 0, "violations": []},
            "recommendations": ["No blocking compliance issues found."],
        }


def test_upload_process_compliance_report_flow(authenticated_client: TestClient, monkeypatch):
    """Critical production smoke flow: upload -> process -> compliance -> report."""
    import app.ai.rag.indexing_pipeline as rag_indexing
    import app.modules.compliance.service as compliance_service
    import app.modules.documents.classifier_service as classifier_service
    import app.modules.documents.entity_extraction_service as entity_service
    import app.modules.documents.ingestion as ingestion
    import app.modules.documents.ingestion.pdf_extractor as pdf_extractor

    monkeypatch.setattr(pdf_extractor, "extract_text_from_pdf", lambda *args, **kwargs: POLICY_TEXT)
    monkeypatch.setattr(ingestion, "extract_text", lambda *args, **kwargs: POLICY_TEXT)
    monkeypatch.setattr(classifier_service, "DocumentClassifierService", _FakeClassifier)
    monkeypatch.setattr(entity_service, "EntityExtractionService", _FakeExtractor)
    monkeypatch.setattr(compliance_service, "get_compliance_checker", lambda: _FakeComplianceChecker())
    monkeypatch.setattr(
        rag_indexing,
        "index_document",
        lambda document_id, db: {"chunks_created": 1, "status": "indexed"},
    )

    upload = authenticated_client.post(
        "/api/documents/upload",
        data={
            "title": "E2E Policy",
            "uploaded_by_user_id": "999999",
            "document_category": "policy_wording",
            "status_value": "uploaded",
        },
        files={"file": ("e2e-policy.pdf", io.BytesIO(b"%PDF-1.4\n% e2e smoke\n"), "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    document = upload.json()
    document_id = document["id"]
    assert document["uploaded_by_user_id"] != 999999

    processed = authenticated_client.post(f"/api/documents/{document_id}/process/sync")
    assert processed.status_code == 200, processed.text
    processed_json = processed.json()
    assert processed_json["document_id"] == document_id
    assert processed_json["document_category"] == "policy_wording"
    assert processed_json["compliance_status"] == "compliant"

    compliance = authenticated_client.get(f"/api/documents/{document_id}/compliance")
    assert compliance.status_code == 200, compliance.text
    assert compliance.json()["status"] == "compliant"
    assert compliance.json()["compliance_score"] == 92.0

    report = authenticated_client.post(
        "/api/reports/generate",
        json={"document_id": document_id, "report_type": "compliance"},
    )
    assert report.status_code == 200, report.text[:300]
    assert report.headers["content-type"] == "application/pdf"
    assert report.content.startswith(b"%PDF")

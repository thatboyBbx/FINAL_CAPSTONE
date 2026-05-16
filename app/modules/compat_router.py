from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.documents import service as document_service
from app.modules.documents.model import ComplianceCheck, Document


router = APIRouter(dependencies=[Depends(get_current_user)], tags=["compat"])


class DocumentIdRequest(BaseModel):
    document_id: int


class AnalysisMlRequest(BaseModel):
    document_ids: list[int]
    analysis_types: list[str] = []


class AnalysisDeviationRequest(BaseModel):
    template_id: int | None = None
    document_ids: list[int]


class KnowledgeBaseAskRequest(BaseModel):
    question: str


def _run_compliance_check(db: Session, document_id: int) -> dict[str, Any]:
    from app.modules.compliance.service import get_compliance_checker
    from app.modules.documents.ingestion import extract_text

    document = document_service.get_document_by_id(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    text = extract_text(document.file_path)
    if not text or len(text.strip()) < 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot run compliance check because text extraction failed.",
        )

    result = get_compliance_checker().check_compliance(document_text=text, document_type="all")
    try:
        db.add(document_service._build_compliance_check(document_id, result))
        db.commit()
    except Exception:
        db.rollback()
    return result


def _latest_or_fresh_compliance(db: Session, document_id: int) -> dict[str, Any]:
    latest = (
        db.query(ComplianceCheck)
        .filter(ComplianceCheck.document_id == document_id)
        .order_by(ComplianceCheck.checked_at.desc())
        .first()
    )
    if latest:
        return {
            "compliance_score": latest.compliance_score,
            "status": latest.status,
            "mandatory_clauses": {
                "total_required": latest.mandatory_required,
                "found": latest.mandatory_found,
                "missing": json.loads(latest.mandatory_missing) if latest.mandatory_missing else [],
                "present": [],
            },
            "prohibited_terms": {
                "found": latest.prohibited_found,
                "violations": json.loads(latest.prohibited_violations) if latest.prohibited_violations else [],
            },
            "recommendations": json.loads(latest.recommendations) if latest.recommendations else [],
        }
    return _run_compliance_check(db, document_id)


@router.post("/api/compliance/check")
def compat_compliance_check(payload: DocumentIdRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _run_compliance_check(db, payload.document_id)


@router.get("/api/compliance/check/{document_id}")
def compat_compliance_recheck(document_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _run_compliance_check(db, document_id)


@router.post("/api/analysis/risk")
def compat_analysis_risk(payload: DocumentIdRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    compliance = _latest_or_fresh_compliance(db, payload.document_id)
    compliance_score = float(compliance.get("compliance_score", 0) or 0)
    risk_score = max(0.0, min(100.0, 100.0 - compliance_score))
    if risk_score >= 70:
        risk_level = "High"
    elif risk_score >= 40:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    missing = compliance.get("mandatory_clauses", {}).get("missing", []) or []
    violations = compliance.get("prohibited_terms", {}).get("violations", []) or []
    risk_factors: list[dict[str, Any]] = []
    if missing:
        risk_factors.append(
            {
                "name": "Missing mandatory clauses",
                "description": f"{len(missing)} required clause(s) missing.",
                "severity": "high" if len(missing) >= 2 else "medium",
                "score": min(10, len(missing) * 3),
            }
        )
    if violations:
        risk_factors.append(
            {
                "name": "Prohibited wording detected",
                "description": f"{len(violations)} prohibited term violation(s) found.",
                "severity": "high",
                "score": min(10, len(violations) * 3),
            }
        )

    return {
        "document_id": payload.document_id,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_factors": risk_factors,
        "recommendations": compliance.get("recommendations", []),
        "source": "compliance_compat",
    }


@router.post("/api/analysis/ner")
def compat_analysis_ner(payload: DocumentIdRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    result = document_service.process_document_full(db=db, document_id=payload.document_id)
    entities = document_service.get_document_entities(db, payload.document_id)
    return {
        "document_id": payload.document_id,
        "entities_found": len(entities),
        "entities_by_type": result.get("entities_by_type", {}),
        "entities": entities,
        "processing_time_ms": result.get("processing_time_ms"),
    }


@router.post("/api/analysis/ml")
def compat_analysis_ml(payload: AnalysisMlRequest, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    analysis_types = {item.lower() for item in payload.analysis_types}

    for document_id in payload.document_ids:
        document = document_service.get_document_by_id(db, document_id)
        if not document:
            results.append({"document_id": document_id, "error": "Document not found."})
            continue

        item: dict[str, Any] = {
            "document_id": document_id,
            "title": document.title,
            "requested_analysis_types": sorted(analysis_types),
        }

        try:
            if analysis_types & {"ner", "clause"}:
                process_result = document_service.process_document_full(db=db, document_id=document_id)
                item["classification"] = {
                    "document_category": process_result.get("document_category"),
                    "confidence": process_result.get("classification_confidence"),
                    "method": process_result.get("classification_method"),
                }
                item["entities_by_type"] = process_result.get("entities_by_type", {})

            if "risk" in analysis_types:
                item["risk"] = compat_analysis_risk(DocumentIdRequest(document_id=document_id), db)

            if "clause" in analysis_types:
                from app.modules.deviation.clause_scorer import get_clause_scorer

                scorer = get_clause_scorer(db)
                item["clause_analysis"] = scorer.score_document(document_id, db)
        except Exception as exc:
            item["error"] = str(exc)

        results.append(item)

    return results


@router.post("/api/analysis/deviation")
def compat_analysis_deviation(
    payload: AnalysisDeviationRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from app.modules.deviation.clause_scorer import get_clause_scorer

    scorer = get_clause_scorer(db)
    results = []
    for document_id in payload.document_ids:
        results.append(
            {
                "document_id": document_id,
                "template_id": payload.template_id,
                "analysis": scorer.score_document(document_id, db),
            }
        )
    return {"template_id": payload.template_id, "results": results}


@router.post("/api/knowledge-base/ask")
def compat_knowledge_base_ask(
    payload: KnowledgeBaseAskRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from app.ai.rag.qa_engine import QAEngine

    documents = db.query(Document).order_by(Document.created_at.desc()).limit(10).all()
    if not documents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No documents available in the knowledge base.")

    combined_chunks: list[str] = []
    for document in documents:
        text = document_service.extract_document_text(db, document.id)
        if text:
            title = document.title or document.original_filename or f"Document #{document.id}"
            combined_chunks.append(f"{title}\n{text[:4000]}")

    if not combined_chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No searchable document text is available yet.",
        )

    engine = QAEngine()
    result = engine.answer(
        document_id="knowledge-base",
        question=payload.question,
        document_title="Knowledge Base",
        document_text="\n\n".join(combined_chunks),
    )
    return result


@router.post("/api/documents/compare")
def compat_documents_compare(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
) -> Any:
    from app.modules.comparison.service import ComparisonService
    from app.modules.comparison.router import CompareRequest
    from app.modules.documents.model import Document as DocumentModel

    request = CompareRequest(**payload)
    document_a_id, document_b_id = request.resolved_ids()

    for doc_id in (document_a_id, document_b_id):
        if not db.query(DocumentModel).filter(DocumentModel.id == doc_id).first():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document id={doc_id} not found.",
            )

    report = ComparisonService().compare(document_a_id, document_b_id, db)
    return {
        "status": "complete",
        "document_a_id": document_a_id,
        "document_b_id": document_b_id,
        **report,
    }


@router.get("/documents/compliance/statistics")
def compat_documents_compliance_statistics(db: Session = Depends(get_db)) -> dict[str, Any]:
    from app.modules.documents.router import get_compliance_statistics

    return get_compliance_statistics(db)


@router.get("/documents/{document_id:int}")
def compat_document_redirect(document_id: int) -> RedirectResponse:
    return RedirectResponse(url=f"/documents-ui/{document_id}", status_code=307)


@router.get("/document-detail/{document_id:int}")
def compat_document_detail_redirect(document_id: int) -> RedirectResponse:
    return RedirectResponse(url=f"/documents-ui/{document_id}", status_code=307)

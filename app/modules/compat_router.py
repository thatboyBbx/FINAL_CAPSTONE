from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.access_control import require_document_access
from app.modules.auth.dependencies import get_current_user
from app.modules.compliance.model import ComplianceResult
from app.modules.documents import service as document_service
from app.modules.documents.model import Document
from app.modules.users.model import User


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


class AdvisoryAnalyseRequest(BaseModel):
    document_id: int


_SOURCE_ROOT = (Path(__file__).resolve().parents[2] / "sources" / "downloads" / "SOURCES").resolve()
_KB_SOURCE_REFERENCES = [
    ("Insurance Act [Chapter 24:07]", "Insurance Act.pdf"),
    ("Insurance and Pensions Commission Act", "Insurance and Pensions Commission Act.pdf"),
    ("Regulatory Sandbox Guidelines", "REGULATORY-SANDBOX-GUIDELINES-FOR-THE-INSURANCE-AND-PENSIONS-INDUSTRY-.pdf"),
    ("ZICARP Frameworks - Circular 32 of 2023", "Circular 32 of 2023 - ZICARP Final Frameworks - 29 Nov 2023.pdf"),
    ("Overall Risk Based Capital Framework (TS 1)", "TS 1 -  Overall Risk Based Capital Framework.pdf"),
    ("Minimum Capital Requirement (TS 5)", "TS 5 - Determination of Minimum Capital Requirement.pdf"),
    ("Ladder of Supervisory Intervention (GRS 11)", "GRS 11 Ladder of Supervisory Intervention.pdf"),
]
_MANDATORY_CLAUSES_PATH = (Path(__file__).resolve().parents[2] / "sources" / "kb" / "mandatory_clauses.json").resolve()


@router.post("/api/advisory/analyse")
def analyse_advisory(
    payload: AdvisoryAnalyseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Compatibility endpoint used by the advisory UI."""
    document = require_document_access(db, current_user, payload.document_id)

    from app.modules.insurers.model import Insurer

    insurers = (
        db.query(Insurer)
        .filter(Insurer.ipec_registration_status == "active")
        .order_by(Insurer.name)
        .limit(5)
        .all()
    )
    recommendations = [
        {
            "name": insurer.name,
            "match_score": max(0.55, 0.9 - (idx * 0.06)),
            "csp_score": None,
            "gap_summary": (
                "Review policy wording, claims history, and current IPEC standing "
                "before placement."
            ),
        }
        for idx, insurer in enumerate(insurers)
    ]

    category = document.document_category or "unclassified"
    return {
        "document_id": document.id,
        "summary": (
            f"Advisory generated for {document.title or document.original_filename}. "
            f"Document category: {category}. Recommendations are limited to available "
            "registry data and should be reviewed by a broker before placement."
        ),
        "recommended_insurers": recommendations,
        "gap_analysis": [
            "Confirm coverage limits, exclusions, and deductibles against client needs.",
            "Verify insurer registration status and settlement capacity before binding.",
        ],
    }


@lru_cache(maxsize=16)
def _extract_source_pdf_text(source_file: str) -> str:
    from app.modules.documents.ingestion.pdf_extractor import extract_text_from_pdf

    path = (_SOURCE_ROOT / source_file).resolve()
    if not path.exists() or _SOURCE_ROOT not in path.parents:
        return ""
    return extract_text_from_pdf(path, max_pages=12) or ""


def _knowledge_source_chunks(question: str) -> list[dict[str, str]]:
    terms = {
        term.strip(".,:;!?()[]{}").lower()
        for term in question.split()
        if len(term.strip(".,:;!?()[]{}")) >= 4
    }
    ranked_refs = sorted(
        _KB_SOURCE_REFERENCES,
        key=lambda ref: sum(1 for term in terms if term in f"{ref[0]} {ref[1]}".lower()),
        reverse=True,
    )
    selected_refs = [ref for ref in ranked_refs if any(term in f"{ref[0]} {ref[1]}".lower() for term in terms)]
    if not selected_refs:
        selected_refs = ranked_refs[:4]
    elif len(selected_refs) < 3:
        selected_refs = selected_refs + [ref for ref in ranked_refs if ref not in selected_refs][: 3 - len(selected_refs)]

    chunks: list[dict[str, str]] = []
    for title, source_file in selected_refs[:4]:
        text = _extract_source_pdf_text(source_file).strip()
        if text:
            chunks.append(
                {
                    "title": title,
                    "source": source_file,
                    "text": f"{title}\nSource file: {source_file}\n{text[:12000]}",
                }
            )
    return chunks


def _knowledge_source_excerpts(question: str, chunks: list[dict[str, str]]) -> list[dict[str, str]]:
    terms = [
        term.strip(".,:;!?()[]{}").lower()
        for term in question.split()
        if len(term.strip(".,:;!?()[]{}")) >= 4
    ]
    excerpts: list[dict[str, str]] = []
    for chunk in chunks:
        sentences = [
            re.sub(r"\s+", " ", sentence).strip()
            for sentence in re.split(r"(?<=[.!?])\s+", chunk["text"])
        ]
        ranked = sorted(
            [sentence for sentence in sentences if len(sentence) > 40],
            key=lambda sentence: sum(1 for term in terms if term in sentence.lower()),
            reverse=True,
        )
        best = next((sentence for sentence in ranked if any(term in sentence.lower() for term in terms)), "")
        if best:
            excerpts.append(
                {
                    "title": chunk["title"],
                    "source": chunk["source"],
                    "excerpt": best[:700],
                }
            )
    return excerpts[:5]


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
        db.add(document_service._build_compliance_result(document_id, result))
        db.commit()
    except Exception:
        db.rollback()
    return result


def _process_document_for_ml(db: Session, document: Document) -> dict[str, Any]:
    from app.modules.documents.classifier_service import DocumentClassifierService
    from app.modules.documents.entity_extraction_service import EntityExtractionService

    text = document_service.extract_document_text(db, document.id)
    if not text or len(text.strip()) < 50:
        return {
            "document_id": document.id,
            "error": "Insufficient text extracted from document.",
            "text_length": len(text or ""),
            "classification": {
                "document_category": document.document_category,
                "confidence": document.classification_confidence,
                "method": document.classification_method,
            },
            "entities_by_type": {},
            "entities": [],
            "processing_time_ms": 0,
        }

    classifier = DocumentClassifierService()
    classification = classifier.classify(text)
    document.document_category = classification["category"]
    document.classification_confidence = classification["confidence"]
    document.classification_method = classification["method"]
    document.classified_at = datetime.now(timezone.utc)
    db.commit()

    extraction = EntityExtractionService().extract_entities(
        document_id=document.id,
        text=text,
        db=db,
    )

    return {
        "document_id": document.id,
        "text_length": len(text),
        "document_text": text,
        "classification": {
            "document_category": classification["category"],
            "confidence": classification["confidence"],
            "method": classification["method"],
        },
        "entities_by_type": extraction.get("entities_by_type", {}),
        "entities": extraction.get("entities", []),
        "entities_found": extraction.get("entities_found", 0),
        "processing_time_ms": extraction.get("processing_time_ms", 0),
        "rag_indexing_status": "skipped_for_ml_analytics",
    }


def _score_text_clauses_for_ml(document_id: int, text: str, scorer: Any) -> dict[str, Any]:
    from app.modules.deviation.clause_scorer import _chunk_text_as_clauses

    clauses = _chunk_text_as_clauses(text, document_id)
    scores = []
    label_counts: dict[str, int] = {}
    for clause in clauses:
        result = scorer.score_clause(clause.get("text", ""), clause.get("clause_type", "general"))
        label = result.get("deviation_label", "unknown")
        label_counts[label] = label_counts.get(label, 0) + 1
        scores.append(
            {
                "clause_type": clause.get("clause_type", "general"),
                "clause_text": clause.get("text", "")[:300],
                **result,
            }
        )
    numeric_scores = [
        float(score["deviation_score"])
        for score in scores
        if score.get("deviation_score") is not None
    ]
    high_deviation = [
        score for score in scores
        if (score.get("deviation_score") or 0) > 0.55
    ]
    return {
        "document_id": document_id,
        "total_clauses_scored": len(scores),
        "deviation_summary": label_counts,
        "high_deviation_clauses": high_deviation,
        "avg_deviation_score": round(sum(numeric_scores) / len(numeric_scores), 4) if numeric_scores else 0.0,
        "scores": scores,
        "source": "ml_text_chunk_fallback",
    }


def _ensure_mandatory_standard_clauses(db: Session) -> dict[str, int]:
    from app.modules.deviation.model import StandardClause
    from app.modules.shared.clause_classifier import classify_clause_type

    if not _MANDATORY_CLAUSES_PATH.exists():
        return {"loaded": 0, "inserted": 0}

    data = json.loads(_MANDATORY_CLAUSES_PATH.read_text(encoding="utf-8"))
    clauses = data.get("clauses", []) if isinstance(data, dict) else []
    inserted = 0

    for clause in clauses:
        requirement = str(clause.get("requirement") or "").strip()
        section = str(clause.get("section") or "").strip()
        description = str(clause.get("description") or "").strip()
        keywords = ", ".join(clause.get("keywords") or [])
        text = ". ".join(part for part in [requirement, section, description, f"Keywords: {keywords}" if keywords else ""] if part)
        if not text:
            continue

        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        existing = db.query(StandardClause).filter(StandardClause.text_hash == text_hash).first()
        if existing:
            continue

        db.add(
            StandardClause(
                text=text,
                clause_type=classify_clause_type(text),
                source=f"mandatory_clauses.json:{clause.get('id') or requirement}",
                jurisdiction=data.get("jurisdiction", "Zimbabwe"),
                text_hash=text_hash,
            )
        )
        inserted += 1

    if inserted:
        db.commit()
        try:
            import app.modules.deviation.clause_scorer as clause_scorer_module

            clause_scorer_module._cached_scorer = None
        except Exception:
            pass

    return {"loaded": len(clauses), "inserted": inserted}


def _latest_or_fresh_compliance(db: Session, document_id: int) -> dict[str, Any]:
    latest = (
        db.query(ComplianceResult)
        .filter(ComplianceResult.document_id == document_id)
        .order_by(ComplianceResult.checked_at.desc())
        .first()
    )
    if latest:
        clause_results = json.loads(latest.clause_results) if latest.clause_results else {}
        violations = (
            json.loads(latest.prohibited_terms_found)
            if latest.prohibited_terms_found
            else []
        )
        return {
            "compliance_score": latest.compliance_score,
            "status": latest.status,
            "mandatory_clauses": {
                "total_required": clause_results.get("total_required", 0),
                "found": clause_results.get("found", 0),
                "missing": json.loads(latest.missing_mandatory_clauses)
                if latest.missing_mandatory_clauses
                else [],
                "present": clause_results.get("present", []),
            },
            "prohibited_terms": {
                "found": len(violations),
                "violations": violations,
            },
            "recommendations": json.loads(latest.summary) if latest.summary else [],
        }
    return _run_compliance_check(db, document_id)


@router.post("/api/compliance/check")
def compat_compliance_check(
    payload: DocumentIdRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    require_document_access(db, current_user, payload.document_id)
    return _run_compliance_check(db, payload.document_id)


@router.get("/api/compliance/check/{document_id}")
def compat_compliance_recheck(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    require_document_access(db, current_user, document_id)
    return _run_compliance_check(db, document_id)


@router.post("/api/analysis/risk")
def compat_analysis_risk(
    payload: DocumentIdRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    require_document_access(db, current_user, payload.document_id)
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
        "compliance_score": compliance_score,
        "compliance_status": compliance.get("status"),
        "risk_factors": risk_factors,
        "recommendations": compliance.get("recommendations", []),
        "source": "compliance_compat",
    }


@router.post("/api/analysis/ner")
def compat_analysis_ner(
    payload: DocumentIdRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    require_document_access(db, current_user, payload.document_id)
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
def compat_analysis_ml(
    payload: AnalysisMlRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    analysis_types = {item.lower() for item in payload.analysis_types}
    if not analysis_types:
        analysis_types = {"risk", "ner", "clause"}

    for document_id in payload.document_ids:
        try:
            document = require_document_access(db, current_user, document_id)
        except HTTPException as exc:
            results.append({"document_id": document_id, "error": exc.detail})
            continue

        item: dict[str, Any] = {
            "document_id": document_id,
            "title": document.title,
            "file_size": document.file_size,
            "requested_analysis_types": sorted(analysis_types),
        }

        try:
            process_result: dict[str, Any] = {}
            if analysis_types & {"ner", "clause"}:
                process_result = _process_document_for_ml(db, document)
                item.update(
                    {
                        "text_length": process_result.get("text_length", 0),
                        "classification": process_result.get("classification", {}),
                        "entities_by_type": process_result.get("entities_by_type", {}),
                        "entities": process_result.get("entities", [])[:25],
                        "entities_found": process_result.get("entities_found", 0),
                        "processing_time_ms": process_result.get("processing_time_ms", 0),
                        "rag_indexing_status": process_result.get("rag_indexing_status"),
                    }
                )
                if process_result.get("error"):
                    item.setdefault("warnings", []).append(process_result["error"])

            if "risk" in analysis_types:
                item["risk"] = _latest_or_fresh_compliance(db, document_id)
                compliance_score = float(item["risk"].get("compliance_score", 0) or 0)
                item["risk"] = {
                    **item["risk"],
                    "risk_score": max(0.0, min(100.0, 100.0 - compliance_score)),
                }

            if "clause" in analysis_types:
                from app.modules.deviation.clause_scorer import get_clause_scorer

                scorer = get_clause_scorer(db)
                try:
                    item["clause_analysis"] = scorer.score_document(document_id, db)
                    if (
                        item["clause_analysis"].get("total_clauses_scored", 0) == 0
                        and process_result.get("document_text")
                    ):
                        item["clause_analysis"] = _score_text_clauses_for_ml(
                            document_id=document_id,
                            text=process_result["document_text"],
                            scorer=scorer,
                        )
                except Exception as exc:
                    item["clause_analysis"] = {
                        "document_id": document_id,
                        "total_clauses_scored": 0,
                        "deviation_summary": {},
                        "high_deviation_clauses": [],
                        "avg_deviation_score": 0.0,
                        "scores": [],
                        "error": str(exc),
                    }
                    item.setdefault("warnings", []).append(f"Clause analysis skipped: {exc}")
        except Exception as exc:
            item["error"] = str(exc)

        results.append(item)

    risk_scores = [
        float(item["risk"]["risk_score"])
        for item in results
        if item.get("risk") and item["risk"].get("risk_score") is not None
    ]
    compliance_scores = [
        float(item["risk"]["compliance_score"])
        for item in results
        if item.get("risk") and item["risk"].get("compliance_score") is not None
    ]
    clause_total = sum(
        int(
            (item.get("clause_analysis") or {}).get("total_clauses_scored")
            or (item.get("clause_analysis") or {}).get("total_clauses")
            or 0
        )
        for item in results
    )
    text_characters = sum(int(item.get("text_length") or 0) for item in results)
    file_bytes = sum(int(item.get("file_size") or 0) for item in results)
    entity_total = sum(int(item.get("entities_found") or 0) for item in results)
    entity_types = {
        entity_type
        for item in results
        for entity_type in (item.get("entities_by_type") or {}).keys()
    }
    category_counts: dict[str, int] = {}
    for item in results:
        category = (item.get("classification") or {}).get("document_category") or "unknown"
        category_counts[category] = category_counts.get(category, 0) + 1

    summary = {
        "documents_requested": len(payload.document_ids),
        "documents_analyzed": len([item for item in results if not item.get("error")]),
        "analysis_types": sorted(analysis_types),
        "average_risk_score": round(sum(risk_scores) / len(risk_scores), 2) if risk_scores else 0.0,
        "average_compliance_score": round(sum(compliance_scores) / len(compliance_scores), 2) if compliance_scores else None,
        "high_risk_documents": len([score for score in risk_scores if score >= 70]),
        "entities_found": entity_total,
        "entity_types_found": len(entity_types),
        "clauses_scored": clause_total,
        "text_characters": text_characters,
        "file_bytes": file_bytes,
        "category_distribution": category_counts,
    }

    return {"summary": summary, "results": results}


@router.post("/api/analysis/deviation")
def compat_analysis_deviation(
    payload: AnalysisDeviationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    from app.modules.deviation.clause_scorer import get_clause_scorer

    standard_source = _ensure_mandatory_standard_clauses(db)
    scorer = get_clause_scorer(db)
    results = []
    for document_id in payload.document_ids:
        require_document_access(db, current_user, document_id)
        results.append(
            {
                "document_id": document_id,
                "template_id": None,
                "standard_source": "sources/kb/mandatory_clauses.json",
                "analysis": scorer.score_document(document_id, db),
            }
        )
    return {
        "template_id": None,
        "standard_source": "sources/kb/mandatory_clauses.json",
        "standard_source_stats": standard_source,
        "results": results,
    }


@router.post("/api/knowledge-base/ask")
def compat_knowledge_base_ask(
    payload: KnowledgeBaseAskRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from app.ai.rag.qa_engine import QAEngine

    source_chunks = _knowledge_source_chunks(payload.question)
    if source_chunks:
        engine = QAEngine()
        result = engine.answer(
            document_id="knowledge-base-sources",
            question=payload.question,
            document_title="Knowledge Base Source Directory",
            document_text="\n\n".join(chunk["text"] for chunk in source_chunks),
        )
        excerpts = _knowledge_source_excerpts(payload.question, source_chunks)
        result["sources"] = [chunk["source"] for chunk in source_chunks]
        result["source_excerpts"] = excerpts
        if excerpts:
            result["answer"] = (
                f"{result.get('answer', '').strip()}\n\n"
                "Source-backed excerpts:\n"
                + "\n".join(
                    f"- {item['title']} ({item['source']}): {item['excerpt']}"
                    for item in excerpts[:3]
                )
            )
        return result

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
    result["sources"] = [chunk.split("\n", 1)[0] for chunk in combined_chunks[:5]]
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
    summary = report.get("summary") or {}
    return {
        "status": "complete",
        "document_a_id": document_a_id,
        "document_b_id": document_b_id,
        "added_count": int(summary.get("added") or 0),
        "removed_count": int(summary.get("removed") or 0),
        "changed_count": int(summary.get("modified") or 0),
        "unchanged_count": int(summary.get("identical") or 0),
        "summary_text": _comparison_summary_text(report),
        "diff_lines": _comparison_diff_lines(report),
        **report,
    }


def _comparison_summary_text(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    doc_a = (report.get("document_a") or {}).get("filename") or "Document A"
    doc_b = (report.get("document_b") or {}).get("filename") or "Document B"
    total_a = int(summary.get("total_clauses_a") or 0)
    total_b = int(summary.get("total_clauses_b") or 0)
    modified = int(summary.get("modified") or 0)
    added = int(summary.get("added") or 0)
    removed = int(summary.get("removed") or 0)
    identical = int(summary.get("identical") or 0)

    if total_a and not total_b:
        return (
            f"{doc_a} produced {total_a} clause sections, but {doc_b} produced no extractable "
            "clause sections. The comparison therefore treats the base document clauses as removed "
            "from the comparison document."
        )
    if total_b and not total_a:
        return (
            f"{doc_b} produced {total_b} clause sections, but {doc_a} produced no extractable "
            "clause sections. The comparison therefore treats the comparison document clauses as added."
        )
    return (
        f"Compared {total_a} base clauses with {total_b} comparison clauses: "
        f"{identical} unchanged, {modified} changed, {added} added, and {removed} removed."
    )


def _comparison_diff_lines(report: dict[str, Any], limit: int = 80) -> list[str]:
    lines: list[str] = []
    for change in (report.get("all_changes") or [])[:limit]:
        status_value = change.get("status")
        text = (
            ((change.get("clause_b") or {}).get("text"))
            or ((change.get("clause_a") or {}).get("text"))
            or change.get("change_summary")
            or ""
        )
        prefix = {
            "added": "+",
            "removed": "-",
            "modified": "?",
            "identical": " ",
        }.get(status_value, " ")
        if text:
            lines.append(f"{prefix} {change.get('change_summary') or text[:220]}")
    return lines


@router.get("/documents/compliance/statistics")
def compat_documents_compliance_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    from app.modules.documents.router import get_compliance_statistics

    return get_compliance_statistics(db, current_user)


@router.get("/documents/{document_id:int}")
def compat_document_redirect(document_id: int) -> RedirectResponse:
    return RedirectResponse(url=f"/documents-ui/{document_id}", status_code=307)


@router.get("/document-detail/{document_id:int}")
def compat_document_detail_redirect(document_id: int) -> RedirectResponse:
    return RedirectResponse(url=f"/documents-ui/{document_id}", status_code=307)

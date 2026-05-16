"""
Batch processing tasks — run as FastAPI BackgroundTasks (thread-safe).
Each task creates its own DB session.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def process_single_document(document_id: int) -> dict:
    """
    Full processing pipeline for a single document.
    Called as a FastAPI BackgroundTask — creates its own DB session.

    Pipeline:
      1. Mark document as 'processing'
      2. Extract text (existing extractor)
      3. Run NLP analysis (existing circulars NLP)
      4. Run risk scoring (existing fusion)
      5. RAG index (Advancement 1)
      6. Clause deviation scoring (Advancement 4)
      7. Policy tracker sync (Advancement 6)
      8. Mark document as 'complete'; update batch progress
    """
    from app.core.db import SessionLocal
    from app.modules.documents.model import Document
    from app.modules.batch.model import ProcessingBatch

    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.error("process_single_document: doc %d not found", document_id)
            return {"status": "error", "reason": "document not found"}

        batch_id = getattr(doc, "batch_id", None)

        # Step 1 — mark processing
        doc.status = "processing"
        db.commit()

        risk_score = 0.0
        compliance_score = 0.0

        # Step 2+3 — text extraction + NLP analysis
        try:
            from app.modules.circulars.extractor import extract_text, clean_text
            from app.modules.circulars.nlp import extract_entities, score_risk_signals, categorise_circular
            from app.modules.circulars.model import CircularAnalysis

            text = clean_text(extract_text(doc.file_path))
            if text:
                entities = extract_entities(text)
                risk_signals = score_risk_signals(text)
                category_info = categorise_circular(text)

                # Upsert CircularAnalysis
                analysis = (
                    db.query(CircularAnalysis)
                    .filter(CircularAnalysis.document_id == document_id)
                    .first()
                )
                if not analysis:
                    analysis = CircularAnalysis(document_id=document_id)
                    db.add(analysis)

                analysis.extracted_text = text
                analysis.nlp_risk_score = risk_signals.get("total_risk_score", 0.0)
                analysis.compliance_signal = risk_signals.get("compliance", 0)
                analysis.financial_stress_signal = risk_signals.get("financial_stress", 0)
                analysis.claims_signal = risk_signals.get("claims", 0)
                analysis.regulatory_signal = risk_signals.get("regulatory", 0)
                analysis.market_conduct_signal = risk_signals.get("market_conduct", 0)
                analysis.total_risk_signals = sum(
                    v for k, v in risk_signals.items() if isinstance(v, int)
                )
                analysis.predicted_category = category_info.get("category")
                analysis.category_confidence = category_info.get("confidence")
                analysis.dates_found = "|".join(entities.get("dates", []))
                analysis.monetary_values_found = "|".join(entities.get("monetary_values", []))
                analysis.regulatory_refs_found = "|".join(entities.get("regulatory_refs", []))
                analysis.insurer_mentions_found = "|".join(entities.get("insurer_mentions", []))
                analysis.status = "analysed"

                db.commit()
                db.refresh(analysis)
                compliance_score = float(category_info.get("confidence", 0.0))
        except Exception as exc:
            logger.warning("NLP pipeline failed for doc %d: %s", document_id, exc)

        # Step 4 — risk scoring (best-effort)
        try:
            from app.modules.scoring.fusion import fuse_risk_scores
            result = fuse_risk_scores(db, document_id)
            if result:
                risk_score = float(getattr(result, "fused_score", 0.0))
        except Exception as exc:
            logger.warning("Risk scoring failed for doc %d: %s", document_id, exc)

        # Step 5 — RAG indexing
        try:
            from app.ai.rag.indexing_pipeline import index_document
            index_document(document_id, db)
        except Exception as exc:
            logger.warning("RAG indexing failed for doc %d: %s", document_id, exc)

        # Step 6 — clause deviation scoring
        try:
            from app.modules.deviation.clause_scorer import get_clause_scorer
            scorer = get_clause_scorer(db)
            scorer.score_document(document_id, db)
        except Exception as exc:
            logger.warning("Deviation scoring failed for doc %d: %s", document_id, exc)

        # Step 7 — policy tracker sync
        try:
            from app.modules.tracker.service import PolicyTrackerService
            PolicyTrackerService().sync_from_document(db, document_id)
        except Exception as exc:
            logger.warning("Policy tracker sync failed for doc %d: %s", document_id, exc)

        # Step 8 — mark complete and update batch
        doc.status = "complete"
        db.commit()

        if batch_id:
            _update_batch_progress(db, batch_id)

        logger.info("Document %d processed successfully.", document_id)
        return {
            "document_id": document_id,
            "status": "complete",
            "risk_score": risk_score,
            "compliance_score": compliance_score,
        }

    except Exception as exc:
        logger.error("process_single_document failed for doc %d: %s", document_id, exc)
        try:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.status = "failed"
                db.commit()
            if batch_id:
                _update_batch_progress(db, batch_id, failed=True)
        except Exception:
            pass
        return {"document_id": document_id, "status": "failed", "error": str(exc)}
    finally:
        db.close()


def _update_batch_progress(db, batch_id: int, failed: bool = False) -> None:
    """Increment batch completed/failed count and set status when all done."""
    from app.modules.batch.model import ProcessingBatch
    from app.modules.documents.model import Document

    batch = db.query(ProcessingBatch).filter(ProcessingBatch.id == batch_id).first()
    if not batch:
        return

    if failed:
        batch.failed_count = (batch.failed_count or 0) + 1
    else:
        batch.completed_count = (batch.completed_count or 0) + 1

    done = (batch.completed_count or 0) + (batch.failed_count or 0)
    if done >= (batch.total_documents or 0):
        batch.status = "complete" if (batch.failed_count or 0) == 0 else "partial_failure"
        batch.completed_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except Exception as exc:
        logger.warning("Failed to update batch %d progress: %s", batch_id, exc)
        db.rollback()

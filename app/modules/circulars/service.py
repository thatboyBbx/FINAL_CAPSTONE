from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.circulars.classifier import get_classifier
from app.modules.circulars.extractor import clean_text, extract_text
from app.modules.circulars.model import CircularAnalysis
from app.modules.circulars.nlp import CircularNLPAnalyser
from app.modules.circulars.repo import CircularRepo
from app.modules.documents.repo import get_document_by_id


_repo = CircularRepo()
_nlp  = CircularNLPAnalyser()


def analyse_document(db: Session, document_id: int) -> CircularAnalysis:
    """
    Full pipeline:
      1. Load document record + file path
      2. Extract text from PDF/DOCX
      3. Run NLP analysis (entities, risk signals)
      4. Run DL classifier (MLP on TF-IDF)
      5. Persist + return CircularAnalysis record
    """
    doc = get_document_by_id(db, document_id)
    if not doc:
        raise ValueError(f"Document {document_id} not found.")

    # --- Text extraction ---
    raw_text = extract_text(doc.file_path)
    text = clean_text(raw_text)

    if not text:
        text = f"{doc.title} {doc.document_category or ''} {doc.notes or ''}"

    # --- NLP analysis ---
    nlp_result = _nlp.analyse(text)

    # --- DL classifier ---
    classifier = get_classifier()
    if not classifier.is_trained():
        classifier.train(use_proxy=True)

    dl_result = classifier.predict_with_nlp(text, nlp_result=nlp_result)

    # --- Build DB record ---
    analysis = CircularAnalysis(
        document_id=document_id,
        extracted_text=text[:10000],   # cap stored text at 10k chars

        risk_level=dl_result["risk_level"],
        risk_class=dl_result["risk_class"],
        prob_low=dl_result["probabilities"]["low"],
        prob_moderate=dl_result["probabilities"]["moderate"],
        prob_high=dl_result["probabilities"]["high"],
        fused_risk_level=dl_result["fused_risk_level"],
        fused_risk_score=dl_result["fused_risk_score"],

        predicted_category=dl_result["predicted_category"],
        category_confidence=dl_result["category_confidence"],
        nlp_risk_score=dl_result["nlp_risk_score"],

        compliance_signal=nlp_result.compliance_signal,
        financial_stress_signal=nlp_result.financial_stress_signal,
        claims_signal=nlp_result.claims_signal,
        regulatory_signal=nlp_result.regulatory_signal,
        market_conduct_signal=nlp_result.market_conduct_signal,
        total_risk_signals=nlp_result.total_risk_signals,

        dates_found="|".join(nlp_result.dates[:10]),
        monetary_values_found="|".join(nlp_result.monetary_values[:10]),
        regulatory_refs_found="|".join(nlp_result.regulatory_refs[:10]),
        insurer_mentions_found="|".join(nlp_result.insurer_mentions[:5]),

        model_label=dl_result["model"],
        status="analysed",
    )

    return _repo.upsert(db, analysis)


def train_classifier(
    texts: list[str] | None = None,
    labels: list[int] | None = None,
) -> dict:
    """Train (or retrain) the DL classifier, optionally with real labelled circulars."""
    classifier = get_classifier()
    return classifier.train(texts=texts, labels=labels, use_proxy=True)


def get_analysis(db: Session, document_id: int) -> CircularAnalysis | None:
    return _repo.get_by_document_id(db, document_id)


def list_analyses(db: Session, skip: int = 0, limit: int = 100) -> list[CircularAnalysis]:
    return _repo.list_all(db, skip=skip, limit=limit)


def risk_summary(db: Session) -> dict[str, int]:
    return _repo.count_by_risk(db)

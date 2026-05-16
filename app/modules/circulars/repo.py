from sqlalchemy.orm import Session

from app.modules.circulars.model import CircularAnalysis


class CircularRepo:
    def get_by_document_id(self, db: Session, document_id: int) -> CircularAnalysis | None:
        return db.query(CircularAnalysis).filter(
            CircularAnalysis.document_id == document_id
        ).first()

    def list_all(self, db: Session, skip: int = 0, limit: int = 100) -> list[CircularAnalysis]:
        return (
            db.query(CircularAnalysis)
            .order_by(CircularAnalysis.analysed_at.desc())
            .offset(skip).limit(limit).all()
        )

    def list_by_risk(self, db: Session, risk_level: str) -> list[CircularAnalysis]:
        return (
            db.query(CircularAnalysis)
            .filter(CircularAnalysis.fused_risk_level == risk_level)
            .order_by(CircularAnalysis.analysed_at.desc())
            .all()
        )

    def upsert(self, db: Session, analysis: CircularAnalysis) -> CircularAnalysis:
        existing = self.get_by_document_id(db, analysis.document_id)
        if existing:
            for col in CircularAnalysis.__table__.columns:
                if col.name not in ("id", "document_id", "analysed_at"):
                    setattr(existing, col.name, getattr(analysis, col.name))
            db.commit()
            db.refresh(existing)
            return existing
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        return analysis

    def count_by_risk(self, db: Session) -> dict[str, int]:
        rows = db.query(
            CircularAnalysis.fused_risk_level,
        ).all()
        counts: dict[str, int] = {"low": 0, "moderate": 0, "high": 0, "unknown": 0}
        for (level,) in rows:
            key = level if level in counts else "unknown"
            counts[key] += 1
        return counts

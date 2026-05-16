from sqlalchemy.orm import Session
from sqlalchemy import select

from app.modules.insurers.model import Insurer
from app.modules.insurers.schemas import InsurerCreate


class InsurerRepo:
    def create(self, db: Session, payload: InsurerCreate) -> Insurer:
        insurer = Insurer(
            name=payload.name.strip(),
            country=(payload.country.strip() if payload.country else None),
            industry_segment=(payload.industry_segment.strip() if payload.industry_segment else None),
        )
        db.add(insurer)
        db.commit()
        db.refresh(insurer)
        return insurer

    def get(self, db: Session, insurer_id: int) -> Insurer | None:
        return db.get(Insurer, insurer_id)

    def get_by_name(self, db: Session, name: str) -> Insurer | None:
        stmt = select(Insurer).where(Insurer.name == name.strip())
        return db.execute(stmt).scalars().first()

    def list(self, db: Session, skip: int = 0, limit: int = 50) -> list[Insurer]:
        stmt = select(Insurer).offset(skip).limit(limit)
        return list(db.execute(stmt).scalars().all())

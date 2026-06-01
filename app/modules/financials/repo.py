from datetime import date, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.pagination import normalize_pagination
from app.modules.financials.model import FinancialSnapshot


class FinancialRepo:
    def create_many(self, db: Session, snapshots: list[FinancialSnapshot]) -> int:
        db.add_all(snapshots)
        db.commit()
        return len(snapshots)

    def list_by_insurer(self, db: Session, insurer_id: int, skip: int = 0, limit: int = 200) -> list[FinancialSnapshot]:
        skip, limit = normalize_pagination(skip, limit)
        stmt = (
            select(FinancialSnapshot)
            .where(FinancialSnapshot.insurer_id == insurer_id)
            .order_by(desc(FinancialSnapshot.reporting_date))
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    def latest(self, db: Session, insurer_id: int) -> FinancialSnapshot | None:
        stmt = (
            select(FinancialSnapshot)
            .where(FinancialSnapshot.insurer_id == insurer_id)
            .order_by(desc(FinancialSnapshot.reporting_date))
            .limit(1)
        )
        return db.execute(stmt).scalars().first()

    def list_by_range(self, db: Session, insurer_id: int, start: date, end: date) -> list[FinancialSnapshot]:
        stmt = (
            select(FinancialSnapshot)
            .where(FinancialSnapshot.insurer_id == insurer_id)
            .where(FinancialSnapshot.reporting_date >= start)
            .where(FinancialSnapshot.reporting_date <= end)
            .order_by(desc(FinancialSnapshot.reporting_date))
        )
        return list(db.execute(stmt).scalars().all())

    def list_last_days(self, db: Session, insurer_id: int, days: int) -> list[FinancialSnapshot]:
        """
        Returns snapshots in the last `days` days relative to the latest available reporting_date
        for this insurer (not relative to today's date).
        """
        if days <= 0:
            return []

        end = db.execute(
            select(func.max(FinancialSnapshot.reporting_date)).where(
                FinancialSnapshot.insurer_id == insurer_id
            )
        ).scalar_one_or_none()
        if not end:
            return []

        start = end - timedelta(days=days)

        return self.list_by_range(db, insurer_id, start=start, end=end)

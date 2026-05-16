from sqlalchemy.orm import Session

from app.modules.insurers.repo import InsurerRepo
from app.modules.insurers.schemas import InsurerCreate
from app.modules.insurers.model import Insurer


class InsurerService:
    def __init__(self) -> None:
        self.repo = InsurerRepo()

    def create_insurer(self, db: Session, payload: InsurerCreate) -> Insurer:
        existing = self.repo.get_by_name(db, payload.name)
        if existing:
            raise ValueError("Insurer with this name already exists.")
        return self.repo.create(db, payload)

    def get_insurer(self, db: Session, insurer_id: int) -> Insurer | None:
        return self.repo.get(db, insurer_id)

    def list_insurers(self, db: Session, skip: int = 0, limit: int = 50) -> list[Insurer]:
        return self.repo.list(db, skip=skip, limit=limit)

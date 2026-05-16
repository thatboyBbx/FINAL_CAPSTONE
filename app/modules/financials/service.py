import csv
import io
from datetime import datetime, date
from sqlalchemy.orm import Session

from app.modules.financials.model import FinancialSnapshot
from app.modules.financials.repo import FinancialRepo

from app.modules.insurers.repo import InsurerRepo
from app.modules.insurers.schemas import InsurerCreate


class FinancialService:
    def __init__(self) -> None:
        self.repo = FinancialRepo()
        self.insurer_repo = InsurerRepo()

    def _parse_date(self, s: str) -> date:
        s = (s or "").strip()
        # Expecting YYYY-MM-DD for consistency
        return datetime.strptime(s, "%Y-%m-%d").date()

    def _parse_float(self, s: str) -> float:
        """
        Handles common formats:
        - "1,200,000"
        - " 1200000 "
        - "$1,200,000" (we strip currency symbols)
        """
        if s is None:
            raise ValueError("Missing numeric value")
        s = s.strip()
        for ch in ["$", "€", "£", "ZWL", "USD"]:
            s = s.replace(ch, "")
        s = s.replace(",", "").strip()
        if s == "":
            raise ValueError("Empty numeric value")
        return float(s)

    def upload_csv(
        self,
        db: Session,
        csv_bytes: bytes,
        create_missing_insurers: bool = True
    ) -> dict:
        """
        CSV required columns:
          insurer_name, reporting_date, claims_reserves, claims_paid, premiums_written, liquidity_ratio

        reporting_date must be YYYY-MM-DD
        """
        text = csv_bytes.decode("utf-8-sig")  # handles BOM if present
        reader = csv.DictReader(io.StringIO(text))

        required = {
            "insurer_name",
            "reporting_date",
            "claims_reserves",
            "claims_paid",
            "premiums_written",
            "liquidity_ratio",
        }

        if not reader.fieldnames:
            raise ValueError("CSV has no header row.")

        missing_cols = required - set([h.strip() for h in reader.fieldnames])
        if missing_cols:
            raise ValueError(f"CSV missing required columns: {sorted(missing_cols)}")

        created = 0
        skipped = 0
        errors: list[dict] = []
        snapshots: list[FinancialSnapshot] = []

        row_num = 1  # header is row 1
        for row in reader:
            row_num += 1
            try:
                insurer_name = (row.get("insurer_name") or "").strip()
                if not insurer_name:
                    raise ValueError("insurer_name is empty")

                insurer = self.insurer_repo.get_by_name(db, insurer_name)
                if not insurer:
                    if not create_missing_insurers:
                        raise ValueError(f"Insurer '{insurer_name}' not found and create_missing_insurers=false")
                    insurer = self.insurer_repo.create(
                        db,
                        InsurerCreate(name=insurer_name, country=None, industry_segment=None)
                    )

                reporting_date = self._parse_date(row.get("reporting_date"))

                claims_reserves = self._parse_float(row.get("claims_reserves"))
                claims_paid = self._parse_float(row.get("claims_paid"))
                premiums_written = self._parse_float(row.get("premiums_written"))
                liquidity_ratio = self._parse_float(row.get("liquidity_ratio"))

                # sanity checks (simple but strict)
                if claims_reserves < 0 or claims_paid < 0 or premiums_written < 0:
                    raise ValueError("Negative financial values are not allowed")
                if liquidity_ratio <= 0:
                    raise ValueError("liquidity_ratio must be > 0")

                snapshots.append(
                    FinancialSnapshot(
                        insurer_id=insurer.id,
                        reporting_date=reporting_date,
                        claims_reserves=claims_reserves,
                        claims_paid=claims_paid,
                        premiums_written=premiums_written,
                        liquidity_ratio=liquidity_ratio,
                    )
                )
                created += 1

            except Exception as e:
                skipped += 1
                errors.append({"row": row_num, "error": str(e)})

        if snapshots:
            self.repo.create_many(db, snapshots)

        return {
            "inserted": created,
            "skipped": skipped,
            "errors": errors[:20],  # cap for readability
        }

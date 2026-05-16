from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import random

from sqlalchemy.orm import Session

from app.modules.financials.model import FinancialSnapshot
from app.modules.insurers.model import Insurer


@dataclass
class SeedConfig:
    months: int = 6
    snapshots_per_month: int = 1
    seed: int = 42


def seed_financials_for_all_insurers(db: Session, cfg: SeedConfig) -> dict:
    random.seed(cfg.seed)

    insurers = db.query(Insurer).all()
    if not insurers:
        return {"status": "noop", "detail": "No insurers found to seed."}

    today = date.today()
    inserted = 0

    for ins in insurers:
        # Make each insurer slightly different
        base_prem = random.uniform(200_000, 2_000_000)
        base_res = random.uniform(500_000, 8_000_000)
        base_liq = random.uniform(0.9, 2.2)

        for m in range(cfg.months):
            d = today - timedelta(days=30 * m)

            # Simple dynamics
            prem = max(10_000.0, base_prem * random.uniform(0.85, 1.15))
            claims = max(1_000.0, prem * random.uniform(0.4, 1.2))
            reserves = max(50_000.0, base_res + random.uniform(-0.15, 0.15) * base_res - (m * random.uniform(5_000, 50_000)))
            liq = max(0.2, base_liq * random.uniform(0.85, 1.10))

            snap = FinancialSnapshot(
                insurer_id=ins.id,
                reporting_date=d,
                premiums_written=float(prem),
                claims_paid=float(claims),
                claims_reserves=float(reserves),
                liquidity_ratio=float(liq),
            )
            db.add(snap)
            inserted += 1

    db.commit()
    return {"status": "ok", "insurers_seeded": len(insurers), "snapshots_inserted": inserted}

from pydantic import BaseModel, Field
from datetime import date, datetime


class FinancialSnapshotCreate(BaseModel):
    insurer_id: int
    reporting_date: date

    claims_reserves: float = Field(ge=0)
    claims_paid: float = Field(ge=0)
    premiums_written: float = Field(ge=0)
    liquidity_ratio: float = Field(gt=0)


class FinancialSnapshotRead(BaseModel):
    id: int
    insurer_id: int
    reporting_date: date

    claims_reserves: float
    claims_paid: float
    premiums_written: float
    liquidity_ratio: float

    created_at: datetime

    model_config = {"from_attributes": True}

"""
app/modules/compliance/schemas.py
===================================
Pydantic v2 schemas for the compliance module.
"""
from __future__ import annotations

from pydantic import BaseModel


class ComplianceCheckRequest(BaseModel):
    document_text: str
    document_type: str = "all"


class ComplianceCheckResponse(BaseModel):
    compliance_score: float
    status: str
    mandatory_clauses: dict
    prohibited_terms: dict
    recommendations: list[str]

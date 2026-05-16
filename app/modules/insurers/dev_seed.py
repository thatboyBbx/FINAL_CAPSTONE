"""
Seed all IPEC-licensed Zimbabwe insurers (2022 registry).
Safe to call multiple times — only inserts missing names.
Covers: 20 short-term, 12 life assurance, 3 reinsurers, 8 funeral assurers,
        11 microinsurers, 29 brokers = 83 total entities.
"""
from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from app.modules.insurers.model import Insurer

logger = logging.getLogger(__name__)

# ── Master insurer list ────────────────────────────────────────────────────
# Each dict maps directly to Insurer model fields.

_SHORT_TERM = [
    {"name": "AFC Insurance",                          "short_name": "AFC Insurance",          "category": "short_term", "parent_group": "AFC Holdings",             "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Alliance Insurance",                     "short_name": "Alliance Insurance",     "category": "short_term",                                               "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Allied Insurance Ltd",                   "short_name": "Allied Insurance",       "category": "short_term",                                               "zse_listed": False, "head_office_city": "Harare"},
    {"name": "CBZ Insurance Limited",                  "short_name": "CBZ Insurance",          "category": "short_term", "parent_group": "CBZ Holdings",              "zse_listed": True,  "zse_ticker": "CBZ",  "head_office_city": "Harare"},
    {"name": "Cell Insurance Company Ltd",             "short_name": "Cell Insurance",         "category": "short_term",                                               "zse_listed": False, "head_office_city": "Harare", "icm_member": True},
    {"name": "Champions Insurance",                    "short_name": "Champions Insurance",    "category": "short_term",                                               "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Clarion Insurance",                      "short_name": "Clarion Insurance",      "category": "short_term",                                               "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Credit Insurance Zimbabwe",              "short_name": "CIZ",                    "category": "short_term",                                               "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Econet Insurance",                       "short_name": "Econet Insurance",       "category": "short_term", "parent_group": "Econet Wireless",           "zse_listed": True,  "zse_ticker": "ECO",  "head_office_city": "Harare"},
    {"name": "Empaya Insurance",                       "short_name": "Empaya Insurance",       "category": "short_term",                                               "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Evolution Insurance",                    "short_name": "Evolution Insurance",    "category": "short_term",                                               "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Export Credit Guarantee Company of Zimbabwe (Pvt) Ltd", "short_name": "ECGCZ", "category": "short_term",                                               "zse_listed": False, "head_office_city": "Harare"},
    {"name": "FBC Insurance",                          "short_name": "FBC Insurance",          "category": "short_term", "parent_group": "FBC Holdings",              "zse_listed": True,  "zse_ticker": "FBC",  "head_office_city": "Harare"},
    {"name": "Hamilton Insurance",                     "short_name": "Hamilton Insurance",     "category": "short_term",                                               "zse_listed": False, "head_office_city": "Harare"},
    {"name": "NicozDiamond Insurance",                 "short_name": "NicozDiamond",           "category": "short_term", "parent_group": "First Mutual Holdings Ltd", "zse_listed": True,  "zse_ticker": "FMHL", "head_office_city": "Harare"},
    {"name": "Old Mutual Insurance",                   "short_name": "OM Insurance",           "category": "short_term", "parent_group": "Old Mutual Ltd",            "zse_listed": True,  "zse_ticker": "OMU",  "head_office_city": "Harare"},
    {"name": "Quality Insurance",                      "short_name": "Quality Insurance",      "category": "short_term",                                               "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Safel Insurance",                        "short_name": "Safel Insurance",        "category": "short_term",                                               "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Sanctuary Insurance",                    "short_name": "Sanctuary Insurance",    "category": "short_term",                                               "zse_listed": False, "head_office_city": "Harare", "date_established": "2011-01-01"},
    {"name": "Zimnat Lion Insurance",                  "short_name": "Zimnat Lion",            "category": "short_term", "parent_group": "Zimnat Group",              "zse_listed": False, "head_office_city": "Harare"},
]

_LIFE = [
    {"name": "CBZ Life Limited",                       "short_name": "CBZ Life",               "category": "life_assurance", "parent_group": "CBZ Holdings",              "zse_listed": True,  "zse_ticker": "CBZ",  "head_office_city": "Harare"},
    {"name": "Doves Life Assurance",                   "short_name": "Doves Life",             "category": "life_assurance",                                               "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Econet Life (Pvt) Ltd",                  "short_name": "Econet Life",            "category": "life_assurance", "parent_group": "Econet Wireless",           "zse_listed": True,  "zse_ticker": "ECO",  "head_office_city": "Harare"},
    {"name": "Evolution Health & Life",                "short_name": "Evolution Life",         "category": "life_assurance",                                               "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Fidelity Life Assurance",                "short_name": "Fidelity Life",          "category": "life_assurance",                                               "zse_listed": True,  "zse_ticker": "FLA",  "head_office_city": "Harare"},
    {"name": "First Mutual Life Assurance Services",   "short_name": "FML Life",               "category": "life_assurance", "parent_group": "First Mutual Holdings Ltd", "zse_listed": True,  "zse_ticker": "FMHL", "head_office_city": "Harare"},
    {"name": "Heritage Life Assurance",                "short_name": "Heritage Life",          "category": "life_assurance",                                               "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Nhaka Life Assurance (Pvt) Ltd",         "short_name": "Nhaka Life",             "category": "life_assurance",                                               "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Nyaradzo Life Assurance",                "short_name": "Nyaradzo Life",          "category": "life_assurance",                                               "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Old Mutual Life Assurance",              "short_name": "OM Life",                "category": "life_assurance", "parent_group": "Old Mutual Ltd",            "zse_listed": True,  "zse_ticker": "OMU",  "head_office_city": "Harare"},
    {"name": "ZB Life Assurance",                      "short_name": "ZB Life",                "category": "life_assurance", "parent_group": "ZB Financial Holdings",     "zse_listed": True,  "zse_ticker": "ZBH",  "head_office_city": "Harare"},
    {"name": "Zimnat Life Assurance",                  "short_name": "Zimnat Life",            "category": "life_assurance", "parent_group": "Zimnat Group",              "zse_listed": False, "head_office_city": "Harare"},
]

_REINSURERS = [
    {"name": "ZimRe Holdings Limited",                 "short_name": "ZimRe",                  "category": "reinsurer",  "zse_listed": True, "zse_ticker": "ZIMR", "icm_member": True,  "head_office_city": "Harare"},
    {"name": "First Mutual Reinsurance Company",       "short_name": "FMRe",                   "category": "reinsurer",  "parent_group": "First Mutual Holdings Ltd", "zse_listed": True, "zse_ticker": "FMHL", "head_office_city": "Harare"},
    {"name": "Tropical Reinsurance Company",           "short_name": "Tropical Re",            "category": "reinsurer",  "zse_listed": False, "head_office_city": "Harare"},
]

_FUNERAL = [
    {"name": "First Funeral Assurance",                "category": "funeral_assurer", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Foundation Mutual Society",              "category": "funeral_assurer", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Moonlight Funeral Assurance & Services", "category": "funeral_assurer", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Orchid Funeral Assurance",               "category": "funeral_assurer", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Passion Funeral Assurance",              "category": "funeral_assurer", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Ruvimbo Funeral Assurance",              "category": "funeral_assurer", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Sunset Funeral Assurance",               "category": "funeral_assurer", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Vineyard Funeral Assurance",             "category": "funeral_assurer", "zse_listed": False, "head_office_city": "Harare"},
]

_MICRO = [
    {"name": "Bayce Microinsurance",                   "category": "microinsurer", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Clientsure Microinsurance",              "category": "microinsurer", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Coverlink Microinsurance (Pvt) Ltd",     "category": "microinsurer", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "EBA Microinsurance",                     "category": "microinsurer", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Ethical Microinsurance",                 "category": "microinsurer", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Golden Knot Microinsurance",             "category": "microinsurer", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Highground Microinsurance",              "category": "microinsurer", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Evolution Microinsurance",               "category": "microinsurer", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Microsure Microinsurance",               "category": "microinsurer", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Rise Capital Microinsurance",            "category": "microinsurer", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Zambuko Microinsurance",                 "category": "microinsurer", "zse_listed": False, "head_office_city": "Harare"},
]

_BROKERS = [
    {"name": "Amour Khan Insurance Brokers",           "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Bright Insurance Brokers",               "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Broksure Insurance Brokers",             "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Capital Insurance Brokers",              "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Care Insurance Brokers",                 "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "CBZ Risk Advisory Services",             "category": "broker", "zse_listed": False, "head_office_city": "Harare", "parent_group": "CBZ Holdings"},
    {"name": "Coverlink Insurance Brokers",            "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Eaton & Youngs",                         "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Entwide Insurance Brokers",              "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Eureka Insurance Brokers",               "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "First Sun Alliance Insurance Brokers",   "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Firstlink Insurance Brokers",            "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Glenrand M.I.B Zimbabwe",               "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Goldstick Insurance Brokers",            "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "HRIB (Pvt) Ltd",                        "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Hunt Adams & Associates",               "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "L.A.Guard Insurance Brokers",           "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Minerva Risk Solutions",                 "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Momentum Insurance Brokers",             "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Paul Mkondo Insurance Brokers",          "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Perpro Insurance Brokers",               "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Progressive Insurance Brokers",          "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Rainbow Insurance Brokers",              "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Safari Insurance Brokers",               "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Satib Insurance Brokers",               "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "TIB Insurance Brokers",                  "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Victory Insurance Brokers",              "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "WFDR (Pvt) Ltd",                        "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
    {"name": "Zimbabwe Insurance Brokers Limited",     "category": "broker", "zse_listed": False, "head_office_city": "Harare"},
]

# Combined master list
ALL_INSURERS: list[dict] = (
    _SHORT_TERM + _LIFE + _REINSURERS + _FUNERAL + _MICRO + _BROKERS
)

# ── Seed function ──────────────────────────────────────────────────────────

def seed_insurers(db: Session, cfg=None) -> dict:
    """
    Upsert all IPEC-licensed Zimbabwe insurers into the DB.
    Idempotent: skips existing names, inserts missing ones.
    Returns summary dict with counts.
    """
    from datetime import date as _date

    existing_names: set[str] = {
        row[0] for row in db.query(Insurer.name).all()
    }
    created = 0
    skipped = 0

    for data in ALL_INSURERS:
        if data["name"] in existing_names:
            skipped += 1
            continue
        try:
            # Parse date_established if supplied as string
            est = data.get("date_established")
            if isinstance(est, str):
                est = _date.fromisoformat(est)

            ins = Insurer(
                name                      = data["name"],
                short_name                = data.get("short_name", data["name"]),
                category                  = data.get("category"),
                parent_group              = data.get("parent_group"),
                zse_listed                = data.get("zse_listed", False),
                zse_ticker                = data.get("zse_ticker"),
                head_office_city          = data.get("head_office_city", "Harare"),
                country                   = "Zimbabwe",
                icm_member                = data.get("icm_member", False),
                pool_participant          = data.get("pool_participant", False),
                ipec_registration_status  = "active",
                date_established          = est,
                industry_segment          = None,   # legacy field, left empty
            )
            db.add(ins)
            created += 1
        except Exception as exc:
            logger.warning("Seed failed for %s: %s", data["name"], exc)
            db.rollback()
            continue

    try:
        db.commit()
    except Exception as exc:
        logger.warning("Insurer seed commit error: %s", exc)
        db.rollback()

    total = db.query(Insurer).count()
    return {
        "status":    "ok",
        "created":   created,
        "skipped":   skipped,
        "total_now": total,
    }

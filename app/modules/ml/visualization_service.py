"""
app/modules/ml/visualization_service.py
=========================================
Dashboard chart data builder. Moved from app/services/visualization_service.py.
Demo data dependency removed — visualizations now use real DB data or empty defaults.
"""
from __future__ import annotations


def _load_demo_rows() -> list[dict]:
    """Demo data source removed — returns empty list."""
    return []


def _round2(value: float) -> float:
    return round(value, 2)


def _group_sum(rows: list[dict], key_field: str, value_field: str) -> tuple[list[str], list[float]]:
    grouped: dict[str, float] = {}
    for row in rows:
        key = str(row[key_field])
        grouped[key] = grouped.get(key, 0.0) + float(row[value_field])
    labels = list(grouped.keys())
    values = [_round2(grouped[label]) for label in labels]
    return labels, values


def _group_avg(rows: list[dict], key_field: str, value_field: str) -> tuple[list[str], list[float]]:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        key = str(row[key_field])
        grouped.setdefault(key, []).append(float(row[value_field]))
    labels = list(grouped.keys())
    values = [_round2(sum(grouped[label]) / len(grouped[label])) for label in labels]
    return labels, values


def _group_count(rows: list[dict], key_field: str) -> tuple[list[str], list[int]]:
    grouped: dict[str, int] = {}
    for row in rows:
        key = str(row[key_field])
        grouped[key] = grouped.get(key, 0) + 1
    labels = list(grouped.keys())
    values = [grouped[label] for label in labels]
    return labels, values


def get_default_dashboard_visualizations() -> dict:
    rows = _load_demo_rows()

    insurer_claim_labels, insurer_claim_values = _group_sum(rows, "insurer", "claim_amount")
    insurer_settlement_labels, insurer_settlement_values = _group_avg(rows, "insurer", "settlement_days")
    policy_mix_labels, policy_mix_values = _group_count(rows, "policy_type")
    status_mix_labels, status_mix_values = _group_count(rows, "claim_status")
    avg_premium_labels, avg_premium_values = _group_avg(rows, "policy_type", "premium")
    avg_risk_labels, avg_risk_values = _group_avg(rows, "insurer", "risk_score")

    return {
        "insurer_claim_chart": {
            "title": "Total Claim Amount by Insurer",
            "chart_type": "bar",
            "labels": insurer_claim_labels,
            "values": insurer_claim_values,
        },
        "insurer_settlement_chart": {
            "title": "Average Settlement Days by Insurer",
            "chart_type": "line",
            "labels": insurer_settlement_labels,
            "values": insurer_settlement_values,
        },
        "policy_mix_chart": {
            "title": "Policy Type Mix",
            "chart_type": "doughnut",
            "labels": policy_mix_labels,
            "values": policy_mix_values,
        },
        "status_mix_chart": {
            "title": "Claim Status Mix",
            "chart_type": "pie",
            "labels": status_mix_labels,
            "values": status_mix_values,
        },
        "avg_premium_chart": {
            "title": "Average Premium by Policy Type",
            "chart_type": "bar",
            "labels": avg_premium_labels,
            "values": avg_premium_values,
        },
        "avg_risk_chart": {
            "title": "Average Risk Score by Insurer",
            "chart_type": "bar",
            "labels": avg_risk_labels,
            "values": avg_risk_values,
        },
    }


def get_visualization_by_key(visual_key: str) -> dict:
    visualizations = get_default_dashboard_visualizations()
    normalized_key = visual_key.strip().lower()

    key_map = {
        "insurer_claim_chart": "insurer_claim_chart",
        "claim_amount_by_insurer": "insurer_claim_chart",
        "insurer_settlement_chart": "insurer_settlement_chart",
        "settlement_days_by_insurer": "insurer_settlement_chart",
        "policy_mix_chart": "policy_mix_chart",
        "policy_type_mix": "policy_mix_chart",
        "status_mix_chart": "status_mix_chart",
        "claim_status_mix": "status_mix_chart",
        "avg_premium_chart": "avg_premium_chart",
        "average_premium_by_policy_type": "avg_premium_chart",
        "avg_risk_chart": "avg_risk_chart",
        "average_risk_score_by_insurer": "avg_risk_chart",
    }

    resolved_key = key_map.get(normalized_key)
    if not resolved_key:
        raise ValueError("Visualization key not recognized.")
    return visualizations[resolved_key]


def get_visualization_catalog() -> list[dict]:
    visuals = get_default_dashboard_visualizations()
    return [
        {
            "key": k,
            "title": visuals[k]["title"],
            "chart_type": visuals[k]["chart_type"],
        }
        for k in visuals
    ]

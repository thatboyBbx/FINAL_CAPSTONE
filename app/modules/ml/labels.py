from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


"""
PHASE 6 LABELS

We support TWO modes:

(6A) DEMO MODE (profile="demo")
  - Uses proxy labels (weak supervision).
  - Labels are derived from engineered financial + news features.
  - Purpose: MVP demo + validate ML lifecycle (train/test/save/load/predict).
  - NOT a real-world ground-truth settlement outcome label.

(6B) APP MODE (profile="app")
  - Uses real labels from a user-provided CSV.
  - Purpose: real supervised training when ground truth is available.
"""


@dataclass
class LabelConfig:
    profile: str
    labels_csv_path: str | None = None  # required for app profile


class LabelProvider:
    def label(self, insurer_id: int, feature_row: dict) -> int:
        raise NotImplementedError


class ProxyLabelProvider(LabelProvider):
    """
    DEMO LABELS (Proxy / Weak Supervision)

    Label meaning:
      0 = low settlement-risk
      1 = moderate settlement-risk
      2 = high settlement-risk

    These are NOT true outcomes — they are rule-derived targets for demo training.
    """

    def label(self, insurer_id: int, feature_row: dict) -> int:
        rai = feature_row["reserve_adequacy_index"]
        cpi = feature_row["claims_pressure_indicator"]
        lss = feature_row["liquidity_stress_score"]
        rdv = feature_row["reserve_depletion_velocity"]
        news_score = feature_row["news_risk_score"]
        reg_events = feature_row["regulatory_event_count"]

        high = 0
        moderate = 0

        # High-risk triggers (domain rules)
        if cpi >= 1.0:
            high += 1
        if rai > 0 and rai < 2.0:
            high += 1
        if lss >= 1.1:
            high += 1
        if rdv < -5000:
            high += 1
        if news_score >= 5.0 or reg_events >= 1:
            high += 1

        # Moderate-risk triggers
        if 0.85 <= cpi < 1.0:
            moderate += 1
        if 2.0 <= rai < 3.0:
            moderate += 1
        if 0.95 <= lss < 1.1:
            moderate += 1
        if -5000 <= rdv < 0:
            moderate += 1
        if 2.0 <= news_score < 5.0:
            moderate += 1

        if high >= 2:
            return 2
        if high == 1 or moderate >= 2:
            return 1
        return 0


class CsvLabelProvider(LabelProvider):
    """
    APP LABELS (Real Supervised Labels)

    Expected CSV format:
      insurer_id,label

    Where label is:
      0 = low settlement-risk
      1 = moderate settlement-risk
      2 = high settlement-risk
    """

    def __init__(self, labels_csv_path: str):
        path = Path(labels_csv_path)
        if not path.exists():
            raise ValueError(
                f"Labels CSV not found at '{labels_csv_path}'. "
                f"Create it with columns: insurer_id,label"
            )

        self.map: dict[int, int] = {}
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise ValueError("Labels CSV missing header row.")
            for row in reader:
                iid = int(row["insurer_id"])
                lab = int(row["label"])
                if lab not in (0, 1, 2):
                    raise ValueError("Labels must be 0,1,2.")
                self.map[iid] = lab

    def label(self, insurer_id: int, feature_row: dict) -> int:
        if insurer_id not in self.map:
            raise ValueError(f"No real label found for insurer_id={insurer_id} in labels CSV.")
        return self.map[insurer_id]


def make_label_provider(cfg: LabelConfig) -> tuple[LabelProvider, str]:
    if cfg.profile == "demo":
        return ProxyLabelProvider(), "proxy_labels"
    if cfg.profile == "app":
        if not cfg.labels_csv_path:
            raise ValueError("App profile requires labels_csv_path.")
        return CsvLabelProvider(cfg.labels_csv_path), "real_labels_csv"
    raise ValueError("profile must be 'demo' or 'app'")

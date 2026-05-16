"""
Train a custom spaCy NER model for insurance document entity extraction.

Dataset
-------
HuggingFace:  autonlp-project/insurance-ner
  BIO-tagged tokens covering insurance-domain entities.

Training parameters
-------------------
  Epochs    : 100
  Batch     : 8 examples
  Dropout   : 0.35
  Eval split: 20% of dataset

Output
------
  Model   : storage/models/app/ner_model/
  Metrics : storage/models/app/ner_model/metrics.json

Usage
-----
  python scripts/train_ner_model.py

    # Optional overrides
    python scripts/train_ner_model.py --epochs 50 --output path/to/model
"""

import argparse
import json
import logging
import random
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = Path("storage/models/app/ner_model")
DEFAULT_EPOCHS     = 100
DEFAULT_BATCH_SIZE = 8
DEFAULT_DROPOUT    = 0.35
EVAL_FRACTION      = 0.20


# ---------------------------------------------------------------------------
# Dataset helpers
# ---------------------------------------------------------------------------

def load_dataset(dataset_name: str) -> dict:
    """
    Load the insurance NER dataset from HuggingFace Hub.

    Returns a dict with keys 'train' (and optionally 'test', 'validation').
    Falls back to a tiny synthetic dataset when the Hub is unavailable so
    the script can still be tested offline.
    """
    try:
        from datasets import load_dataset as hf_load  # noqa: PLC0415
        logger.info("Downloading dataset '%s' from HuggingFace Hub …", dataset_name)
        ds = hf_load(dataset_name, trust_remote_code=True)
        logger.info(
            "Dataset loaded. Splits: %s", {k: len(v) for k, v in ds.items()}
        )
        return ds
    except Exception as exc:
        logger.warning(
            "Could not load dataset from Hub (%s) — using synthetic fallback.",
            exc,
        )
        return _synthetic_fallback_dataset()


def _synthetic_fallback_dataset() -> dict:
    """
    Return a minimal synthetic insurance NER dataset for offline testing.

    Each example mirrors the HuggingFace BIO format:
      tokens : list[str]
      ner_tags: list[int]   (indices into a label list)

    Labels used here match the insurance entity types the service expects.
    """
    # Label list (index → label string)
    LABELS = [
        "O",
        "B-COVERAGE_AMOUNT", "I-COVERAGE_AMOUNT",
        "B-PREMIUM",         "I-PREMIUM",
        "B-DEDUCTIBLE",      "I-DEDUCTIBLE",
        "B-POLICY_PERIOD",   "I-POLICY_PERIOD",
        "B-POLICY_NUMBER",   "I-POLICY_NUMBER",
        "B-INSURER",         "I-INSURER",
        "B-INSURED",         "I-INSURED",
        "B-EXCLUSION",       "I-EXCLUSION",
    ]

    raw_examples = [
        {
            "tokens":   ["The", "coverage", "limit", "is", "$1,000,000", "per", "occurrence"],
            "ner_tags": [0,      0,          0,       0,    1,             2,     2],
        },
        {
            "tokens":   ["Annual", "premium", "of", "$5,000", "is", "due", "by", "January"],
            "ner_tags": [0,        0,         0,    3,        0,    0,     0,    0],
        },
        {
            "tokens":   ["The", "$500", "deductible", "applies", "per", "claim"],
            "ner_tags": [0,     5,      6,             0,         0,     0],
        },
        {
            "tokens":   ["Policy", "No.", "ZW-2024-001", "issued", "by", "RM", "Insurance"],
            "ner_tags": [0,        0,     9,              0,        0,    11,   12],
        },
        {
            "tokens":   ["ABC", "Holdings", "is", "the", "insured", "under", "this", "policy"],
            "ner_tags": [13,    14,          0,    0,     0,         0,       0,      0],
        },
        {
            "tokens":   ["Flood", "damage", "is", "excluded", "from", "coverage"],
            "ner_tags": [15,      16,        0,    0,          0,      0],
        },
        {
            "tokens":   ["Policy", "period", "01/01/2024", "to", "31/12/2024"],
            "ner_tags": [0,        0,         7,            8,    8],
        },
    ]

    # Build a DatasetDict-like structure with train/test split
    examples = raw_examples * 50          # inflate for minimal training signal
    random.shuffle(examples)
    split = int(len(examples) * 0.8)

    class _FakeDataset:
        def __init__(self, rows, label_list):
            self.rows = rows
            self.features = {"ner_tags": _FakeClassLabel(label_list)}
        def __iter__(self): return iter(self.rows)
        def __len__(self): return len(self.rows)

    class _FakeClassLabel:
        def __init__(self, names): self.names = names
        def int2str(self, i): return self.names[i] if i < len(self.names) else "O"

    # HuggingFace-compatible duck-typed dataset
    LABELS_OBJ = _FakeClassLabel(LABELS)

    class _DuckDataset(_FakeDataset):
        pass

    class _FakeDatasetDict(dict):
        pass

    ds = _FakeDatasetDict()
    ds["train"] = _DuckDataset(examples[:split], LABELS)
    ds["test"]  = _DuckDataset(examples[split:], LABELS)
    return ds


# ---------------------------------------------------------------------------
# Format conversion
# ---------------------------------------------------------------------------

def convert_to_spacy_format(
    dataset,
    label_feature,
    max_examples: int | None = None,
) -> list[tuple[str, dict]]:
    """
    Convert a HuggingFace BIO-tagged dataset split to spaCy training format.

    spaCy expects a list of (text, {"entities": [(start, end, label)]}) tuples
    where start/end are character offsets in the text string.

    Parameters
    ----------
    dataset:
        A HuggingFace dataset split (iterable of {tokens, ner_tags}).
    label_feature:
        The ClassLabel feature from dataset.features["ner_tags"], used to
        convert integer tags back to label strings.
    max_examples:
        Optional cap on training examples (useful for quick smoke-tests).

    Returns
    -------
    List of (text, annotations) tuples in spaCy DocBin-compatible format.
    """
    spacy_data: list[tuple[str, dict]] = []
    skipped = 0

    for i, example in enumerate(dataset):
        if max_examples and i >= max_examples:
            break

        tokens   = example["tokens"]
        ner_tags = example["ner_tags"]

        # Convert integer tags to string labels
        labels = [label_feature.int2str(t) for t in ner_tags]

        # Reconstruct the text and compute character offsets
        # (HuggingFace datasets do not always store offsets, so we rebuild them
        #  by joining tokens with a single space — a reasonable approximation)
        text = " ".join(tokens)
        entities: list[tuple[int, int, str]] = []

        char_pos = 0
        current_label: str | None = None
        span_start: int = 0

        for token, label in zip(tokens, labels):
            token_end = char_pos + len(token)

            if label.startswith("B-"):
                # Close any open span
                if current_label:
                    entities.append((span_start, char_pos - 1, current_label))
                current_label = label[2:]   # strip B- prefix
                span_start    = char_pos

            elif label.startswith("I-"):
                # Continuation — keep current span open
                entity_type = label[2:]
                if current_label != entity_type:
                    # Mismatch (I- without matching B-): close current and open new
                    if current_label:
                        entities.append((span_start, char_pos - 1, current_label))
                    current_label = entity_type
                    span_start    = char_pos

            else:  # "O"
                if current_label:
                    entities.append((span_start, char_pos - 1, current_label))
                    current_label = None

            char_pos = token_end + 1   # +1 for the space separator

        # Close any remaining open span
        if current_label:
            entities.append((span_start, char_pos - 1, current_label))

        # Validate: filter out degenerate spans
        valid_entities = [
            (s, e, lbl) for s, e, lbl in entities
            if s < e and s >= 0 and e <= len(text)
        ]

        if len(valid_entities) < len(entities):
            skipped += 1

        spacy_data.append((text, {"entities": valid_entities}))

    if skipped:
        logger.warning(
            "Skipped %d degenerate entity spans during format conversion.", skipped
        )

    return spacy_data


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_insurance_ner(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    n_epochs: int = DEFAULT_EPOCHS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    dropout: float = DEFAULT_DROPOUT,
) -> dict[str, float]:
    """
    Train a custom spaCy NER model on the insurance NER dataset.

    Returns a dict containing precision, recall, and F1 scores on the
    held-out test set.
    """
    import spacy                               # noqa: PLC0415
    from spacy.training import Example         # noqa: PLC0415
    from spacy.util import minibatch, compounding  # noqa: PLC0415

    logger.info("══════════════════════════════════════════════")
    logger.info("  InsureIntel — Insurance NER Model Training  ")
    logger.info("══════════════════════════════════════════════")

    # ── 1. Load dataset ─────────────────────────────────────────────────────
    logger.info("Step 1/5 — Loading insurance NER dataset …")
    dataset = load_dataset("autonlp-project/insurance-ner")

    train_split = dataset["train"]
    test_split  = dataset.get("test") or dataset.get("validation")

    # If no separate test split, carve one out of training data
    if test_split is None:
        logger.info("  No test split found — using %.0f%% of training data for eval.",
                    EVAL_FRACTION * 100)
        all_rows = list(train_split)
        random.shuffle(all_rows)
        split_idx = int(len(all_rows) * (1 - EVAL_FRACTION))
        train_rows = all_rows[:split_idx]
        test_rows  = all_rows[split_idx:]

        # Reconstruct fake dataset objects
        class _RowList:
            def __init__(self, rows, feats): self.rows = rows; self.features = feats
            def __iter__(self): return iter(self.rows)
            def __len__(self): return len(self.rows)

        train_split = _RowList(train_rows, train_split.features)
        test_split  = _RowList(test_rows,  train_split.features)

    label_feature = train_split.features["ner_tags"]

    # ── 2. Convert to spaCy format ──────────────────────────────────────────
    logger.info("Step 2/5 — Converting dataset to spaCy format …")
    train_data = convert_to_spacy_format(train_split, label_feature)
    test_data  = convert_to_spacy_format(test_split,  label_feature)
    logger.info("  Training examples : %d", len(train_data))
    logger.info("  Test examples     : %d", len(test_data))

    # ── 3. Build NER pipeline ───────────────────────────────────────────────
    logger.info("Step 3/5 — Building spaCy NER pipeline …")
    nlp = spacy.blank("en")
    ner = nlp.add_pipe("ner")

    # Register all entity labels found in training data
    labels_seen: set[str] = set()
    for _text, annotations in train_data:
        for _s, _e, lbl in annotations["entities"]:
            labels_seen.add(lbl)
    for lbl in sorted(labels_seen):
        ner.add_label(lbl)
    logger.info("  Entity labels registered: %s", sorted(labels_seen))

    # ── 4. Train ─────────────────────────────────────────────────────────────
    logger.info("Step 4/5 — Training for %d epochs (batch=%d, dropout=%.2f) …",
                n_epochs, batch_size, dropout)

    optimizer = nlp.begin_training()
    best_f1   = 0.0
    t0        = time.perf_counter()

    for epoch in range(1, n_epochs + 1):
        random.shuffle(train_data)
        losses: dict[str, float] = {}

        batches = minibatch(train_data, size=compounding(4.0, batch_size, 1.001))
        for batch in batches:
            examples = []
            for text, annotations in batch:
                doc = nlp.make_doc(text)
                try:
                    example = Example.from_dict(doc, annotations)
                    examples.append(example)
                except Exception:
                    continue   # skip malformed examples silently

            if examples:
                nlp.update(examples, drop=dropout, losses=losses)

        # Log every 10 epochs
        if epoch % 10 == 0 or epoch == n_epochs:
            ner_loss = losses.get("ner", 0.0)
            elapsed  = time.perf_counter() - t0
            logger.info(
                "  Epoch %3d/%d  —  NER loss: %.4f  (elapsed: %.1f s)",
                epoch, n_epochs, ner_loss, elapsed,
            )

    # ── 5. Evaluate ──────────────────────────────────────────────────────────
    logger.info("Step 5/5 — Evaluating on test set …")

    tp: dict[str, int] = {}
    fp: dict[str, int] = {}
    fn: dict[str, int] = {}

    for text, annotations in test_data:
        doc      = nlp(text)
        pred_set = {(e.start_char, e.end_char, e.label_) for e in doc.ents}
        gold_set = {(s, e, lbl) for s, e, lbl in annotations["entities"]}

        for span in pred_set:
            lbl = span[2]
            if span in gold_set:
                tp[lbl] = tp.get(lbl, 0) + 1
            else:
                fp[lbl] = fp.get(lbl, 0) + 1

        for span in gold_set:
            lbl = span[2]
            if span not in pred_set:
                fn[lbl] = fn.get(lbl, 0) + 1

    all_labels = sorted(set(list(tp.keys()) + list(fp.keys()) + list(fn.keys())))
    total_tp = sum(tp.values())
    total_fp = sum(fp.values())
    total_fn = sum(fn.values())

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    recall    = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)

    logger.info("──────────────────────────────────────────")
    logger.info("  Overall metrics:")
    logger.info("    Precision : %.4f", precision)
    logger.info("    Recall    : %.4f", recall)
    logger.info("    F1        : %.4f", f1)
    logger.info("──────────────────────────────────────────")
    logger.info("  Per-label breakdown:")
    for lbl in all_labels:
        ltp  = tp.get(lbl, 0)
        lfp  = fp.get(lbl, 0)
        lfn  = fn.get(lbl, 0)
        lp   = ltp / (ltp + lfp) if (ltp + lfp) > 0 else 0.0
        lr   = ltp / (ltp + lfn) if (ltp + lfn) > 0 else 0.0
        lf1  = 2 * lp * lr / (lp + lr) if (lp + lr) > 0 else 0.0
        logger.info("    %-25s  P=%.3f  R=%.3f  F1=%.3f", lbl, lp, lr, lf1)
    logger.info("──────────────────────────────────────────")

    # ── Save model ────────────────────────────────────────────────────────────
    output_dir.mkdir(parents=True, exist_ok=True)
    nlp.to_disk(str(output_dir))
    logger.info("Model saved to:  %s", output_dir)

    # ── Save metrics (required for dissertation reporting) ───────────────────
    metrics = {
        "precision":  round(precision, 6),
        "recall":     round(recall,    6),
        "f1":         round(f1,        6),
        "epochs":     n_epochs,
        "batch_size": batch_size,
        "dropout":    dropout,
        "train_size": len(train_data),
        "test_size":  len(test_data),
        "labels":     all_labels,
        "per_label":  {
            lbl: {
                "precision": round(tp.get(lbl,0) / (tp.get(lbl,0) + fp.get(lbl,0)), 4)
                             if (tp.get(lbl,0) + fp.get(lbl,0)) > 0 else 0.0,
                "recall":    round(tp.get(lbl,0) / (tp.get(lbl,0) + fn.get(lbl,0)), 4)
                             if (tp.get(lbl,0) + fn.get(lbl,0)) > 0 else 0.0,
                "f1":        round(
                    2 * (tp.get(lbl,0) / max(tp.get(lbl,0)+fp.get(lbl,0),1))
                      * (tp.get(lbl,0) / max(tp.get(lbl,0)+fn.get(lbl,0),1))
                    / max(
                        (tp.get(lbl,0) / max(tp.get(lbl,0)+fp.get(lbl,0),1))
                      + (tp.get(lbl,0) / max(tp.get(lbl,0)+fn.get(lbl,0),1)),
                        1e-10,
                    ), 4,
                ),
            }
            for lbl in all_labels
        },
    }

    metrics_path = output_dir / "metrics.json"
    with metrics_path.open("w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)
    logger.info("Metrics saved to: %s", metrics_path)

    return metrics


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Train the InsureIntel insurance NER model."
    )
    p.add_argument(
        "--epochs", type=int, default=DEFAULT_EPOCHS,
        help=f"Training epochs (default: {DEFAULT_EPOCHS})",
    )
    p.add_argument(
        "--batch", type=int, default=DEFAULT_BATCH_SIZE,
        help=f"Mini-batch size (default: {DEFAULT_BATCH_SIZE})",
    )
    p.add_argument(
        "--dropout", type=float, default=DEFAULT_DROPOUT,
        help=f"Dropout rate (default: {DEFAULT_DROPOUT})",
    )
    p.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT_DIR,
        help=f"Model output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    metrics = train_insurance_ner(
        output_dir=args.output,
        n_epochs=args.epochs,
        batch_size=args.batch,
        dropout=args.dropout,
    )

    print("\n" + "═" * 50)
    print("  TRAINING COMPLETE")
    print("═" * 50)
    print(f"  F1 Score  : {metrics['f1']:.4f}")
    print(f"  Precision : {metrics['precision']:.4f}")
    print(f"  Recall    : {metrics['recall']:.4f}")
    print(f"  Model     : {args.output}")
    print(f"  Metrics   : {args.output}/metrics.json")
    print("═" * 50)

    # Non-zero exit code when F1 is below the 0.80 dissertation target
    if metrics["f1"] < 0.80:
        logger.warning(
            "F1 score %.4f is below the 0.80 dissertation target. "
            "Consider more training data or additional epochs.",
            metrics["f1"],
        )
        sys.exit(1)

    sys.exit(0)

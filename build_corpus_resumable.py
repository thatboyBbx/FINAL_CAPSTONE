from __future__ import annotations
import json, logging, sys
from pathlib import Path

BASE_DIR     = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger       = logging.getLogger("corpus_builder")
SOURCES_DIR  = BASE_DIR / "sources"
DATASETS_DIR = BASE_DIR / "storage" / "datasets" / "app"
CORPUS_PATH  = DATASETS_DIR / "circulars_corpus.json"
STATE_PATH   = DATASETS_DIR / "corpus_state.json"
BATCH_SIZE   = 20
MAX_PAGES    = 5
DATASETS_DIR.mkdir(parents=True, exist_ok=True)

def extract_text_fast(fp):
    try:
        import pdfplumber
        pages = []
        with pdfplumber.open(fp) as pdf:
            for pg in pdf.pages[:MAX_PAGES]:
                t = pg.extract_text()
                if t: pages.append(t)
        if pages: return "\n".join(pages)
    except Exception:
        pass
    from app.modules.documents.ingestion.pdf_extractor import extract_text_from_pdf
    return extract_text_from_pdf(fp)

def collect_all_files():
    srcs = [
        (SOURCES_DIR / "downloads" / "insurance_circulars", "circulars"),
        (SOURCES_DIR / "reports",                            "reports"),
        (SOURCES_DIR / "insurancedocuments",                 "insurance_forms"),
        (SOURCES_DIR / "insurancepolicydocuments (1)",       "policy_documents"),
    ]
    out = []
    for d, lbl in srcs:
        if not d.exists(): continue
        for ext in (".pdf", ".xlsx", ".xls"):
            for f in sorted(d.rglob("*" + ext)):
                out.append((f, lbl))
    return out

def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"processed_paths": [], "total_files": 0}

def save_state(s):
    STATE_PATH.write_text(json.dumps(s, indent=2), encoding="utf-8")

def load_corpus():
    if CORPUS_PATH.exists():
        return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    return []

def save_corpus(c):
    CORPUS_PATH.write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")

def main():
    from app.modules.documents.ingestion.feature_extractor import extract_features
    all_files     = collect_all_files()
    state         = load_state()
    corpus        = load_corpus()
    done_set      = set(state["processed_paths"])
    remaining     = [(f, l) for f, l in all_files if str(f) not in done_set]
    total         = len(all_files)
    logger.info("Total: %d  Done: %d  Remaining: %d", total, len(done_set), len(remaining))
    if not remaining:
        cats = {}
        for r in corpus:
            c = r.get("category","unknown"); cats[c] = cats.get(c,0)+1
        extr = sum(1 for r in corpus if r.get("extractable"))
        logger.info("COMPLETE. Corpus=%d  Extractable=%d  Cats=%s", len(corpus), extr, cats)
        return
    batch = remaining[:BATCH_SIZE]
    logger.info("Batch: %d files (max_pages=%d)", len(batch), MAX_PAGES)
    new_recs = []
    for i, (fp, lbl) in enumerate(batch, 1):
        try:
            text = extract_text_fast(fp)
            rec  = extract_features(file_path=fp, text=text, source_label=lbl)
            new_recs.append(rec)
            done_set.add(str(fp))
            if i % 10 == 0 or i == len(batch):
                logger.info("  [%d/%d] %s", i, len(batch), fp.name)
        except Exception as e:
            logger.warning("  SKIP %s: %s", fp.name, e)
            done_set.add(str(fp))
    corpus.extend(new_recs)
    save_corpus(corpus)
    state["processed_paths"] = list(done_set)
    state["total_files"]     = total
    save_state(state)
    left = total - len(done_set)
    pct  = int(len(done_set)/total*100) if total else 0
    logger.info("Done batch. Added=%d  Corpus=%d  Progress=%d/%d(%d%%)  Left=%d",
                len(new_recs), len(corpus), len(done_set), total, pct, left)
    if left:
        logger.info("Run again to continue (%d left).", left)
    else:
        cats2 = {}
        for r in corpus:
            c = r.get("category","unknown"); cats2[c] = cats2.get(c,0)+1
        logger.info("=== BUILD COMPLETE === Corpus=%d Cats=%s", len(corpus), cats2)

if __name__ == "__main__":
    main()

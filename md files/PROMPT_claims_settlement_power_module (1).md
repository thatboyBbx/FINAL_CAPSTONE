# Claude Code Implementation Prompt
## Module: Claims Settlement Power (CSP) — Insurer Financial Intelligence

> **Replaces:** The ZSE (Zimbabwe Stock Exchange) module — **remove entirely**: all ZSE scraper
> code, database tables, API routes, and UI templates. Delete every file and reference.
>
> **Location in platform:** Analytics section (new sub-tab: "Settlement Power")
>
> **Report integration:** CSP scores and natural language assessments are injected into every
> document analysis report where an INSURER entity is detected by the NER pipeline.

---

## WHY THIS MODULE EXISTS — THE PLAIN ENGLISH PROBLEM

When a broker recommends a policy to a client, the most important question is not just
*"does this policy cover what we need?"* — it is *"if a claim is made tomorrow, can this
insurer actually pay?"*

That question has three concrete parts:

1. **Does the insurer have enough total assets to cover its total liabilities?** — Solvency
2. **Does the insurer have liquid money available right now**, not locked in buildings or
   long-term bond portfolios? — Liquidity and Claims Settlement Capacity
3. **Has the insurer set aside enough money for claims it already knows about but has not
   paid yet?** — Claims Reserves (IBNR + outstanding claims)

No existing tool in Zimbabwe answers all three simultaneously for a broker, in plain English,
linked to the specific insurer named in the document they are reviewing. This module builds
that capability.

---

## THE MODEL — WHICH MODEL AND WHY (FULL EXPLANATION)

### Primary Scoring: Weighted Composite Score (WCS)

The core scoring model is a **Weighted Composite Score (WCS)** — a calibrated linear
combination of four normalized financial indicators, each scaled to 0–100.

**Why WCS and not a neural network or deep learning model?**

Zimbabwe has approximately 20–25 active insurers at any time. IPEC publishes quarterly
FSR-1 returns, giving at most 100 data rows per year across all insurers. A neural network
or random forest trained on this volume will overfit immediately and produce results that
cannot be interrogated or defended — to a dissertation examiner or a broker asking "why
does this score say 67?" A WCS is:

- **Interpretable** — every point in the score traces directly to a formula
- **Auditable** — quarter-on-quarter changes can be attributed to a specific metric
- **Regulatory grounded** — the normalization anchors (e.g. IPEC minimum solvency 150%)
  come directly from Zimbabwe's Insurance Act Chapter 24:07 and IPEC supervisory directives
- **Academically defensible** — weights are derived via ablation study on IPEC's historical
  distressed insurer register, not assigned by intuition

**The four indicators and their weights:**

| Indicator | Weight | Justification |
|---|---|---|
| Solvency Ratio | 35% | IPEC's primary regulatory threshold. Most predictive of structural insolvency in the IPEC distressed register |
| Claims Settlement Capacity | 30% | Directly answers the broker's question — liquid assets available to settle claims now. Liquidity failure is the proximate cause of most claims disputes |
| Claims Reserves Adequacy | 20% | IBNR + outstanding reserve ratio. A leading warning signal — thin reserves precede future solvency deterioration |
| General Liquidity Ratio | 15% | Current ratio (current assets / current liabilities). Supports settlement capacity but is less insurance-specific |

These weights must be validated and documented via ablation study. See the dissertation
methodology section at the bottom of this file.

### Secondary Layer: XGBoost Anomaly Classifier

Alongside the WCS, train an **XGBoost binary classifier** that predicts whether an insurer
is *"at risk of claims settlement failure"* based on the same four indicators plus
year-on-year change rates.

**Why XGBoost specifically?**

- The training dataset is **small and class-imbalanced** — distressed insurers are rare.
  XGBoost's gradient boosting focuses on the minority class through iterative reweighting,
  outperforming logistic regression and plain decision trees in this scenario
- XGBoost supports **SHAP (SHapley Additive exPlanations) natively**. Every prediction
  comes with a breakdown of exactly which financial metric contributed most to the score.
  This is mandatory for the dissertation's explainability requirement and for broker-facing
  output — the model cannot be a black box
- It generalises better than a single decision tree through ensembling but remains
  far more tractable than a neural network on a 25-insurer dataset
- It is **deterministic given a fixed seed** — reproducibility is a dissertation commitment

**Training data:** IPEC's published list of insurers placed under curatorship, licence
revocation, or flagged in annual supervision reports = ground truth label `is_distressed = 1`.
Supplement with synthetic perturbation of FSR-1 data (add Gaussian noise to financial
figures of healthy insurers to simulate near-distress states) to expand training volume.

### Output: Natural Language Generation (NLG)

The numerical CSP score is always accompanied by a **structured plain English summary**
generated by a rule-based template engine — not the Claude API. This works offline and
is deterministic: the same inputs always produce the same output.

Example output:

> *"Claims Settlement Power: 71/100 — Adequate. This insurer's solvency ratio of 187%
> exceeds IPEC's mandatory minimum of 150%, and liquid assets cover approximately 2.3
> months of projected claims. However, IBNR reserves have declined 12% year-on-year,
> which warrants monitoring. Overall: capital adequacy is sound for standard claims
> volumes."*

**Forbidden words in all NLG output:** "risky," "dangerous," "failing," "avoid," "do not
use," "insolvent" (unless solvency ratio is below 100% — factual statement only).

**Permitted advisory framing:** "warrants monitoring," "enhanced due diligence recommended,"
"within regulatory parameters," "capital adequacy indicators are below benchmark,"
"escalate to senior broker."

---

## DATA SOURCES

### Primary: IPEC FSR-1 Quarterly Returns

URL: `https://www.ipec.co.zw/download-centre/`

The FSR-1 (Financial Soundness Return) is a mandatory quarterly filing by all IPEC-licensed
insurers, published as PDFs on the IPEC website. It contains:
- Total assets and liabilities
- Solvency margin and ratio
- Gross premiums written and claims paid
- Outstanding claims reserves
- IBNR provisions
- Reinsurance cessions

**Scraping strategy:** Fetch the IPEC download centre page, extract all PDF links matching
`FSR` or `Financial Soundness` or `Quarterly Return` in the link text or filename. Download
each PDF. Use `pdfplumber` for text-PDF extraction. For scanned PDFs, fall back to the
platform's existing Tesseract OCR pipeline.

### Secondary: Audited Annual Financial Statements

- **AfricanFinancials** (`africanfinancials.com`) — annual reports for Zimbabwean insurers
- **Insurer websites** — most IPEC-licensed insurers publish annual reports; build a
  configurable per-insurer URL map in `settings.py`

### What is NOT used

- ZSE share price data — removed entirely
- News sentiment — flows through the separate news intelligence module only
- Any data requiring a paid API subscription

---

## FILE STRUCTURE

```
app/
├── scrapers/
│   ├── ipec_fsr1_scraper.py           # Scrapes IPEC download centre, downloads FSR-1 PDFs
│   ├── ipec_pdf_parser.py             # Extracts tables from FSR-1 PDFs
│   └── insurer_financials_scraper.py  # AfricanFinancials + insurer website annual reports
│
├── models/
│   ├── insurer.py                     # Insurer master table
│   ├── insurer_financials.py          # Quarterly + annual financial data per insurer
│   └── csp_score.py                   # Computed CSP scores
│
├── schemas/
│   └── csp_schema.py                  # Pydantic v2 schemas
│
├── ml/
│   ├── csp_wcs_scorer.py              # Weighted Composite Score calculator
│   ├── csp_xgboost_model.py           # XGBoost classifier + SHAP
│   ├── csp_normalizer.py              # Maps raw financial figures to 0-100 scale
│   ├── csp_nlg.py                     # Rule-based natural language generator
│   └── csp_training_pipeline.py       # Training script for XGBoost
│
├── services/
│   └── csp_service.py                 # Orchestrates scoring, lookup, report injection
│
├── api/
│   └── routes/
│       └── csp_routes.py              # Analytics sub-tab routes + broker lookup endpoint
│
├── tasks/
│   └── csp_refresh_task.py            # APScheduler: quarterly data refresh + rescore
│
└── templates/
    ├── analytics/
    │   └── settlement_power.html       # Main CSP analytics sub-tab
    └── partials/
        └── csp_report_card.html        # Injected into document analysis reports
```

**Delete entirely (ZSE removal):**
```
app/scrapers/zse_scraper.py            (if exists)
app/models/zse_data.py                 (if exists)
app/api/routes/zse_routes.py           (if exists)
app/templates/analytics/zse.html       (if exists)
```
Remove all ZSE references from analytics navigation, route registrations, and any dashboard
template that rendered ZSE data.

---

## DATABASE MODELS

### `insurer` table (`app/models/insurer.py`)

Use SQLAlchemy 2.0 `Mapped[]` / `mapped_column()` exclusively.

```
id:                      UUID primary key
name:                    str  (full legal name, e.g. "Old Mutual Zimbabwe Limited")
short_name:              str  (display name, e.g. "Old Mutual")
ipec_licence_number:     str | None  (indexed)
insurer_type:            str  (enum: "life", "short_term", "reinsurer", "composite")
is_active:               bool
website_url:             str | None
africanfinancials_slug:  str | None
created_at:              datetime
updated_at:              datetime
```

### `insurer_financials` table (`app/models/insurer_financials.py`)

```
id:                          UUID primary key
insurer_id:                  UUID FK → insurer.id

--- Period ---
period_type:                 str  (enum: "quarterly", "annual")
period_year:                 int
period_quarter:              int | None  (1–4, NULL for annual)

--- Solvency ---
total_assets_usd:            Decimal
total_liabilities_usd:       Decimal
solvency_margin_usd:         Decimal
solvency_ratio_pct:          Decimal  (e.g. 187.5)
ipec_minimum_solvency_pct:   Decimal  (default 150.0)

--- Claims ---
gross_claims_paid_usd:       Decimal
outstanding_claims_reserve:  Decimal
ibnr_reserve_usd:            Decimal
total_claims_reserves_usd:   Decimal  (outstanding + IBNR)
claims_ratio_pct:            Decimal

--- Liquidity ---
current_assets_usd:          Decimal
current_liabilities_usd:     Decimal
liquidity_ratio:             Decimal
liquid_assets_usd:           Decimal  (cash + short-term instruments only)

--- Premiums ---
gross_premiums_written_usd:  Decimal
net_premiums_earned_usd:     Decimal

--- Metadata ---
data_source:                 str  (e.g. "IPEC FSR-1 Q3 2024")
source_url:                  str | None
extraction_confidence:       float  (1.0 = clean PDF table, 0.7 = OCR)
created_at:                  datetime
```

### `csp_score` table (`app/models/csp_score.py`)

```
id:                          UUID primary key
insurer_id:                  UUID FK → insurer.id
financials_id:               UUID FK → insurer_financials.id

--- WCS Components (all 0–100) ---
solvency_score:              float
settlement_capacity_score:   float
reserves_adequacy_score:     float
liquidity_score:             float
wcs_score:                   float  (weighted composite)
wcs_band:                    str  (enum: "Strong","Adequate","Marginal","Weak","Critical")

--- XGBoost Layer ---
xgb_at_risk_probability:     float  (0.0–1.0)
xgb_at_risk_flag:            bool
shap_values_json:            JSONB  (feature → contribution mapping)

--- NLG ---
natural_language_summary:    str
broker_recommendation:       str

--- Metadata ---
scored_at:                   datetime
model_version:               str  (e.g. "wcs_v1.0_xgb_v1.0")
```

---

## IMPLEMENTATION INSTRUCTIONS

### Step 1 — IPEC Scraper + PDF Parser

**`IPECFinancialScraper` (`app/scrapers/ipec_fsr1_scraper.py`):**

- `def scrape_download_centre(self) -> list[str]` — fetches the IPEC download centre page
  and returns all PDF URLs whose link text or filename contains "FSR", "Financial Soundness",
  or "Quarterly Return"
- `def download_pdf(self, url: str, dest_dir: str) -> str` — downloads to local temp
  directory, returns local path
- `def is_already_processed(self, source_url: str) -> bool` — checks `insurer_financials`
  for existing row with matching `source_url` to prevent re-processing

**`IPECPDFParser` (`app/scrapers/ipec_pdf_parser.py`):**

- `def extract_tables(self, pdf_path: str) -> list[dict]` — uses `pdfplumber` to extract all
  tables. If a page returns text below 0.5 confidence (or no text), falls back to Tesseract
  OCR via the platform's existing OCR pipeline. Returns a list of row dicts per insurer
- `def parse_insurer_row(self, row: dict) -> InsurerFinancialsCreate | None` — maps raw
  column names to the schema. Build a `COLUMN_ALIAS_MAP` dict to handle FSR-1 format
  variations across IPEC's different reporting periods (column names have changed at least
  twice since 2020)
- `def infer_period(self, filename: str) -> tuple[int, int | None]` — parses year and
  quarter from filename patterns like `FSR1_Q3_2024.pdf` or `Annual_Returns_2023.pdf`

### Step 2 — Normalizer (`app/ml/csp_normalizer.py`)

Implement piecewise linear scaling for each indicator anchored to IPEC benchmarks.
Use linear interpolation between anchor points:

```
Solvency Score (anchors):
  solvency_ratio_pct < 100   → score = 0
  solvency_ratio_pct = 150   → score = 50   (IPEC minimum)
  solvency_ratio_pct = 200   → score = 75
  solvency_ratio_pct >= 250  → score = 100

Settlement Capacity Score:
  Derived metric: liquid_assets_usd / (gross_claims_paid_usd / 12) = months_coverage
  months_coverage < 1   → score = 0
  months_coverage = 2   → score = 50
  months_coverage = 4   → score = 75
  months_coverage >= 6  → score = 100

Reserves Adequacy Score:
  Derived metric: total_claims_reserves_usd / gross_claims_paid_usd = reserves_ratio
  reserves_ratio < 0.5  → score = 0
  reserves_ratio = 1.0  → score = 50
  reserves_ratio = 1.5  → score = 75
  reserves_ratio >= 2.0 → score = 100

Liquidity Score:
  liquidity_ratio = current_assets / current_liabilities
  liquidity_ratio < 1.0  → score = 0
  liquidity_ratio = 1.2  → score = 50
  liquidity_ratio = 1.5  → score = 75
  liquidity_ratio >= 2.0 → score = 100
```

Implement `def interpolate(value: float, anchors: list[tuple[float, float]]) -> float` as
a general piecewise linear interpolator, then call it for each indicator.

### Step 3 — WCS Scorer (`app/ml/csp_wcs_scorer.py`)

```python
WCS_WEIGHTS = {
    "solvency":    0.35,
    "settlement":  0.30,
    "reserves":    0.20,
    "liquidity":   0.15,
}

WCS_BANDS = [
    (85, 100, "Strong"),
    (65, 84,  "Adequate"),
    (45, 64,  "Marginal"),
    (25, 44,  "Weak"),
    (0,  24,  "Critical"),
]
```

Implement `def score(self, financials: InsurerFinancialsRead) -> CSPComponentScores` that:
1. Calls the normalizer for all four indicators
2. Computes the weighted composite
3. Assigns the band
4. Returns a `CSPComponentScores` Pydantic model with all four component scores, the
   composite score, and the band

Implement `def explain_components(self, scores: CSPComponentScores) -> list[str]` that
returns one plain English sentence per component. Example sentences:

```
Solvency (strong):    "Solvency ratio of {pct}% provides a {buffer}% buffer above IPEC's mandatory minimum."
Solvency (marginal):  "Solvency ratio of {pct}% is close to IPEC's mandatory minimum of 150% — warrants monitoring."
Solvency (critical):  "Solvency ratio of {pct}% is below IPEC's mandatory minimum of 150%."
Settlement (strong):  "Liquid assets cover approximately {months} months of projected claims."
Settlement (weak):    "Liquid assets cover less than one month of projected claims — settlement capacity is limited."
Reserves (strong):    "Claims reserves are {ratio}x annual paid claims — adequately provisioned."
Reserves (weak):      "Claims reserves represent {ratio}x annual paid claims — below industry benchmark of 1.0x."
Liquidity (strong):   "Current ratio of {ratio} indicates comfortable short-term financial flexibility."
Liquidity (critical): "Current liabilities exceed current assets — immediate liquidity pressure present."
```

### Step 4 — XGBoost Model (`app/ml/csp_xgboost_model.py`)

Feature set for training and inference:

```python
FEATURES = [
    "solvency_ratio_pct",
    "settlement_capacity_months",      # liquid_assets / (claims_paid / 12)
    "reserves_to_paid_ratio",          # total_reserves / claims_paid
    "liquidity_ratio",
    "claims_ratio_pct",
    "solvency_ratio_yoy_change",       # % change vs same quarter prior year
    "claims_reserves_yoy_change",
    "premiums_yoy_change",
]
```

Implement:
- `def train(self, X: pd.DataFrame, y: pd.Series) -> None` — use `xgb.XGBClassifier` with
  `scale_pos_weight = (n_negative / n_positive)` to handle class imbalance. Set `random_state=42`
  for reproducibility. Save to `app/ml/models/csp_xgboost.joblib` via `joblib.dump`
- `def load(self) -> None` — loads saved model on service startup. If file not found, logs a
  warning and sets `self.model = None` (WCS-only fallback)
- `def predict_risk(self, features: dict[str, float]) -> tuple[float, bool]` — returns
  `(probability, flag)`. Flag is True if probability > 0.5
- `def get_shap_explanation(self, features: dict[str, float]) -> dict[str, float]` — computes
  SHAP values using `shap.TreeExplainer`. Returns feature → contribution dict
- `def shap_to_sentence(self, shap_dict: dict[str, float]) -> str` — converts the SHAP dict
  to a plain English sentence. Find the feature with the highest absolute SHAP value and
  describe it. Examples:
  - `solvency_ratio_yoy_change` negative → "Primary signal: solvency ratio has declined {pct}% over the past year."
  - `settlement_capacity_months` dominant negative → "Primary signal: liquid asset coverage of claims has deteriorated."
  - If all SHAP values are small (< 0.1) → "No single dominant risk signal identified — risk is diffuse across multiple indicators."

### Step 5 — NLG (`app/ml/csp_nlg.py`)

Implement `CSPNaturalLanguageGenerator` class. Pure rule-based templates. No API calls.

Structure:
- Opening sentence — selected by WCS band
- Component sentences — from `WCSScorer.explain_components()`, include only components
  scoring below 60 (problems) and above 80 (strengths); skip middle-range components to
  keep summaries concise
- SHAP sentence — from `XGBoostModel.shap_to_sentence()` (only if XGBoost model is loaded)
- Closing advisory — selected by this logic:
  - WCS >= 75 and not at-risk: "No enhanced due diligence required at this time."
  - WCS 50–74 or at-risk probability 0.3–0.5: "Recommend monitoring quarterly IPEC filings for this insurer."
  - WCS 25–49 or at-risk probability > 0.5: "Enhanced due diligence recommended before policy placement."
  - WCS < 25: "Escalate to senior broker — capital adequacy indicators are below IPEC regulatory threshold."

Implement `def generate(self, scores: CSPComponentScores, xgb_result: XGBResult | None) -> tuple[str, str]`
that returns `(natural_language_summary, broker_recommendation)`.

### Step 6 — CSP Service (`app/services/csp_service.py`)

Implement `CSPService`:

- `def get_csp_for_insurer(self, insurer_name: str) -> CSPScoreRead | None` — fuzzy match
  insurer name using `rapidfuzz.fuzz.token_sort_ratio`. Threshold: 75. Returns most recent
  CSP score for the matched insurer
- `def get_all_csp_scores(self) -> list[CSPScoreRead]` — all insurers' latest scores, used
  for charts
- `def score_insurer(self, insurer_id: str) -> CSPScoreRead` — fetches latest financials for
  insurer, runs WCS + XGBoost, calls NLG, saves to `csp_score` table, returns result
- `def refresh_all_scores(self) -> int` — calls `score_insurer` for every active insurer
  with financial data, returns count updated
- `def inject_csp_into_report(self, report_id: str, insurer_name: str) -> bool` — looks up
  CSP, writes a `report_csp_injection` row linking report to CSP score. Returns False if
  no CSP data found (do not fail the report — render the "not available" notice instead)

### Step 7 — API Routes (`app/api/routes/csp_routes.py`)

```
GET  /analytics/settlement-power/
     → Renders settlement_power.html with all insurer CSP scores in context

GET  /analytics/settlement-power/lookup?insurer=<name>
     → Returns CSPScoreRead JSON for matched insurer
     → Used by broker search box (vanilla JS fetch)
     → Returns 404 with {"detail": "No CSP data found for this insurer"} if not matched

GET  /analytics/settlement-power/chart-data
     → Returns JSON: { labels, solvency, settlement, reserves, liquidity, wcs, bands }
     → All arrays same length, one entry per active insurer with data
     → Used by Chart.js for all three chart types

POST /internal/csp/force-refresh
     → ADMIN role required
     → Triggers full scrape + rescore pipeline as background task
     → Returns { "job_id": "...", "status": "started" }
```

### Step 8 — Analytics UI Template (`app/templates/analytics/settlement_power.html`)

**Jinja2 + vanilla JS + Chart.js via CDN. No React. No framework.**

Load Chart.js:
```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
```

**Section 1: Broker Lookup**

A search input: *"Search insurer by name..."*

Vanilla JS: debounced `fetch` call (300ms) to `/analytics/settlement-power/lookup?insurer=<value>`.
On successful response, render a result card below the input containing:
- Insurer full name + IPEC licence number
- WCS score as a large number with band label (colour coded: Strong=green, Adequate=teal,
  Marginal=yellow, Weak=amber, Critical=red — use existing design system CSS variables)
- Four component scores as a mini horizontal bar breakdown (inline `<div>` width set via
  inline style: `width: {score}%`)
- Natural language summary paragraph
- Broker recommendation note in a highlighted box
- Data period label: *"Based on {data_source}"*
- If XGBoost at-risk flag: amber notice block: *"Enhanced Due Diligence Recommended"* +
  SHAP natural language sentence
- Link: *"View full profile in analytics →"*

On 404 response: display: *"No Settlement Power data found for this insurer. Verify name
or check IPEC FSR-1 filings manually."*

Include a small disclaimer below the card:
*"Settlement Power assessments are internal broker work product for advisory purposes only.
This is not a credit rating or regulatory opinion."*

**Section 2: Market Overview — Three Charted Views**

Three tabs (vanilla JS click handler toggles `display: none/block`):

**Tab 1 — Radar Chart: Multi-Insurer Comparison**
- Default: show 4 insurers (top WCS, bottom WCS, and 2 mid-range)
- User can add/remove insurers via checkboxes rendered from the Jinja2 context list
- 4 radar axes: Solvency, Settlement Capacity, Reserves Adequacy, Liquidity
- Chart.js `radar` type
- Tooltips show exact score + label

**Tab 2 — Bubble Chart: Settlement Capacity vs Solvency**
- X-axis: Solvency Score (0–100)
- Y-axis: Settlement Capacity Score (0–100)
- Bubble radius: proportional to WCS composite score
- Bubble background colour: band colour
- Label each bubble with `short_name`
- Chart.js `bubble` type

**Tab 3 — Horizontal Bar: WCS Rankings**
- All active insurers with data, ranked highest WCS to lowest
- Bar colour = band colour
- Clicking a bar triggers the lookup card in Section 1 (JS: call the lookup endpoint
  with the insurer name from the chart label)
- Chart.js `bar` type with `indexAxis: 'y'`

Respond to `html.dark` class toggle: use `getComputedStyle(document.documentElement)`
to read CSS variable values for chart colours, so charts automatically re-theme.

**Do not add a top-level navigation link for this page.** It lives under the existing
Analytics section as a sub-tab only.

### Step 9 — Report Card Partial (`app/templates/partials/csp_report_card.html`)

Compact Jinja2 partial, injected into every document analysis report where `INSURER`
entity is detected.

```
If CSP data exists:
  - Insurer name (from NER)
  - WCS score badge (coloured by band)
  - Natural language summary (one sentence)
  - Three key metrics in small text: Solvency {pct}% | Settlement {months} months | Reserves {ratio}x
  - Link: "View full Settlement Power profile →" → /analytics/settlement-power/lookup?insurer=<name>

If no CSP data:
  - Neutral grey notice: "Settlement Power data not yet available for this insurer.
    Verify directly via IPEC FSR-1 quarterly returns."
```

### Step 10 — Quarterly Refresh Task (`app/tasks/csp_refresh_task.py`)

```python
# APScheduler: 15th of January, April, July, October at 06:00 Harare time
# FSR-1 returns are typically published 6–8 weeks after quarter end
scheduler.add_job(
    func=run_csp_refresh,
    trigger=CronTrigger(
        month="1,4,7,10",
        day=15,
        hour=6,
        minute=0,
        timezone=pytz.timezone("Africa/Harare")
    ),
    id="quarterly_csp_refresh",
    replace_existing=True,
    misfire_grace_time=86400   # run within 24hrs if server was down at trigger time
)
```

`run_csp_refresh()` must:
1. Run `IPECFinancialScraper.scrape_download_centre()` and process all new PDFs
2. Run `InsurerFinancialsScraper` for AfricanFinancials annual reports
3. Call `CSPService.refresh_all_scores()`
4. Log to `csp_refresh_log` table: `run_id`, `started_at`, `completed_at`,
   `insurers_updated`, `new_financials_rows`, `errors_json`

---

## DISSERTATION METHODOLOGY NOTE

Place as module-level docstring in `app/ml/csp_wcs_scorer.py`:

```
Methodology Note (Chapter 3 — Model Design):

The Claims Settlement Power (CSP) model uses a Weighted Composite Score (WCS) as
its primary mechanism, supplemented by an XGBoost binary classifier for anomaly
detection.

WCS was selected over black-box alternatives for three reasons: (1) data volume
constraints — Zimbabwe's ~25 active insurers produce insufficient observations for
deep learning generalisation (Goodfellow et al., 2016); (2) interpretability
requirements — broker-facing advisory output must be fully explainable per
regulatory advisory standards; (3) regulatory grounding — normalization anchors
are derived directly from Zimbabwe's Insurance Act Chapter 24:07 and IPEC
supervisory directives, giving the model's thresholds formal regulatory validity.

Weight derivation: The 35/30/20/15 allocation across solvency, settlement capacity,
reserves adequacy, and liquidity was calibrated via leave-one-out ablation on IPEC's
historical distressed insurer register (insurers under curatorship 2015–2024). The
weight combination minimising mean absolute prediction error on known distress events
was selected as the production configuration, consistent with the ablation study
methodology described in Chapter 4.

XGBoost was selected for the anomaly layer because gradient boosting handles class
imbalance through iterative sample reweighting (Chen & Guestrin, 2016), and its
native SHAP integration (Lundberg & Lee, 2017) enables per-prediction feature
attribution, directly supporting the platform's explainability requirements.

All normalization anchors are grounded in regulatory thresholds where available
(IPEC minimum solvency 150%) and actuarial practice standards where regulatory
benchmarks are absent (e.g. 2-month liquid asset coverage adapted from Lloyd's
minimum liquidity requirements for the Zimbabwean context).
```

---

## TESTING SCRIPT (`tests/test_csp_module.py`)

1. `test_wcs_strong_insurer` — solvency 220%, settlement 4.5 months, reserves 1.8x,
   liquidity 1.9 → WCS >= 65, band "Adequate" or "Strong"
2. `test_wcs_critical_insurer` — solvency 105%, settlement 0.5 months, reserves 0.3x,
   liquidity 0.8 → WCS < 25, band "Critical"
3. `test_normalizer_solvency_at_minimum` — solvency_ratio_pct = 150.0 → solvency_score = 50.0
4. `test_normalizer_solvency_breach` — solvency_ratio_pct = 90.0 → solvency_score = 0.0
5. `test_normalizer_interpolation` — solvency_ratio_pct = 175.0 → score between 50 and 75
6. `test_nlg_no_forbidden_words` — any valid CSP input → summary contains none of:
   "risky", "dangerous", "failing", "avoid", "do not use"
7. `test_nlg_critical_closes_with_escalation` — WCS < 25 → broker_recommendation contains
   "Escalate"
8. `test_fuzzy_lookup_matches_variant` — query "Old Mutual" → matches "Old Mutual Zimbabwe
   Limited" with confidence >= 75
9. `test_chart_data_arrays_equal_length` — GET /analytics/settlement-power/chart-data →
   all arrays in response JSON have identical length
10. `test_csp_injected_into_report` — mock report with INSURER entity "CBZ Insurance" →
    `csp_report_card` partial renders in report HTML, WCS score visible
11. `test_no_csp_renders_graceful_notice` — INSURER entity with no matching insurer in DB →
    report renders "not yet available" notice, does not raise exception
12. `test_ipec_column_alias_map` — feed mock FSR-1 table with variant column headers →
    parser maps correctly to `insurer_financials` schema fields
13. `test_shap_sentence_dominant_feature` — SHAP dict with `solvency_ratio_yoy_change = -0.8`
    dominant → sentence mentions "solvency" and "declined"

Run: `pytest tests/test_csp_module.py -v`

---

## DEPENDENCIES TO ADD TO `requirements.txt`

```
xgboost>=2.0.0      # Gradient boosting classifier for anomaly detection
shap>=0.44.0        # SHAP explainability (native XGBoost integration)
rapidfuzz>=3.5.0    # Fuzzy string matching for insurer name lookup
scikit-learn>=1.3.0 # Preprocessing, metrics, train/test split
joblib>=1.3.0       # Model persistence
pandas>=2.1.0       # Feature engineering
pytz>=2023.3        # Timezone (Africa/Harare)
```

---

## CRITICAL CONSTRAINTS

- **Never use React, Vue, or any JS framework** — Jinja2 + Chart.js CDN + vanilla JS only
- **Never use `Optional[str]`** — use `str | None` throughout
- **Never use SQLAlchemy `Column()`** — use `Mapped[]` / `mapped_column()` exclusively
- **Never use Pydantic v1 style** — `model_config = ConfigDict(...)` throughout
- **Never describe a CSP score as a credit rating, risk prediction, or public rating**
- **Never use forbidden NLG words**: risky, dangerous, failing, avoid, do not use
- **Full implementations only** — no placeholders, no TODOs, every method complete
- **Full inline comments and docstrings** on all code
- **All output is broker work product** — include the disclaimer in the UI template

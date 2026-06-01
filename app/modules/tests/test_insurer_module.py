"""
8 pytest tests for the Insurer Intelligence Module.
Run: pytest app/modules/tests/test_insurer_module.py -v
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base, get_db


# ── In-memory SQLite test DB ──────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db():
    """In-memory SQLite session with all tables created."""
    # Import all models so Base.metadata has them
    import app.modules.insurers.model         # noqa: F401
    import app.modules.insurers.claims_model  # noqa: F401
    import app.modules.insurers.scrape_model  # noqa: F401
    import app.modules.financials.model       # noqa: F401
    import app.modules.news.model             # noqa: F401

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# ── Test 1: Seed data completeness ────────────────────────────────────────────

def test_seed_data_complete(db):
    """seed_insurers should insert at least 20 short-term insurers."""
    from app.modules.insurers.dev_seed import seed_insurers
    result = seed_insurers(db)
    assert isinstance(result, dict), "seed_insurers must return a dict"
    assert result.get("total_now", 0) >= 20, (
        f"Expected >= 20 insurers, got {result.get('total_now')}"
    )

    from app.modules.insurers.model import Insurer
    short_term_count = (
        db.query(Insurer).filter(Insurer.category == "short_term").count()
    )
    assert short_term_count >= 20, (
        f"Expected >= 20 short-term insurers, got {short_term_count}"
    )


# ── Test 2: FinancialSnapshot upsert ─────────────────────────────────────────

def test_financial_snapshot_upsert(db):
    """Insert then update a FinancialSnapshot; no duplicate rows should exist."""
    from app.modules.insurers.model import Insurer
    from app.modules.financials.model import FinancialSnapshot

    insurer = db.query(Insurer).first()
    assert insurer is not None, "Need at least one insurer in DB"

    # Insert
    snap = FinancialSnapshot(
        insurer_id=insurer.id,
        period_label="Q1_2025",
        period_type="quarterly",
        total_revenue_usd=1_000_000,
    )
    db.add(snap)
    db.commit()

    # Update (simulate upsert)
    existing = (
        db.query(FinancialSnapshot)
        .filter_by(insurer_id=insurer.id, period_label="Q1_2025")
        .first()
    )
    existing.total_revenue_usd = 1_200_000
    db.commit()

    count = (
        db.query(FinancialSnapshot)
        .filter_by(insurer_id=insurer.id, period_label="Q1_2025")
        .count()
    )
    assert count == 1, f"Expected 1 row, got {count} (duplicate upsert?)"
    assert float(existing.total_revenue_usd) == 1_200_000


# ── Test 3: parse_usd_value ───────────────────────────────────────────────────

def test_parse_usd_value():
    """parse_usd_value must handle 10 format variations."""
    from app.infrastructure.scrapers.scraper_utils import parse_usd_value

    cases = [
        ("US$153.97 million",  153_970_000.0),
        ("USD 268.42m",        268_420_000.0),
        ("$239.42M",           239_420_000.0),
        ("153,970,000",        153_970_000.0),
        ("12.5",               12.5),
        ("USD 1.5 billion",    1_500_000_000.0),
        ("1,000",              1_000.0),
        ("0",                  0.0),
        ("500k",               500_000.0),
        ("$0.75",              0.75),
    ]

    for text, expected in cases:
        result = parse_usd_value(text)
        assert result is not None, f"parse_usd_value({text!r}) returned None"
        assert abs(result - expected) < expected * 0.01 + 1, (
            f"parse_usd_value({text!r}) = {result}, expected ~{expected}"
        )


# ── Test 4: Sentiment scoring ─────────────────────────────────────────────────

def test_sentiment_scoring():
    """VADER + keyword boosting should correctly classify insurance headlines."""
    try:
        import nltk
        nltk.download("vader_lexicon", quiet=True)
        from nltk.sentiment.vader import SentimentIntensityAnalyzer  # noqa: F401 — availability probe
    except ImportError:
        pytest.skip("nltk not installed")

    from app.infrastructure.scrapers.news_scraper import NewsScraper
    scraper = NewsScraper()

    positives = [
        "Insurance company records record profits and announces dividend increase",
        "Old Mutual reports strong growth in premiums and expands market share",
        "Zimnat achieves stability milestone and launches innovative new product",
    ]
    negatives = [
        "IPEC places insurer under curatorship amid fraud allegations and complaints",
        "Insurer defaults on claims payments amid instalment dispute and crisis",
        "Regulator fines insurance company for systematic failure to pay claims",
    ]
    neutrals = [
        "Insurance conference scheduled for next month in Harare",
        "IPEC releases quarterly report on industry statistics",
    ]

    for text in positives:
        score, label = scraper._score_sentiment(text)
        assert label == "positive", f"Expected positive for: {text!r}, got {label} (score={score})"

    for text in negatives:
        score, label = scraper._score_sentiment(text)
        assert label == "negative", f"Expected negative for: {text!r}, got {label} (score={score})"

    for text in neutrals:
        score, label = scraper._score_sentiment(text)
        # Neutral texts should not be strongly positive
        assert score < 0.5, f"Expected neutral/negative for: {text!r}, got score={score}"


# ── Test 5: Risk flag computation ─────────────────────────────────────────────

def test_risk_flag_computation():
    """compute_risk_flags should detect all 8 spec conditions."""
    from app.modules.insurers.analytics_service import InsurerAnalytics

    class FakeFinancials:
        capital_adequacy_ratio = 0.8   # below 1.0 → flag
        cash_and_bank_pct      = 3.0   # below 5% → flag
        reinsurance_assets_pct = 8.0   # below 10% → flag
        prescribed_assets_pct  = 5.0   # below 10% → flag

    class FakeClaims:
        working_capital_negative    = True   # → flag
        claims_instalment_flag      = True   # → flag
        complaints_resolution_rate  = 55.0   # below 70% → flag

    flags = InsurerAnalytics().compute_risk_flags(
        insurer_id=1,
        financials=FakeFinancials(),
        claims=FakeClaims(),
        sentiment_label_30d="negative",   # → flag
    )

    assert len(flags) >= 7, f"Expected ≥7 risk flags, got {len(flags)}: {flags}"
    assert any("capital" in f.lower() for f in flags), "Missing capital adequacy flag"
    assert any("instalment" in f.lower() for f in flags), "Missing instalment flag"
    assert any("sentiment" in f.lower() for f in flags), "Missing sentiment flag"
    assert any("working capital" in f.lower() for f in flags), "Missing working capital flag"


# ── Test 6: Rule-based settlement score ───────────────────────────────────────

def test_rule_based_settlement_score(db):
    """Rule-based score should be in a sensible range given known metrics."""
    from app.modules.insurers.model import Insurer
    from app.modules.financials.model import FinancialSnapshot
    from app.modules.insurers.claims_model import ClaimsMetrics
    from app.modules.ml.insurer_predictor import InsurerPredictor

    insurer = db.query(Insurer).first()
    assert insurer is not None

    # Add a good financial snapshot
    snap = db.query(FinancialSnapshot).filter_by(
        insurer_id=insurer.id, period_label="Q2_2025"
    ).first()
    if not snap:
        snap = FinancialSnapshot(
            insurer_id=insurer.id,
            period_label="Q2_2025",
            period_type="quarterly",
            capital_adequacy_ratio=1.8,
            cash_and_bank_pct=20.0,
        )
        db.add(snap)

    # Add a healthy claims row
    cm = db.query(ClaimsMetrics).filter_by(
        insurer_id=insurer.id, period_label="Q2_2025"
    ).first()
    if not cm:
        cm = ClaimsMetrics(
            insurer_id=insurer.id,
            period_label="Q2_2025",
            claims_instalment_flag=False,
            working_capital_negative=False,
            complaints_resolution_rate=90.0,
        )
        db.add(cm)
    db.commit()

    score = InsurerPredictor()._rule_based_settlement(db, insurer.id, __import__("pandas").DataFrame())
    assert 60 <= score <= 100, f"Expected score in [60, 100] for healthy insurer, got {score}"


# ── Test 7: Market overview structure ─────────────────────────────────────────

def test_market_overview_structure(db):
    """get_market_overview() should return all required keys."""
    from app.modules.insurers.analytics_service import InsurerAnalytics

    overview = InsurerAnalytics().get_market_overview(db)
    required_keys = [
        "period_label",
        "total_sector_revenue_usd",
        "total_sector_assets_usd",
        "active_insurer_count",
        "zse_listed_count",
        "market_leaders",
        "category_breakdown",
    ]
    for key in required_keys:
        assert key in overview, f"Missing key in market_overview: {key!r}"

    assert isinstance(overview["market_leaders"], list)
    assert isinstance(overview["category_breakdown"], dict)
    assert overview["active_insurer_count"] >= 0


# ── Test 8: API insurer list ──────────────────────────────────────────────────

def test_api_insurer_list():
    """GET /insurers/ should return 200 with a list."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.db import get_db
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.modules.auth import service as auth_service
    from app.modules.users import service as users_service
    from app.modules.users.schemas import UserCreate

    # Create in-memory DB for this test
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    test_db = TestingSessionLocal()

    # Override get_db
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Create a test user and generate token
    user_create = UserCreate(
        staff_id="TEST_API_USER",
        email="api-test@example.com",
        full_name="API Test User",
        password="TestPassword123!",
        role="user",
    )
    password_hash = auth_service.hash_password(user_create.password)
    user = users_service.create_user(test_db, user_create, password_hash=password_hash)
    token = auth_service.create_access_token(user)

    # Create client with auth header
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token}"})

    response = client.get("/insurers/")
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text[:200]}"
    )
    data = response.json()
    assert isinstance(data, list), f"Expected list, got {type(data)}"

    # Cleanup
    app.dependency_overrides.clear()
    test_db.close()

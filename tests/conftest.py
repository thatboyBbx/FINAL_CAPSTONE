"""
Test configuration and fixtures.

IMPORTANT: app.main must be imported BEFORE Base.metadata.create_all() so that
all model imports in main.py register their tables with Base.metadata. The import
order in this file is deliberate.

SQLite in-memory databases are connection-scoped by default — each new connection
gets a fresh empty database. We use StaticPool to force all connections to share
a single in-memory database instance.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 1. Import the app first — this triggers all model imports in main.py
from app.main import app  # noqa: E402  (must be first app import)

# 2. Now import Base/get_db — metadata is fully populated
from app.core.db import Base, get_db  # noqa: E402

from fastapi.testclient import TestClient
from app.modules.auth import service as auth_service
from app.modules.users import service as users_service
from app.modules.users.schemas import UserCreate

SQLALCHEMY_TEST_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # all connections share the same in-memory DB
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db):
    """Create a test user for authentication tests."""
    import uuid

    unique_id = str(uuid.uuid4())[:8]
    user_create = UserCreate(
        staff_id=f"TEST_USER_{unique_id}",
        email=f"test_{unique_id}@example.com",
        full_name="Test User",
        password="TestPassword123!",
        role="admin",
    )
    password_hash = auth_service.hash_password(user_create.password)
    user = users_service.create_user(db, user_create, password_hash=password_hash, role="admin")
    return user


@pytest.fixture
def auth_headers(test_user) -> dict:
    """Returns Authorization headers for a logged-in test user."""
    token = auth_service.create_access_token(test_user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_client(client, test_user):
    """Test client with a valid JWT session cookie."""
    token = auth_service.create_access_token(test_user)
    client.cookies.set("access_token", token)
    return client


@pytest.fixture
def authenticated_client(db):
    """Create a TestClient with an authenticated user and JWT token in headers."""
    import uuid

    def override_get_db():
        try:
            yield db
        finally:
            pass

    # Create a test user with a unique staff_id to avoid conflicts
    unique_id = str(uuid.uuid4())[:8]
    user_create = UserCreate(
        staff_id=f"TEST_USER_{unique_id}",
        email=f"test_{unique_id}@example.com",
        full_name="Test User",
        password="TestPassword123!",
        role="admin",
    )
    password_hash = auth_service.hash_password(user_create.password)
    user = users_service.create_user(db, user_create, password_hash=password_hash, role="admin")

    # Generate JWT token
    token = auth_service.create_access_token(user)

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        # Add Authorization header with Bearer token
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c
    app.dependency_overrides.clear()

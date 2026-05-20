"""
Tests that Alembic migrations are in a consistent state.
These tests do not apply migrations — they verify the migration files exist and are valid.
"""
from __future__ import annotations

from pathlib import Path

import pytest


class TestAlembicMigrationState:
    """Verify the Alembic version history has the expected structure."""

    def test_at_least_four_migration_files_exist(self) -> None:
        """There must be at least 4 migration files: baseline + 3 Phase 1 feature migrations."""
        versions_dir = Path("alembic/versions")
        migration_files = list(versions_dir.glob("*.py"))
        # Filter out __init__.py and README files
        real_migrations = [f for f in migration_files if not f.name.startswith("_")]
        assert len(real_migrations) >= 4, (
            f"Expected >= 4 migration files, found {len(real_migrations)}. "
            "Create feature migrations for clients, csp, compliance modules."
        )

    def test_clients_migration_exists(self) -> None:
        """There must be a migration file mentioning the clients module."""
        versions_dir = Path("alembic/versions")
        content = " ".join(f.read_text(encoding="utf-8") for f in versions_dir.glob("*.py"))
        assert "clients" in content.lower(), "No migration found for the clients module"

    def test_csp_migration_exists(self) -> None:
        """There must be a migration file mentioning the csp module."""
        versions_dir = Path("alembic/versions")
        content = " ".join(f.read_text(encoding="utf-8") for f in versions_dir.glob("*.py"))
        assert "csp" in content.lower(), "No migration found for the csp module"

    def test_compliance_migration_exists(self) -> None:
        """There must be a migration file mentioning the compliance module."""
        versions_dir = Path("alembic/versions")
        content = " ".join(f.read_text(encoding="utf-8") for f in versions_dir.glob("*.py"))
        assert "compliance" in content.lower(), "No migration found for the compliance module"

    def test_versions_dir_exists(self) -> None:
        """The alembic/versions directory must exist."""
        versions_dir = Path("alembic/versions")
        assert versions_dir.exists(), "alembic/versions directory not found"
        assert versions_dir.is_dir(), "alembic/versions is not a directory"

    def test_migration_files_have_upgrade_function(self) -> None:
        """Every migration file must define an upgrade() function."""
        versions_dir = Path("alembic/versions")
        for mf in versions_dir.glob("*.py"):
            if mf.name.startswith("_"):
                continue
            content = mf.read_text(encoding="utf-8")
            assert "def upgrade" in content, f"{mf.name} is missing an upgrade() function"

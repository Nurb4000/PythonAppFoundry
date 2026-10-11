"""Tests for Alembic migration framework."""
import os
import pytest


class TestMigrationFramework:
    """Test that migrations directory and files exist."""

    def test_migrations_directory_exists(self):
        """Migrations directory should exist."""
        assert os.path.isdir('migrations')

    def test_versions_directory_exists(self):
        """Migrations/versions directory should exist."""
        assert os.path.isdir('migrations/versions')

    def test_env_py_exists(self):
        """Alembic env.py should exist."""
        assert os.path.isfile('migrations/env.py')

    def test_alembic_ini_exists(self):
        """Alembic configuration file should exist."""
        assert os.path.isfile('migrations/alembic.ini')

    def test_initial_migration_exists(self):
        """Initial migration file should exist."""
        assert os.path.isfile('migrations/versions/001_initial.py')

    def test_allowed_groups_migration_exists(self):
        """Migration for allowed_groups column should exist."""
        assert os.path.isfile('migrations/versions/002_add_allowed_groups.py')

    def test_module_fields_migration_exists(self):
        """Migration for module fields should exist."""
        assert os.path.isfile('migrations/versions/003_add_module_fields.py')

    def test_query_reports_migration_exists(self):
        """Migration for query_reports.module_id should exist."""
        assert os.path.isfile('migrations/versions/004_add_query_reports_module_id.py')

    def test_migration_chain_is_valid(self, app_context):
        """Migration revisions should form a valid chain."""
        import importlib.util
        import os

        versions_dir = 'migrations/versions'
        migration_files = sorted([
            f for f in os.listdir(versions_dir)
            if f.endswith('.py') and not f.startswith('__')
        ])
        assert len(migration_files) >= 4

        # Load each migration module and check revision chain
        modules = []
        for f in migration_files:
            spec = importlib.util.spec_from_file_location(f.replace('.py', ''), os.path.join(versions_dir, f))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            modules.append(mod)

        # Check revision chain
        assert modules[0].down_revision is None
        assert modules[1].down_revision == 'initial'
        assert modules[2].down_revision == 'add_allowed_groups'
        assert modules[3].down_revision == 'add_module_fields'

    def test_migration_upgrade_downgrade(self, app_context):
        """Each migration should have upgrade and downgrade functions."""
        import importlib.util
        import os

        versions_dir = 'migrations/versions'
        for f in os.listdir(versions_dir):
            if not f.endswith('.py') or f.startswith('__'):
                continue
            spec = importlib.util.spec_from_file_location(f.replace('.py', ''), os.path.join(versions_dir, f))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            assert callable(getattr(mod, 'upgrade', None)), f'{f} missing upgrade()'
            assert callable(getattr(mod, 'downgrade', None)), f'{f} missing downgrade()'

    def test_inline_migration_fallback(self, app_context):
        """Inline migration fallback should work for legacy databases."""
        from app import _apply_inline_migrations, db as _db
        from sqlalchemy import inspect as sa_inspect

        inspector = sa_inspect(_db.get_engine())
        # Should not raise
        _apply_inline_migrations(inspector)

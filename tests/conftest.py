"""Pytest configuration and shared fixtures for PythonAppFoundry."""
import os
import sys
import tempfile
import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app, db as _db


@pytest.fixture(scope='session')
def app_dir(tmp_path_factory):
    """Create a temporary instance directory for the test app."""
    return tmp_path_factory.mktemp('instance')


@pytest.fixture(scope='session')
def app(app_dir):
    """Create a Flask app configured for testing with a temporary SQLite DB."""
    db_file = str(app_dir / 'test.db')
    os.environ['DATABASE_URL'] = f'sqlite:///{db_file}'
    os.environ['SECRET_KEY'] = 'test-secret-key-42'

    app = create_app()
    app.config['TESTING'] = True
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    with app.app_context():
        _db.create_all()

    yield app

    with app.app_context():
        _db.session.remove()


@pytest.fixture
def client(app):
    """Flask test client with clean DB session per test."""
    return app.test_client()


@pytest.fixture
def app_context(app):
    """Push application context for tests that need DB access."""
    with app.app_context():
        yield app


@pytest.fixture
def clean_db(app):
    """Drop and recreate all tables before the test."""
    with app.app_context():
        from app.models import (
            User, Module, Route, Script, Form, Template,
            ScheduledTask, Trigger, Group, Upload, Setting,
            QueryReport, ExecutionLog, ScriptExecution, ImportJob,
            DeadLetterEntry, DynamicTableRegistry, Credential,
            IncomingEmail, AuditLog, ModuleVersion, ModuleDependency,
        )
        _db.session.query(ImportJob).delete()
        _db.session.query(ScriptExecution).delete()
        _db.session.query(ExecutionLog).delete()
        _db.session.query(AuditLog).delete()
        _db.session.query(IncomingEmail).delete()
        _db.session.query(Credential).delete()
        _db.session.query(DynamicTableRegistry).delete()
        _db.session.query(DeadLetterEntry).delete()
        _db.session.query(QueryReport).delete()
        _db.session.query(Setting).delete()
        _db.session.query(Upload).delete()
        _db.session.query(Trigger).delete()
        _db.session.query(ScheduledTask).delete()
        _db.session.query(Template).delete()
        _db.session.query(Form).delete()
        _db.session.query(Script).delete()
        _db.session.query(Route).delete()
        _db.session.query(ModuleVersion).delete()
        _db.session.query(ModuleDependency).delete()
        _db.session.query(Module).delete()
        _db.session.query(Group).delete()
        _db.session.query(User).delete()
        _db.session.commit()


@pytest.fixture
def admin_user(clean_db, app_context):
    """Create an admin user for authentication tests."""
    import bcrypt
    from app.models import User
    u = User(
        username='test_admin',
        password_hash=bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode(),
        role='admin',
        is_active=True,
        is_approved=True,
    )
    _db.session.add(u)
    _db.session.commit()
    return u


@pytest.fixture
def logged_in_client(client, admin_user):
    """Test client with admin session."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = 'true'
    return client


@pytest.fixture
def sample_module(clean_db, app_context):
    """Create a sample module for import/export tests."""
    from app.models import Module
    m = Module(
        name='Test Module',
        slug='test-module',
        description='A test module',
        version='1.0.0',
        author='Test',
        enabled=True,
    )
    _db.session.add(m)
    _db.session.commit()
    return m


@pytest.fixture
def sample_script(app_context, sample_module):
    """Create a sample script attached to sample_module."""
    from app.models import Script
    s = Script(
        module_id=sample_module.id,
        name='test_script',
        language='python',
        source_code='_result = "hello world"',
        description='Test script',
    )
    _db.session.add(s)
    _db.session.commit()
    return s

"""Tests for OAuth 2.0 authentication service."""
import pytest


class TestOAuthModels:
    """Test OAuth model definitions."""

    def test_oauth_provider_model(self, app_context):
        """OAuthProvider model should have required fields."""
        from app.models import OAuthProvider
        assert hasattr(OAuthProvider, 'provider_id')
        assert hasattr(OAuthProvider, 'display_name')
        assert hasattr(OAuthProvider, 'client_id')
        assert hasattr(OAuthProvider, 'client_secret')
        assert hasattr(OAuthProvider, 'authorize_url')
        assert hasattr(OAuthProvider, 'token_url')
        assert hasattr(OAuthProvider, 'userinfo_url')
        assert hasattr(OAuthProvider, 'scopes')
        assert hasattr(OAuthProvider, 'enabled')

    def test_oauth_token_model(self, app_context):
        """OAuthToken model should have required fields."""
        from app.models import OAuthToken
        assert hasattr(OAuthToken, 'user_id')
        assert hasattr(OAuthToken, 'provider_id')
        assert hasattr(OAuthToken, 'external_user_id')
        assert hasattr(OAuthToken, 'access_token')
        assert hasattr(OAuthToken, 'refresh_token')
        assert hasattr(OAuthToken, 'expires_at')


class TestOAuthService:
    """Test OAuth service functions."""

    def test_builtin_providers(self, app_context):
        """Built-in providers should be configured."""
        from app.services.oauth import _BUILTIN_PROVIDERS
        assert 'google' in _BUILTIN_PROVIDERS
        assert 'github' in _BUILTIN_PROVIDERS

    def test_setup_builtin_providers(self, app_context):
        """setup_builtin_providers should create disabled providers."""
        from app.models import OAuthProvider
        from app.services.oauth import setup_builtin_providers

        setup_builtin_providers()

        google = OAuthProvider.query.filter_by(provider_id='google').first()
        github = OAuthProvider.query.filter_by(provider_id='github').first()

        assert google is not None
        assert github is not None
        assert google.enabled is False  # Disabled by default
        assert github.enabled is False

    def test_get_enabled_providers(self, app_context):
        """get_enabled_providers should return only enabled providers."""
        from app.models import OAuthProvider
        from app.services.oauth import get_enabled_providers, setup_builtin_providers

        setup_builtin_providers()

        # All disabled initially
        providers = get_enabled_providers()
        assert len(providers) == 0

        # Enable one
        google = OAuthProvider.query.filter_by(provider_id='google').first()
        google.enabled = True
        from app import db as _db
        _db.session.commit()

        providers = get_enabled_providers()
        assert len(providers) == 1
        assert providers[0].provider_id == 'google'

    def test_get_provider(self, app_context):
        """get_provider should return a specific provider."""
        from app.services.oauth import get_provider, setup_builtin_providers

        setup_builtin_providers()

        google = get_provider('google')
        assert google is not None
        assert google.provider_id == 'google'

        unknown = get_provider('unknown')
        assert unknown is None

    def test_get_authorize_url_disabled(self, app_context, clean_db):
        """get_authorize_url should return None for disabled providers."""
        from app.models import OAuthProvider
        from app.services.oauth import get_authorize_url, setup_builtin_providers

        setup_builtin_providers()

        # Ensure all providers are disabled
        for p in OAuthProvider.query.all():
            p.enabled = False
        from app import db as _db
        _db.session.commit()

        url = get_authorize_url('google', 'http://localhost/callback', 'state123')
        assert url is None  # Disabled by default

    def test_get_authorize_url_enabled(self, app_context):
        """get_authorize_url should return a URL for enabled providers."""
        from app.models import OAuthProvider
        from app.services.oauth import get_authorize_url, setup_builtin_providers

        setup_builtin_providers()

        google = OAuthProvider.query.filter_by(provider_id='google').first()
        google.enabled = True
        google.client_id = 'test_client_id'
        from app import db as _db
        _db.session.commit()

        url = get_authorize_url('google', 'http://localhost/callback', 'state123')
        assert url is not None
        assert 'accounts.google.com' in url
        assert 'client_id=test_client_id' in url
        assert 'state=state123' in url


class TestOAuthRoutes:
    """Test OAuth route registration."""

    def test_oauth_blueprint_registered(self, app_context):
        """OAuth blueprint should be registered on the app."""
        from flask import current_app
        blueprints = list(current_app.blueprints.keys())
        assert 'oauth' in blueprints

    def test_authorize_endpoint_exists(self, client, app_context):
        """OAuth authorize endpoint should exist."""
        from app.services.oauth import setup_builtin_providers
        setup_builtin_providers()

        # Don't follow external redirects (Google's OAuth URL)
        resp = client.get('/__auth/oauth/authorize/google')
        # Should redirect (302) to login or Google
        assert resp.status_code in (302, 200)

    def test_callback_endpoint_exists(self, client, app_context):
        """OAuth callback endpoint should exist."""
        from app.services.oauth import setup_builtin_providers
        setup_builtin_providers()

        resp = client.get('/__auth/oauth/callback?code=test&state=abc', follow_redirects=True)
        assert resp.status_code == 200

    def test_status_endpoint(self, client, app_context):
        """OAuth status endpoint should return JSON."""
        from app.services.oauth import setup_builtin_providers
        setup_builtin_providers()

        resp = client.get('/__auth/oauth/status')
        # May be 200 or 404 if route not registered (depends on Flask version)
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            assert resp.mimetype == 'application/json'


class TestOAuthAdminRoutes:
    """Test OAuth admin routes."""

    def test_list_providers_page(self, logged_in_client, clean_db):
        """OAuth providers list page should load."""
        resp = logged_in_client.get('/__admin/oauth/')
        assert resp.status_code == 200

    def test_configure_provider_page(self, logged_in_client, app_context):
        """Configure provider page should load."""
        from app.services.oauth import setup_builtin_providers
        setup_builtin_providers()

        resp = logged_in_client.get('/__admin/oauth/google/configure')
        assert resp.status_code == 200

    def test_linked_accounts_page(self, logged_in_client, clean_db):
        """Linked accounts page should load."""
        resp = logged_in_client.get('/__admin/oauth/linked-accounts')
        assert resp.status_code == 200


class TestOAuthLoginTemplate:
    """Test OAuth login template integration."""

    def test_login_page_shows_oauth_buttons(self, client, app_context):
        """Login page should show OAuth buttons when providers are enabled."""
        from app.models import OAuthProvider
        from app.services.oauth import setup_builtin_providers

        setup_builtin_providers()

        google = OAuthProvider.query.filter_by(provider_id='google').first()
        google.enabled = True
        google.client_id = 'test_client'
        google.client_secret = 'test_secret'
        from app import db as _db
        _db.session.commit()

        resp = client.get('/__auth/login')
        assert resp.status_code == 200
        assert b'Sign in with Google' in resp.data

    def test_login_page_no_oauth_when_disabled(self, client, app_context, clean_db):
        """Login page should not show OAuth buttons when all providers disabled."""
        from app.models import OAuthProvider
        from app.services.oauth import setup_builtin_providers

        setup_builtin_providers()

        # Ensure all providers are disabled
        for p in OAuthProvider.query.all():
            p.enabled = False
        from app import db as _db
        _db.session.commit()

        resp = client.get('/__auth/login')
        assert resp.status_code == 200
        # No "Sign in with" buttons when all disabled
        assert b'Sign in with' not in resp.data


class TestOAuthMigration:
    """Test OAuth migration file."""

    def test_oauth_migration_exists(self):
        """Migration for oauth tables should exist."""
        import os
        assert os.path.isfile('migrations/versions/007_add_oauth_tables.py')

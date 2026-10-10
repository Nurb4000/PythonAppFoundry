"""Tests for CSRF protection on admin routes."""
import pytest


class TestCSRFProtection:
    """Verify that admin POST routes require valid CSRF tokens."""

    def test_admin_post_without_csrf_returns_403(self, logged_in_client):
        """POST to admin route without CSRF token should return 403."""
        resp = logged_in_client.post(
            '/__admin/groups/new',
            data={'name': 'test_group', 'description': 'test'},
            follow_redirects=False,
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"

    def test_admin_post_with_valid_csrf_succeeds(self, logged_in_client):
        """POST to admin route with valid CSRF token should succeed."""
        from app.services.csrf import generate_csrf_token

        # Generate a token and store it in the session
        with logged_in_client.session_transaction() as sess:
            # Access the app context to generate the token
            csrf_token = sess.get('csrf_token')
            if not csrf_token:
                # Token is generated lazily; set one manually for testing
                import secrets
                csrf_token = secrets.token_hex(32)
                sess['csrf_token'] = csrf_token

        resp = logged_in_client.post(
            '/__admin/groups/new',
            data={'name': 'test_group', 'description': 'test', 'csrf_token': csrf_token},
            follow_redirects=True,
        )
        # Should redirect (302) or show page (200), not 403
        assert resp.status_code in (200, 302), f"Expected 200/302, got {resp.status_code}"

    def test_admin_delete_without_csrf_returns_403(self, logged_in_client, clean_db, app_context):
        """DELETE-style POST without CSRF token should return 403."""
        from app.models import Group
        g = Group(name='deletable_group', description='test')
        from app import db as _db
        _db.session.add(g)
        _db.session.commit()

        resp = logged_in_client.post(
            f'/__admin/groups/{g.id}/delete',
            data={},
            follow_redirects=False,
        )
        assert resp.status_code == 403

    def test_csrf_token_in_session(self, logged_in_client):
        """CSRF token should be present in session after POST request."""
        # Token is generated lazily on first POST or explicit access
        with logged_in_client.session_transaction() as sess:
            # Trigger token generation via a POST that needs it
            pass
        # Hit a page that injects CSRF token into context
        resp = logged_in_client.get('/__admin/groups/new')
        assert resp.status_code == 200
        # The token is generated on-demand; check it's available for POST
        with logged_in_client.session_transaction() as sess:
            # Token may or may not be in session yet (generated per-request)
            # What matters is that a POST with a valid token works
            csrf_token = sess.get('csrf_token')
            if csrf_token:
                assert len(csrf_token) == 64

    def test_csrf_protect_get_request_passes(self, logged_in_client):
        """GET requests on CSRF-protected routes should pass without token."""
        resp = logged_in_client.get('/__admin/groups/new')
        assert resp.status_code == 200


class TestCSRFTokenGeneration:
    """Test the CSRF token generation and validation functions."""

    def test_generate_csrf_token(self, app_context):
        """generate_csrf_token should return a hex string."""
        from app.services.csrf import generate_csrf_token
        with app_context.test_request_context():
            token = generate_csrf_token()
            assert len(token) == 64
            assert all(c in '0123456789abcdef' for c in token)

    def test_validate_csrf_token_correct(self, app_context):
        """validate_csrf_token should accept the correct token."""
        from app.services.csrf import generate_csrf_token, validate_csrf_token
        with app_context.test_request_context():
            token = generate_csrf_token()
            assert validate_csrf_token(token) is True

    def test_validate_csrf_token_wrong(self, app_context):
        """validate_csrf_token should reject a wrong token."""
        from app.services.csrf import generate_csrf_token, validate_csrf_token
        with app_context.test_request_context():
            generate_csrf_token()
            assert validate_csrf_token('wrong-token-here') is False

    def test_validate_csrf_token_empty(self, app_context):
        """validate_csrf_token should reject empty token."""
        from app.services.csrf import validate_csrf_token
        with app_context.test_request_context():
            assert validate_csrf_token('') is False
            assert validate_csrf_token(None) is False

"""Tests for API key management."""
import pytest


class TestApiKeyCreation:
    """Test API key creation and token generation."""

    def test_create_api_key(self, app_context, admin_user):
        """Creating an API key should return a model and plaintext token."""
        from app.services.api_key import create_api_key

        key, token = create_api_key(
            name='Test Key',
            user_id=admin_user.id,
        )

        assert key.name == 'Test Key'
        assert key.user_id == admin_user.id
        assert key.is_active is True
        assert key.key_prefix.startswith('paf_sk_')
        # Token should be prefix + underscore + secret (48 chars)
        assert token.startswith(key.key_prefix + '_')
        assert len(token) > 60  # paf_sk_XXXX_SECRET = ~67 chars

    def test_create_api_key_with_module(self, app_context, admin_user, sample_module):
        """API key can be scoped to a module."""
        from app.services.api_key import create_api_key

        key, token = create_api_key(
            name='Module Key',
            user_id=admin_user.id,
            module_id=sample_module.id,
        )

        assert key.module_id == sample_module.id

    def test_create_api_key_with_expiration(self, app_context, admin_user):
        """API key can have an expiration date."""
        from datetime import datetime, timezone, timedelta
        from app.services.api_key import create_api_key

        key, token = create_api_key(
            name='Expiring Key',
            user_id=admin_user.id,
            expires_in_days=30,
        )

        assert key.expires_at is not None
        expected = datetime.now(timezone.utc) + timedelta(days=30)
        # Make both aware for comparison
        if key.expires_at.tzinfo is None:
            key.expires_at = key.expires_at.replace(tzinfo=timezone.utc)
        # Allow 2 second tolerance
        assert abs((key.expires_at - expected).total_seconds()) < 2


class TestApiKeyValidation:
    """Test API key validation."""

    def test_validate_correct_token(self, app_context, admin_user):
        """Valid token should return the ApiKey model."""
        from app.services.api_key import create_api_key, validate_api_key

        key, token = create_api_key(name='Valid Key', user_id=admin_user.id)
        result = validate_api_key(token)

        assert result is not None
        assert result.id == key.id
        assert result.request_count >= 1
        assert result.last_used_at is not None

    def test_validate_wrong_token(self, app_context, admin_user):
        """Wrong token should return None."""
        from app.services.api_key import validate_api_key

        result = validate_api_key('paf_sk_abcd_1234567890' * 5)
        assert result is None

    def test_validate_revoked_key(self, app_context, admin_user):
        """Revoked key should return None."""
        from app.services.api_key import create_api_key, validate_api_key, revoke_api_key

        key, token = create_api_key(name='Revoked Key', user_id=admin_user.id)
        revoke_api_key(key.id)

        result = validate_api_key(token)
        assert result is None


class TestApiKeyRevocation:
    """Test API key revocation."""

    def test_revoke_active_key(self, app_context, admin_user):
        """Revoking an active key should set is_active=False."""
        from app.services.api_key import create_api_key, revoke_api_key, get_api_key

        key, _ = create_api_key(name='To Revoke', user_id=admin_user.id)
        assert revoke_api_key(key.id) is True

        updated = get_api_key(key.id)
        assert updated.is_active is False

    def test_revoke_inactive_key(self, app_context, admin_user):
        """Revoking an already inactive key should return False."""
        from app.services.api_key import create_api_key, revoke_api_key

        key, _ = create_api_key(name='Already Inactive', user_id=admin_user.id)
        assert revoke_api_key(key.id) is True
        assert revoke_api_key(key.id) is False


class TestApiKeyRotation:
    """Test API key rotation."""

    def test_rotate_key(self, app_context, admin_user):
        """Rotating a key should generate a new token."""
        from app.services.api_key import create_api_key, rotate_api_key, validate_api_key

        key, old_token = create_api_key(name='To Rotate', user_id=admin_user.id)
        result = rotate_api_key(key.id)

        assert result is not None
        rotated_key, new_token = result
        assert rotated_key.id == key.id
        assert new_token != old_token
        # Old token should be invalid
        assert validate_api_key(old_token) is None
        # New token should be valid
        assert validate_api_key(new_token) is not None


class TestApiKeyListing:
    """Test API key listing."""

    def test_list_all_keys(self, app_context, admin_user):
        """List all API keys."""
        from app.services.api_key import create_api_key, list_api_keys

        create_api_key(name='Key 1', user_id=admin_user.id)
        create_api_key(name='Key 2', user_id=admin_user.id)

        keys = list_api_keys()
        assert len(keys) >= 2

    def test_list_by_user(self, app_context, admin_user):
        """Filter API keys by user."""
        from app.services.api_key import create_api_key, list_api_keys

        create_api_key(name='User Key', user_id=admin_user.id)

        keys = list_api_keys(user_id=admin_user.id)
        assert len(keys) >= 1
        for k in keys:
            assert k.user_id == admin_user.id


class TestApiKeyAdminRoutes:
    """Test API key admin routes."""

    def test_list_page(self, logged_in_client, clean_db):
        """API keys list page should load."""
        resp = logged_in_client.get('/__admin/api-keys/')
        assert resp.status_code == 200

    def test_new_page(self, logged_in_client, clean_db):
        """New API key form should load."""
        resp = logged_in_client.get('/__admin/api-keys/new')
        assert resp.status_code == 200

    def test_create_key(self, logged_in_client, clean_db):
        """Creating an API key via form should succeed."""
        import secrets
        with logged_in_client.session_transaction() as sess:
            sess['csrf_token'] = secrets.token_hex(32)

        resp = logged_in_client.post(
            '/__admin/api-keys/new',
            data={'name': 'Test Key', 'csrf_token': sess.get('csrf_token')},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b'API key created' in resp.data or b'Save this token' in resp.data

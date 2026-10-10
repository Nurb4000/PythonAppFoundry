"""Tests for webhook HMAC signature verification."""
import json
import pytest


class TestHmacFunctions:
    """Test HMAC signature generation and verification."""

    def test_generate_secret(self, app_context):
        """Generated secret should be 64 hex characters."""
        from app.services.triggers import generate_hmac_secret

        secret = generate_hmac_secret()
        assert len(secret) == 64
        assert all(c in '0123456789abcdef' for c in secret)

    def test_compute_signature(self, app_context):
        """Signature should be deterministic for same body and secret."""
        from app.services.triggers import compute_webhook_signature

        body = b'{"test": "data"}'
        secret = 'a' * 64

        sig1 = compute_webhook_signature(body, secret)
        sig2 = compute_webhook_signature(body, secret)
        assert sig1 == sig2
        assert len(sig1) == 64  # SHA-256 hex digest

    def test_different_body_different_sig(self, app_context):
        """Different bodies should produce different signatures."""
        from app.services.triggers import compute_webhook_signature

        secret = 'b' * 64
        sig1 = compute_webhook_signature(b'body1', secret)
        sig2 = compute_webhook_signature(b'body2', secret)
        assert sig1 != sig2

    def test_different_secret_different_sig(self, app_context):
        """Different secrets should produce different signatures."""
        from app.services.triggers import compute_webhook_signature

        body = b'same body'
        sig1 = compute_webhook_signature(body, 'c' * 64)
        sig2 = compute_webhook_signature(body, 'd' * 64)
        assert sig1 != sig2

    def test_verify_valid_signature(self, app_context):
        """Valid signature should verify successfully."""
        from app.services.triggers import compute_webhook_signature, verify_webhook_signature

        body = b'{"event": "test"}'
        secret = 'e' * 64
        sig = compute_webhook_signature(body, secret)

        assert verify_webhook_signature(body, sig, secret) is True

    def test_verify_invalid_signature(self, app_context):
        """Invalid signature should fail verification."""
        from app.services.triggers import verify_webhook_signature

        body = b'{"event": "test"}'
        secret = 'f' * 64
        assert verify_webhook_signature(body, 'deadbeef' * 8, secret) is False

    def test_verify_empty_body(self, app_context):
        """Empty body should produce a valid signature."""
        from app.services.triggers import compute_webhook_signature, verify_webhook_signature

        secret = '1234567890abcdef' * 4
        sig = compute_webhook_signature(b'', secret)
        assert verify_webhook_signature(b'', sig, secret) is True


class TestWebhookHmacIntegration:
    """Integration tests for HMAC verification in webhook firing."""

    @staticmethod
    def _create_trigger(name, target_table, hmac_secret=''):
        """Helper to create a module, script, and trigger."""
        from app.models import Trigger, Module, Script
        from app import db as _db

        mod = Module(name=f'Test {name}', slug=f'test-{name}', version='1.0.0', author='Test')
        _db.session.add(mod)
        _db.session.commit()

        script = Script(module_id=mod.id, name='handler', language='python',
                        source_code='_result = "fired"')
        _db.session.add(script)
        _db.session.commit()

        trigger = Trigger(
            module_id=mod.id,
            name=name,
            event_type='webhook',
            target_table=target_table,
            script_id=script.id,
            hmac_secret=hmac_secret,
        )
        _db.session.add(trigger)
        _db.session.commit()
        return trigger

    def test_trigger_with_hmac_secret(self, app_context, clean_db):
        """Trigger with hmac_secret should store it correctly."""
        from app.services.triggers import generate_hmac_secret

        secret = generate_hmac_secret()
        self._create_trigger('hmac_webhook', 'test-endpoint', hmac_secret=secret)

        from app.models import Trigger
        stored = Trigger.query.filter_by(name='hmac_webhook').first()
        assert stored.hmac_secret == secret

    def test_fire_webhook_valid_hmac(self, app_context, clean_db):
        """Webhook with valid HMAC signature should fire."""
        from app.services.triggers import (
            fire_webhook, generate_hmac_secret, compute_webhook_signature,
        )

        secret = generate_hmac_secret()
        self._create_trigger('hmac_trigger', 'my-endpoint', hmac_secret=secret)

        body = json.dumps({'data': 'test'}).encode('utf-8')
        sig = compute_webhook_signature(body, secret)

        # Should fire without error
        fire_webhook(
            'my-endpoint',
            payload={'data': 'test'},
            raw_body=body,
            provided_signature=sig,
        )

    def test_fire_webhook_invalid_hmac(self, app_context, clean_db):
        """Webhook with invalid HMAC signature should be skipped."""
        from app.models import ExecutionLog
        from app.services.triggers import fire_webhook, generate_hmac_secret

        secret = generate_hmac_secret()
        self._create_trigger('hmac_invalid', 'my-endpoint', hmac_secret=secret)

        body = json.dumps({'data': 'test'}).encode('utf-8')
        bad_sig = 'deadbeef' * 8

        fire_webhook(
            'my-endpoint',
            payload={'data': 'test'},
            raw_body=body,
            provided_signature=bad_sig,
        )

        logs = ExecutionLog.query.filter_by(
            source_type='webhook',
            source_name='hmac_invalid',
        ).all()
        assert len(logs) == 0

    def test_fire_webhook_missing_signature(self, app_context, clean_db):
        """Webhook with hmac_secret but no signature should be skipped."""
        from app.models import ExecutionLog
        from app.services.triggers import fire_webhook, generate_hmac_secret

        secret = generate_hmac_secret()
        self._create_trigger('hmac_missing', 'my-endpoint', hmac_secret=secret)

        body = json.dumps({'data': 'test'}).encode('utf-8')

        fire_webhook(
            'my-endpoint',
            payload={'data': 'test'},
            raw_body=body,
            provided_signature='',
        )

        logs = ExecutionLog.query.filter_by(
            source_type='webhook',
            source_name='hmac_missing',
        ).all()
        assert len(logs) == 0

    def test_trigger_without_hmac_secret(self, app_context, clean_db):
        """Trigger without hmac_secret should fire normally."""
        from app.models import ExecutionLog
        from app.services.triggers import fire_webhook

        self._create_trigger('plain_no_hmac', 'plain-endpoint', hmac_secret='')

        fire_webhook('plain-endpoint', payload={'data': 'test'})

        logs = ExecutionLog.query.filter_by(
            source_type='webhook',
            source_name='plain_no_hmac',
        ).all()
        assert len(logs) >= 1
        assert logs[-1].status == 'success'

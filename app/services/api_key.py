"""API key management: generation, validation, rotation, revocation.

Keys are stored as bcrypt hashes.  The plaintext token is returned once at
creation time so the caller can store it securely.
"""
import logging
import secrets
import string

from datetime import datetime, timezone

import bcrypt

from app import db
from app.models import ApiKey, User

logger = logging.getLogger(__name__)

# Characters used for the secret portion of API keys
_KEY_CHARS = string.ascii_letters + string.digits


def _generate_token() -> str:
    """Generate a random 48-character alphanumeric token."""
    return ''.join(secrets.choice(_KEY_CHARS) for _ in range(48))


def create_api_key(name: str, user_id: int, module_id: int | None = None,
                   expires_in_days: int | None = None) -> tuple[ApiKey, str]:
    """Create a new API key.

    Returns
    -------
    tuple[ApiKey, str]
        The ApiKey model instance and the plaintext token (shown once).
    """
    secret = _generate_token()
    prefix = f'paf_sk_{secrets.token_hex(4)}'
    full_token = f'{prefix}_{secret}'
    key_hash = bcrypt.hashpw(full_token.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    expires_at = None
    if expires_in_days:
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

    key = ApiKey(
        name=name,
        key_hash=key_hash,
        key_prefix=prefix,
        user_id=user_id,
        module_id=module_id,
        expires_at=expires_at,
    )
    db.session.add(key)
    db.session.commit()

    logger.info(f'API key created: {name} (user={user_id}, module={module_id})')
    return key, full_token


def validate_api_key(token: str) -> ApiKey | None:
    """Validate an API key token.

    Returns the ApiKey model if valid, None otherwise.
    Updates last_used_at and request_count on success.
    """
    if not token or not token.startswith('paf_sk_'):
        return None

    keys = db.session.query(ApiKey).filter_by(is_active=True).all()
    for k in keys:
        if bcrypt.checkpw(token.encode('utf-8'), k.key_hash.encode('utf-8')):
            # Check expiration
            now = datetime.now(timezone.utc)
            if k.expires_at and now > k.expires_at:
                return None
            # Update usage stats
            k.last_used_at = now
            k.request_count = (k.request_count or 0) + 1
            db.session.commit()
            return k

    return None


def revoke_api_key(key_id: int) -> bool:
    """Revoke an API key by setting is_active=False."""
    key = db.session.get(ApiKey, key_id)
    if key and key.is_active:
        key.is_active = False
        db.session.commit()
        logger.info(f'API key revoked: {key.name} (id={key_id})')
        return True
    return False


def rotate_api_key(key_id: int) -> tuple[ApiKey, str] | None:
    """Rotate an API key: generate new token, keep metadata.

    Returns the updated ApiKey and new plaintext token, or None if not found.
    """
    key = db.session.get(ApiKey, key_id)
    if not key:
        return None

    secret = _generate_token()
    new_prefix = f'paf_sk_{secrets.token_hex(4)}'
    full_token = f'{new_prefix}_{secret}'
    key.key_hash = bcrypt.hashpw(full_token.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    key.key_prefix = new_prefix
    db.session.commit()

    logger.info(f'API key rotated: {key.name} (id={key_id})')
    return key, full_token


def list_api_keys(user_id: int | None = None, module_id: int | None = None):
    """List API keys with optional filters."""
    q = db.session.query(ApiKey)
    if user_id is not None:
        q = q.filter_by(user_id=user_id)
    if module_id is not None:
        q = q.filter_by(module_id=module_id)
    return q.order_by(ApiKey.created_at.desc()).all()


def get_api_key(key_id: int) -> ApiKey | None:
    """Get a single API key by ID."""
    return db.session.get(ApiKey, key_id)

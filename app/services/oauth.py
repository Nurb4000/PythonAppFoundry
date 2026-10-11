"""OAuth 2.0 authentication service.

Provides optional social login via OAuth 2.0 providers (Google, GitHub, etc.).
The platform continues to work with local username/password auth when all
providers are disabled.
"""
import logging
from datetime import datetime, timezone, timedelta

import requests

from app import db
from app.models import OAuthProvider, OAuthToken, User

logger = logging.getLogger(__name__)

# Built-in provider configurations
_BUILTIN_PROVIDERS = {
    'google': {
        'display_name': 'Google',
        'authorize_url': 'https://accounts.google.com/o/oauth2/v2/auth',
        'token_url': 'https://oauth2.googleapis.com/token',
        'userinfo_url': 'https://www.googleapis.com/oauth2/v2/userinfo',
        'scopes': 'email profile',
    },
    'github': {
        'display_name': 'GitHub',
        'authorize_url': 'https://github.com/login/oauth/authorize',
        'token_url': 'https://github.com/login/oauth/access_token',
        'userinfo_url': 'https://api.github.com/user',
        'scopes': 'user:email',
    },
}


def get_enabled_providers():
    """Return list of enabled OAuth providers."""
    return OAuthProvider.query.filter_by(enabled=True).all()


def get_provider(provider_id):
    """Get a specific OAuth provider by ID."""
    return OAuthProvider.query.filter_by(provider_id=provider_id).first()


def setup_builtin_providers():
    """Initialize built-in provider configurations if they don't exist.

    Providers are created in disabled state by default — admins must enable
    them and configure client_id/client_secret via the admin UI.
    """
    for pid, config in _BUILTIN_PROVIDERS.items():
        existing = OAuthProvider.query.filter_by(provider_id=pid).first()
        if not existing:
            provider = OAuthProvider(
                provider_id=pid,
                display_name=config['display_name'],
                authorize_url=config['authorize_url'],
                token_url=config['token_url'],
                userinfo_url=config['userinfo_url'],
                scopes=config['scopes'],
                enabled=False,  # Disabled by default
            )
            db.session.add(provider)
    db.session.commit()


def get_authorize_url(provider_id, redirect_uri, state):
    """Build the OAuth authorization URL for a provider.

    Args:
        provider_id: Provider identifier (e.g., 'google', 'github')
        redirect_uri: Callback URL for the authorization response
        state: CSRF state parameter

    Returns:
        Authorization URL string, or None if provider not found/disabled
    """
    provider = get_provider(provider_id)
    if not provider or not provider.enabled:
        return None

    params = {
        'client_id': provider.client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': provider.scopes,
        'state': state,
    }

    # Build URL with query parameters
    from urllib.parse import urlencode
    return f'{provider.authorize_url}?{urlencode(params)}'


def exchange_code_for_token(provider_id, code, redirect_uri):
    """Exchange an authorization code for an access token.

    Args:
        provider_id: Provider identifier
        code: Authorization code from the callback
        redirect_uri: Callback URL (must match the one used in authorize)

    Returns:
        Dict with token data, or None on failure
    """
    provider = get_provider(provider_id)
    if not provider or not provider.enabled:
        return None

    params = {
        'client_id': provider.client_id,
        'client_secret': provider.client_secret,
        'code': code,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }

    try:
        resp = requests.post(provider.token_url, data=params, timeout=10)
        resp.raise_for_status()

        # GitHub returns form-encoded data, others return JSON
        if provider.provider_id == 'github':
            from urllib.parse import parse_qs
            token_data = parse_qs(resp.text)
            # Flatten single-value lists
            for key in token_data:
                if len(token_data[key]) == 1:
                    token_data[key] = token_data[key][0]
        else:
            token_data = resp.json()

        return token_data

    except Exception as e:
        logger.warning(f'OAuth token exchange failed for {provider_id}: {e}')
        return None


def get_userinfo(provider_id, access_token):
    """Fetch user information from the provider.

    Args:
        provider_id: Provider identifier
        access_token: OAuth access token

    Returns:
        Dict with user info, or None on failure
    """
    provider = get_provider(provider_id)
    if not provider or not provider.enabled:
        return None

    headers = {}
    if provider.provider_id == 'github':
        headers['Accept'] = 'application/vnd.github.v3+json'
    else:
        headers['Authorization'] = f'Bearer {access_token}'

    try:
        resp = requests.get(provider.userinfo_url, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()

    except Exception as e:
        logger.warning(f'OAuth userinfo fetch failed for {provider_id}: {e}')
        return None


def authenticate_with_oauth(provider_id, code, redirect_uri):
    """Complete OAuth authentication flow.

    Exchanges the authorization code for a token, fetches user info,
    and creates or updates the local User account.

    Args:
        provider_id: Provider identifier
        code: Authorization code from the callback
        redirect_uri: Callback URL

    Returns:
        User object if authentication successful, None otherwise
    """
    # Exchange code for token
    token_data = exchange_code_for_token(provider_id, code, redirect_uri)
    if not token_data:
        return None

    access_token = token_data.get('access_token', '')
    refresh_token = token_data.get('refresh_token', '')
    token_type = token_data.get('token_type', 'Bearer')
    expires_in = token_data.get('expires_in', 3600)

    # Calculate expiration time
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in) if expires_in else None

    # Fetch user info
    userinfo = get_userinfo(provider_id, access_token)
    if not userinfo:
        return None

    # Extract user details based on provider
    external_user_id = ''
    email = ''
    name = ''

    if provider_id == 'google':
        external_user_id = userinfo.get('id', '')
        email = userinfo.get('email', '')
        name = userinfo.get('name', '')
    elif provider_id == 'github':
        external_user_id = str(userinfo.get('id', ''))
        # GitHub may return primary email from a separate endpoint
        email = userinfo.get('email', '') or ''
        name = userinfo.get('name', '') or userinfo.get('login', '')

    if not external_user_id:
        logger.warning(f'OAuth user missing external ID for {provider_id}')
        return None

    # Find or create user
    existing_token = OAuthToken.query.filter_by(
        provider_id=provider_id,
        external_user_id=external_user_id,
    ).first()

    if existing_token:
        # Update existing token
        existing_token.access_token = access_token
        existing_token.refresh_token = refresh_token
        existing_token.expires_at = expires_at
        user = existing_token.user
    else:
        # Find user by email or create new one
        user = None
        if email:
            user = User.query.filter_by(email=email).first()

        if not user:
            # Create new user
            import bcrypt
            username = name.lower().replace(' ', '_') or f'{provider_id}_{external_user_id[:8]}'
            # Ensure unique username
            base_username = username
            counter = 1
            while User.query.filter_by(username=username).first():
                username = f'{base_username}_{counter}'
                counter += 1

            user = User(
                username=username,
                email=email,
                password_hash=bcrypt.hashpw(b'oauth', bcrypt.gensalt()).decode(),
                role='user',
                is_active=True,
                is_approved=True,
            )
            db.session.add(user)

        # Create new token record
        token = OAuthToken(
            user_id=user.id,
            provider_id=provider_id,
            external_user_id=external_user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_type=token_type,
            expires_at=expires_at,
        )
        db.session.add(token)

    db.session.commit()
    logger.info(f'OAuth authentication successful: {user.username} via {provider_id}')
    return user


def init_oauth(app):
    """Initialize OAuth service on the Flask app.

    Sets up built-in provider configurations if they don't exist.
    """
    with app.app_context():
        setup_builtin_providers()

"""OAuth 2.0 authentication routes."""
import secrets
from flask import Blueprint, request, redirect, url_for, flash, session
from app.services.oauth import (
    get_enabled_providers,
    get_authorize_url,
    authenticate_with_oauth,
)
from app import db
from flask_login import login_user

oauth_bp = Blueprint('oauth', __name__, url_prefix='/__auth/oauth')


@oauth_bp.route('/authorize/<provider_id>')
def authorize(provider_id):
    """Redirect to the OAuth provider's authorization page.

    Args:
        provider_id: Provider identifier (e.g., 'google', 'github')
    """
    # Generate state parameter for CSRF protection
    state = secrets.token_hex(32)
    session['oauth_state'] = state
    session['oauth_provider'] = provider_id

    # Build redirect URI
    redirect_uri = url_for('oauth.callback', _external=True)

    # Get authorization URL
    authorize_url = get_authorize_url(provider_id, redirect_uri, state)
    if not authorize_url:
        flash(f'OAuth provider "{provider_id}" not found or disabled', 'error')
        return redirect(url_for('auth.login'))

    return redirect(authorize_url)


@oauth_bp.route('/callback')
def callback():
    """Handle the OAuth callback from the provider.

    Exchanges the authorization code for a token, fetches user info,
    and logs in the user.
    """
    code = request.args.get('code', '')
    state = request.args.get('state', '')
    error = request.args.get('error', '')

    # Handle OAuth error
    if error:
        error_desc = request.args.get('error_description', error)
        flash(f'OAuth error: {error_desc}', 'error')
        return redirect(url_for('auth.login'))

    # Verify state parameter (CSRF protection)
    stored_state = session.pop('oauth_state', '')
    provider_id = session.pop('oauth_provider', '')

    if not state or state != stored_state:
        flash('OAuth state mismatch', 'error')
        return redirect(url_for('auth.login'))

    if not code:
        flash('Missing authorization code', 'error')
        return redirect(url_for('auth.login'))

    # Get redirect URI
    redirect_uri = url_for('oauth.callback', _external=True)

    # Authenticate with OAuth provider
    user = authenticate_with_oauth(provider_id, code, redirect_uri)
    if not user:
        flash(f'OAuth authentication failed for {provider_id}', 'error')
        return redirect(url_for('auth.login'))

    # Log in the user
    login_user(user, remember=True)
    flash(f'Signed in via {provider_id}', 'success')

    # Redirect to next page or home
    next_url = session.pop('oauth_next', '/')
    return redirect(next_url or '/')


@oauth_bp.route('/linked-accounts')
def linked_accounts():
    """Show linked OAuth accounts for the current user.

    Returns JSON list of linked providers.
    """
    from flask_login import login_required, current_user
    from app.models import OAuthToken

    @login_required
    def _linked_accounts():
        tokens = OAuthToken.query.filter_by(user_id=current_user.id).all()
        return [{
            'provider_id': t.provider_id,
            'external_user_id': t.external_user_id,
            'created_at': t.created_at.isoformat() if t.created_at else None,
        } for t in tokens]

    return _linked_accounts()


@oauth_bp.route('/unlink/<provider_id>', methods=['POST'])
def unlink(provider_id):
    """Unlink an OAuth provider from the current user.

    Args:
        provider_id: Provider identifier to unlink
    """
    from flask_login import login_required, current_user
    from app.models import OAuthToken

    @login_required
    def _unlink():
        token = OAuthToken.query.filter_by(
            user_id=current_user.id,
            provider_id=provider_id,
        ).first()

        if not token:
            flash(f'Provider "{provider_id}" not linked', 'warning')
        else:
            db.session.delete(token)
            db.session.commit()
            flash(f'Unlinked {provider_id}', 'success')

        return redirect(url_for('auth.profile'))

    return _unlink()

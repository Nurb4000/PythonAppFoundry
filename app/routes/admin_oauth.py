"""Admin routes for OAuth provider management."""
from flask import Blueprint, request, redirect, url_for, flash, jsonify
from app.services.admin_utils import admin_required, render_admin
from app import db
from app.models import OAuthProvider, OAuthToken
from app.services.oauth import setup_builtin_providers

oauth_admin_bp = Blueprint('oauth_admin', __name__)


@oauth_admin_bp.route('/')
@admin_required
def list_providers():
    """List all OAuth providers with their configuration status."""
    # Ensure built-in providers exist
    setup_builtin_providers()

    providers = OAuthProvider.query.order_by(OAuthProvider.provider_id).all()
    return render_admin('OAuth Providers', 'admin/oauth/list.html', providers=providers)


@oauth_admin_bp.route('/<provider_id>/configure', methods=['GET', 'POST'])
@admin_required
def configure_provider(provider_id):
    """Configure an OAuth provider (client_id, client_secret, enable/disable)."""
    provider = OAuthProvider.query.filter_by(provider_id=provider_id).first()
    if not provider:
        flash(f'Provider "{provider_id}" not found', 'error')
        return redirect(url_for('admin.oauth_admin.list_providers'))

    if request.method == 'POST':
        provider.client_id = request.form.get('client_id', '').strip()
        provider.client_secret = request.form.get('client_secret', '').strip()
        provider.enabled = 'enabled' in request.form
        provider.scopes = request.form.get('scopes', provider.scopes).strip()

        # Validate required fields if enabled
        if provider.enabled and not (provider.client_id and provider.client_secret):
            flash('Client ID and Client Secret are required when enabled', 'error')
        else:
            db.session.commit()
            status = 'enabled' if provider.enabled else 'disabled'
            flash(f'Provider "{provider.display_name}" {status}', 'success')
            return redirect(url_for('admin.oauth_admin.list_providers'))

    return render_admin(f'Configure {provider.display_name}', 'admin/oauth/configure.html',
                        provider=provider)


@oauth_admin_bp.route('/linked-accounts')
@admin_required
def linked_accounts():
    """List all users with linked OAuth accounts."""
    tokens = OAuthToken.query.order_by(OAuthToken.created_at.desc()).all()

    return render_admin('Linked Accounts', 'admin/oauth/linked.html', tokens=tokens)


@oauth_admin_bp.route('/<token_id>/unlink', methods=['POST'])
@admin_required
def unlink_account(token_id):
    """Unlink an OAuth account from a user."""
    token = db.session.get(OAuthToken, token_id)
    if not token:
        flash('OAuth token not found', 'error')
        return redirect(url_for('admin.oauth_admin.linked_accounts'))

    provider_name = token.provider_id
    db.session.delete(token)
    db.session.commit()
    flash(f'Unlinked {provider_name} account', 'success')
    return redirect(url_for('admin.oauth_admin.linked_accounts'))


@oauth_admin_bp.route('/status')
def status():
    """API endpoint to check OAuth provider status.

    Returns JSON list of enabled providers for the login page.
    """
    from flask import jsonify
    providers = OAuthProvider.query.filter_by(enabled=True).all()
    return jsonify([{
        'provider_id': p.provider_id,
        'display_name': p.display_name,
        'authorize_url': p.authorize_url,
    } for p in providers])

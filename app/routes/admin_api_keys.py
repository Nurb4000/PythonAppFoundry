"""Admin routes for API key management."""
from flask import Blueprint, request, redirect, url_for, flash, jsonify
from flask_login import current_user
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required, render_admin
from app.services.api_key import (
    create_api_key, validate_api_key, revoke_api_key,
    rotate_api_key, list_api_keys, get_api_key,
)
from app.models import ApiKey, Module
from app.services.audit import log_audit
from app import db

api_keys_bp = Blueprint('api_keys', __name__)


@api_keys_bp.route('/')
@admin_required
def list_keys():
    """List all API keys."""
    module_id = request.args.get('module_id', type=int)
    keys = list_api_keys(module_id=module_id)
    modules = db.session.query(Module).order_by(Module.name).all() if module_id is None else []
    return render_admin('API Keys', 'admin/api_keys/list.html',
                        keys=keys, modules=modules, selected_module_id=module_id)


@api_keys_bp.route('/new', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def new_key():
    """Create a new API key."""
    modules = db.session.query(Module).order_by(Module.name).all()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Name is required', 'error')
            return render_admin('New API Key', 'admin/api_keys/new.html', modules=modules)

        module_id = request.form.get('module_id', type=int) or None
        expires_in_days = request.form.get('expires_in_days', type=int)

        try:
            key, plaintext_token = create_api_key(
                name=name,
                user_id=current_user.id,
                module_id=module_id,
                expires_in_days=expires_in_days,
            )
            log_audit('create', 'api_key', key.id, name)
            flash(f'API key created. Save this token: {plaintext_token}', 'success')
            return redirect(url_for('admin.api_keys.list_keys'))
        except Exception as e:
            flash(f'Error creating API key: {e}', 'error')

    return render_admin('New API Key', 'admin/api_keys/new.html', modules=modules)


@api_keys_bp.route('/<int:key_id>/revoke', methods=['POST'])
@admin_required
@csrf_protect
def revoke_key(key_id):
    """Revoke an API key."""
    key = get_api_key(key_id)
    if not key:
        flash('API key not found', 'error')
        return redirect(url_for('admin.api_keys.list_keys'))

    name = key.name
    if revoke_api_key(key_id):
        log_audit('revoke', 'api_key', key_id, name)
        flash(f'API key "{name}" revoked', 'info')
    else:
        flash(f'API key "{name}" was already inactive', 'warning')

    return redirect(url_for('admin.api_keys.list_keys'))


@api_keys_bp.route('/<int:key_id>/rotate', methods=['POST'])
@admin_required
@csrf_protect
def rotate_key(key_id):
    """Rotate an API key (generate new token)."""
    result = rotate_api_key(key_id)
    if result:
        key, plaintext_token = result
        log_audit('rotate', 'api_key', key_id, key.name)
        flash(f'API key rotated. New token: {plaintext_token}', 'success')
    else:
        flash('API key not found', 'error')

    return redirect(url_for('admin.api_keys.list_keys'))


@api_keys_bp.route('/<int:key_id>/delete', methods=['POST'])
@admin_required
@csrf_protect
def delete_key(key_id):
    """Delete an API key."""
    key = get_api_key(key_id)
    if not key:
        flash('API key not found', 'error')
        return redirect(url_for('admin.api_keys.list_keys'))

    name = key.name
    db.session.delete(key)
    db.session.commit()
    log_audit('delete', 'api_key', key_id, name)
    flash(f'API key "{name}" deleted', 'info')
    return redirect(url_for('admin.api_keys.list_keys'))


@api_keys_bp.route('/validate', methods=['POST'])
@admin_required
@csrf_protect
def validate_key():
    """Validate an API key token (for testing)."""
    data = request.get_json(silent=True) or {}
    token = data.get('token', '').strip()
    if not token:
        return jsonify({'valid': False, 'error': 'Token required'}), 400

    key = validate_api_key(token)
    if key:
        return jsonify({
            'valid': True,
            'name': key.name,
            'user_id': key.user_id,
            'module_id': key.module_id,
            'is_active': key.is_active,
            'expires_at': key.expires_at.isoformat() if key.expires_at else None,
            'last_used_at': key.last_used_at.isoformat() if key.last_used_at else None,
            'request_count': key.request_count,
        })
    return jsonify({'valid': False, 'error': 'Invalid or expired token'}), 401

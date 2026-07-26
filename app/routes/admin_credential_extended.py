"""Admin routes for extended credential management."""
from flask import Blueprint, request, redirect, url_for, render_template_string

credential_extended_bp = Blueprint('credential_extended', __name__)


@credential_extended_bp.route('/credentials/<int:id>/test')
@admin_required
def test_credential(id):
    """Test a credential by retrieving it."""
    from app.models import Credential
    from app.services.credential_store import decrypt_value
    
    credential = db.session.get(Credential, id)
    if not credential:
        flash('Credential not found', 'error')
        return redirect(url_for('admin.list_credentials'))
    
    try:
        value = decrypt_value(credential.value_encrypted)
        # Mask the value for display
        if len(value) > 8:
            masked = value[:4] + '*' * (len(value) - 8) + value[-4:]
        else:
            masked = '***'
        flash(f'Credential "{credential.name}" retrieved successfully. Value: {masked}')
    except Exception as e:
        flash(f'Failed to retrieve credential: {e}', 'error')
    
    return redirect(url_for('admin.list_credentials'))


@credential_extended_bp.route('/credentials/bulk-delete', methods=['POST'])
@admin_required
@csrf_protect
def bulk_delete_credentials():
    """Delete multiple credentials at once."""
    from app.models import Credential
    
    credential_ids = request.form.getlist('credential_ids')
    deleted = 0
    for cid in credential_ids:
        credential = db.session.get(Credential, int(cid))
        if credential:
            db.session.delete(credential)
            deleted += 1
    
    db.session.commit()
    flash(f'Deleted {deleted} credential(s)')
    return redirect(url_for('admin.list_credentials'))

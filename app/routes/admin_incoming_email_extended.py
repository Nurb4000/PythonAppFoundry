"""Admin routes for extended incoming email management."""
from flask import Blueprint, request, redirect, url_for, render_template_string

incoming_email_extended_bp = Blueprint('incoming_email_extended', __name__)


@incoming_email_extended_bp.route('/incoming-emails/<int:id>/claim', methods=['POST'])
@admin_required
@csrf_protect
def claim_email(id):
    """Claim an incoming email for a module."""
    from app.models import IncomingEmail, Module
    
    email = db.session.get(IncomingEmail, id)
    if not email:
        flash('Email not found', 'error')
        return redirect(url_for('admin.list_incoming_emails'))
    
    module_slug = request.form.get('module_slug', '')
    if not module_slug:
        flash('Module slug required', 'error')
        return redirect(url_for('admin.list_incoming_emails'))
    
    module = db.session.query(Module).filter_by(slug=module_slug).first()
    if not module:
        flash(f'Module "{module_slug}" not found', 'error')
        return redirect(url_for('admin.list_incoming_emails'))
    
    email.module_slug = module_slug
    email.processed = True
    from datetime import datetime, timezone
    email.processed_at = datetime.now(timezone.utc)
    db.session.commit()
    flash(f'Email claimed by {module.name}')
    return redirect(url_for('admin.view_incoming_email', id=id))


@incoming_email_extended_bp.route('/incoming-emails/bulk-process', methods=['POST'])
@admin_required
@csrf_protect
def bulk_process_emails():
    """Mark multiple emails as processed."""
    from app.models import IncomingEmail
    
    email_ids = request.form.getlist('email_ids')
    processed = 0
    for eid in email_ids:
        email = db.session.get(IncomingEmail, int(eid))
        if email and not email.processed:
            email.processed = True
            from datetime import datetime, timezone
            email.processed_at = datetime.now(timezone.utc)
            processed += 1
    
    db.session.commit()
    flash(f'Processed {processed} email(s)')
    return redirect(url_for('admin.list_incoming_emails'))


@incoming_email_extended_bp.route('/incoming-emails/bulk-delete', methods=['POST'])
@admin_required
@csrf_protect
def bulk_delete_emails():
    """Delete multiple emails at once."""
    from app.models import IncomingEmail
    
    email_ids = request.form.getlist('email_ids')
    deleted = 0
    for eid in email_ids:
        email = db.session.get(IncomingEmail, int(eid))
        if email:
            db.session.delete(email)
            deleted += 1
    
    db.session.commit()
    flash(f'Deleted {deleted} email(s)')
    return redirect(url_for('admin.list_incoming_emails'))

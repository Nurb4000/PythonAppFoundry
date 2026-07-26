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


@incoming_email_extended_bp.route('/incoming-emails/stats')
@admin_required
def email_stats():
    """View incoming email statistics."""
    from app.models import IncomingEmail
    
    total = db.session.query(IncomingEmail).count()
    processed = db.session.query(IncomingEmail).filter_by(processed=True).count()
    pending = total - processed
    
    # Group by module
    module_stats = db.session.query(IncomingEmail.module_slug, db.func.count(IncomingEmail.id)).group_by(IncomingEmail.module_slug).all()
    
    return render_admin('Incoming Email Statistics', '''
<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
  <div class="dash-card">
    <h3>Overview</h3>
    <ul style="margin:0;padding-left:1.5rem;line-height:1.8;">
      <li><strong>Total Emails:</strong> {{ total }}</li>
      <li><strong>Processed:</strong> {{ processed }}</li>
      <li><strong>Pending:</strong> {{ pending }}</li>
    </ul>
  </div>
  
  <div class="dash-card">
    <h3>By Module</h3>
    {% if module_stats %}
    <table style="width:100%;">
    <thead><tr><th>Module</th><th>Count</th></tr></thead>
    <tbody>
    {% for module_slug, count in module_stats %}
    <tr>
      <td>{{ module_slug or 'Unclaimed' }}</td>
      <td>{{ count }}</td>
    </tr>
    {% endfor %}
    </tbody></table>
    {% else %}
    <p style="color:#888;">No emails received yet.</p>
    {% endif %}
  </div>
</div>
''', total=total, processed=processed, pending=pending, module_stats=module_stats)

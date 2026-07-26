"""Admin routes for notification management."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash

notifications_bp = Blueprint('notifications', __name__)


@notifications_bp.route('/notifications')
@admin_required
def list_notifications():
    """View system notifications and alerts."""
    from app.models import Setting
    
    notifications = []
    
    # Check for pending user approvals
    pending_count = db.session.query(db.func.count(User.id)).filter_by(is_approved=False).scalar()
    if pending_count > 0:
        notifications.append({
            'type': 'info',
            'message': f'{pending_count} user(s) pending approval.',
            'action': url_for('admin.list_users'),
        })
    
    # Check for failed webhook executions
    from app.services.triggers import get_dead_letter_queue
    dead_letter = get_dead_letter_queue()
    if dead_letter:
        notifications.append({
            'type': 'warning',
            'message': f'{len(dead_letter)} webhook execution(s) in dead letter queue.',
            'action': url_for('admin.list_dead_letter'),
        })
    
    # Check for old execution logs
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=30)
    old_logs = db.session.query(db.func.count(ExecutionLog.id)).filter(
        ExecutionLog.created_at < cutoff
    ).scalar()
    if old_logs > 1000:
        notifications.append({
            'type': 'info',
            'message': f'{old_logs} execution logs older than 30 days. Consider adjusting log retention.',
            'action': url_for('admin.edit_settings'),
        })
    
    # Check for missing LLM configuration
    llm_provider = Setting.get('llm_provider', '')
    if llm_provider and not Setting.get('llm_endpoint', ''):
        notifications.append({
            'type': 'warning',
            'message': f'LLM provider "{llm_provider}" configured but endpoint not set.',
            'action': url_for('admin.edit_settings'),
        })
    
    return render_admin('Notifications', '''
{% if notifications %}
<div style="display:flex;flex-direction:column;gap:0.75rem;">
  {% for notif in notifications %}
  <div style="background:{% if notif.type == 'error' %}#f8d7da{% elif notif.type == 'warning' %}#fff3cd{% else %}#d1ecf1{% endif %};border:1px solid {% if notif.type == 'error' %}#f5c6cb{% elif notif.type == 'warning' %}#ffeaa7{% else %}#bee5eb{% endif %};padding:1rem;border-radius:4px;">
    <p style="margin:0 0 0.5rem 0;">{{ notif.message }}</p>
    <a href="{{ notif.action }}" style="font-size:0.85em;">View details &rarr;</a>
  </div>
  {% endfor %}
</div>
{% else %}
<p style="color:#888;">No notifications.</p>
{% endif %}''', notifications=notifications)

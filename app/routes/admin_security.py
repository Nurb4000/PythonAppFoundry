"""Admin routes for security monitoring."""
from flask import Blueprint, request, redirect, url_for, render_template_string

security_bp = Blueprint('security', __name__)


@security_bp.route('/security')
@admin_required
def security_dashboard():
    """View security-related information and recent activity."""
    from app.models import User, ExecutionLog
    from datetime import datetime, timedelta
    
    # Recent failed login attempts (last 24 hours)
    cutoff = datetime.now() - timedelta(hours=24)
    recent_logs = db.session.query(ExecutionLog).filter(
        ExecutionLog.created_at > cutoff
    ).order_by(ExecutionLog.created_at.desc()).limit(50).all()
    
    # Active users
    active_users = db.session.query(User).filter_by(is_active=True, is_approved=True).count()
    pending_users = db.session.query(User).filter_by(is_approved=False).count()
    
    return render_admin('Security Dashboard', '''
<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1.5rem;">
  <div class="dash-card">
    <h3>Active Users</h3>
    <div class="value">{{ active_users }}</div>
  </div>
  <div class="dash-card">
    <h3>Pending Approval</h3>
    <div class="value" style="color:{% if pending_users > 0 %}#856404{% else %}#080{% endif %};">{{ pending_users }}</div>
  </div>
</div>

<h2>Recent Activity (Last 24 Hours)</h2>
{% if recent_logs %}
<div class="table-wrap">
<table>
<thead><tr>
  <th>Time</th>
  <th>Type</th>
  <th>Name</th>
  <th>Status</th>
  <th>Duration</th>
</tr></thead>
<tbody>
{% for log in recent_logs %}
<tr>
  <td style="white-space:nowrap;font-size:0.85em;">{{ log.created_at.strftime('%Y-%m-%d %H:%M:%S') }}</td>
  <td>{{ log.source_type }}</td>
  <td>{{ log.source_name }}</td>
  <td><span class="{% if log.status == 'success' %}status-ok{% else %}status-err{% endif %}">{{ log.status|upper }}</span></td>
  <td>{{ log.duration_ms }}ms</td>
</tr>
{% endfor %}
</tbody></table>
</div>
{% else %}
<p style="color:#888;">No activity in the last 24 hours.</p>
{% endif %}''', recent_logs=recent_logs, active_users=active_users, pending_users=pending_users)

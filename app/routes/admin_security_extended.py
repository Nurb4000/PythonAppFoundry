"""Admin routes for extended security monitoring."""
from flask import Blueprint, request, redirect, url_for, render_template_string

security_extended_bp = Blueprint('security_extended', __name__)


@security_extended_bp.route('/security/audit-log')
@admin_required
def audit_log():
    """View detailed audit log of administrative actions."""
    from app.models import ExecutionLog
    
    logs = db.session.query(ExecutionLog).order_by(ExecutionLog.created_at.desc()).limit(100).all()
    
    return render_admin('Audit Log', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.security_dashboard') }}">Back to Security</a>
</div>
{% if logs %}
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
{% for log in logs %}
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
<p style="color:#888;">No audit logs found.</p>
{% endif %}''', logs=logs)


@security_extended_bp.route('/security/ip-logs')
@admin_required
def ip_logs():
    """View IP address logs for security monitoring."""
    # This would typically track IP addresses associated with requests
    # For now, show a placeholder
    return render_admin('IP Logs', '''
<p style="color:#666;">IP logging is not yet implemented. This feature will track IP addresses associated with administrative actions for security auditing.</p>
''')


@security_extended_bp.route('/security/session-logs')
@admin_required
def session_logs():
    """View session logs for security monitoring."""
    # This would typically track user sessions
    # For now, show a placeholder
    return render_admin('Session Logs', '''
<p style="color:#666;">Session logging is not yet implemented. This feature will track user sessions for security auditing.</p>
''')

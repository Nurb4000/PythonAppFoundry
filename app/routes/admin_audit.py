"""Admin routes for audit logging."""
from flask import Blueprint, request, redirect, url_for, render_template_string

audit_bp = Blueprint('audit', __name__)


@audit_bp.route('/audit')
@admin_required
def audit_log():
    """View audit log of administrative actions."""
    from app.models import ExecutionLog
    
    logs = db.session.query(ExecutionLog).order_by(ExecutionLog.created_at.desc()).limit(100).all()
    
    return render_admin('Audit Log', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.list_modules') }}">Back to Modules</a>
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

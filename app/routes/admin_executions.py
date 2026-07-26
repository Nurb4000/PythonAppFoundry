"""Admin routes for per-module execution history."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash
from app.services.admin_utils import developer_or_admin_required
from app import db
from app.models import Module, Script, ExecutionLog

executions_bp = Blueprint('executions', __name__)


@executions_bp.route('/modules/<int:module_id>/executions')
@developer_or_admin_required
def module_executions(module_id):
    """Show recent execution logs for a specific module."""
    module = db.session.get(Module, module_id)
    if not module:
        flash('Module not found', 'error')
        return redirect(url_for('admin.list_modules'))
    
    # Get scripts in this module
    scripts = db.session.query(Script).filter_by(module_id=module_id).all()
    script_names = [s.name for s in scripts]
    
    # Get recent executions for these scripts
    limit = request.args.get('limit', 50, type=int)
    logs = db.session.query(ExecutionLog).filter(
        ExecutionLog.source_name.in_(script_names),
        ExecutionLog.source_type == 'script'
    ).order_by(ExecutionLog.created_at.desc()).limit(limit).all()
    
    return render_admin(f'Executions: {module.name}', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.edit_module', id=m.id) }}">Back to Module</a>
  <form method="GET" style="display:inline;">
    <input type="hidden" name="limit" value="{{ limit }}">
    <select name="status" onchange="this.form.submit()" style="padding:4px 8px;">
      <option value="">All Statuses</option>
      <option value="success" {% if status_filter == 'success' %}selected{% endif %}>Success</option>
      <option value="error" {% if status_filter == 'error' %}selected{% endif %}>Error</option>
    </select>
  </form>
</div>
{% if logs %}
<div class="table-wrap">
<table>
<thead><tr>
  <th>Time</th>
  <th>Script</th>
  <th>Status</th>
  <th>Duration</th>
  <th>Details</th>
</tr></thead>
<tbody>
{% for log in logs %}
<tr>
  <td style="white-space:nowrap;font-size:0.85em;">{{ log.created_at.strftime('%Y-%m-%d %H:%M:%S') }}</td>
  <td><strong>{{ log.source_name }}</strong></td>
  <td><span class="{% if log.status == 'success' %}status-ok{% else %}status-err{% endif %}">{{ log.status|upper }}</span></td>
  <td>{{ log.duration_ms }}ms</td>
  <td>
    {% if log.error_message %}
      <span style="color:#c00;font-size:0.85em;">{{ log.error_message[:100] }}...</span>
    {% elif log.stdout %}
      <span style="color:#888;font-size:0.85em;">{{ log.stdout[:100] }}...</span>
    {% else %}
      <span style="color:#999;font-size:0.85em;">—</span>
    {% endif %}
  </td>
</tr>
{% endfor %}
</tbody></table>
</div>
{% else %}
<p style="color:#888;">No executions found for this module.</p>
{% endif %}''', m=module, logs=logs, limit=limit, status_filter='')

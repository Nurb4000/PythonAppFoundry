"""Admin routes for integration health monitoring."""
from flask import Blueprint, request, redirect, url_for, render_template_string
from app.services.admin_utils import admin_required
from app import db
from app.models import ExecutionLog, Script, Module

integration_health_bp = Blueprint('integration_health', __name__)


@integration_health_bp.route('/integration-health')
@admin_required
def integration_health():
    limit = request.args.get('limit', 100, type=int)
    module_id = request.args.get('module_id', type=int)

    logs_q = db.session.query(ExecutionLog).filter(
        ExecutionLog.source_type.in_(['script', 'task'])
    )

    if module_id:
        script_names = [
            s.name for s in db.session.query(Script.name).filter(Script.module_id == module_id)
        ]
        if script_names:
            logs_q = logs_q.filter(ExecutionLog.source_name.in_(script_names))

    logs_q = logs_q.order_by(ExecutionLog.created_at.desc()).limit(limit)
    logs = logs_q.all()

    total_runs = len(logs)
    errors = [l for l in logs if l.status == 'error']
    error_rate = round(len(errors) / total_runs * 100, 1) if total_runs else 0
    avg_duration = sum(l.duration_ms for l in logs) / total_runs if total_runs else 0

    modules = db.session.query(Module).order_by(Module.name).all()

    return render_admin('Integration Health', '''
<div style="display:flex;gap:1rem;margin-bottom:1rem;flex-wrap:wrap;">
  <div class="dash-card" style="flex:1;min-width:120px;"><h3>Recent Runs</h3><div class="value">{{ total_runs }}</div></div>
  <div class="dash-card" style="flex:1;min-width:120px;"><h3>Errors</h3><div class="value" style="color:{% if errors %} #c00{% else %}#080{% endif %};">{{ errors|length }}</div><div class="sub">{{ error_rate }}% error rate</div></div>
  <div class="dash-card" style="flex:1;min-width:120px;"><h3>Avg Duration</h3><div class="value">{{ '%d'|format(avg_duration) }}ms</div></div>
</div>
<form method="GET" style="margin-bottom:1rem;display:flex;gap:8px;align-items:center;">
  <select name="module_id" onchange="this.form.submit()" style="padding:4px 8px;">
    <option value="">All Modules</option>
    {% for m in modules %}
    <option value="{{ m.id }}" {% if module_id == m.id %}selected{% endif %}>{{ m.name }}</option>
    {% endfor %}
  </select>
  <input name="limit" type="hidden" value="{{ limit }}">
  <noscript><button type="submit">Filter</button></noscript>
  {% if module_id %}<a href="{{ url_for('admin.integration_health') }}" style="color:#007bff;">Clear</a>{% endif %}
</form>
<div class="table-wrap">
<table>
<thead><tr>
  <th>Time</th><th>Script / Task</th><th>Status</th><th>Duration</th><th>Detail</th>
</tr></thead>
<tbody>
{% for log in logs %}
<tr>
  <td style="white-space:nowrap;font-size:0.85em;">{{ log.created_at|localtime }}</td>
  <td><strong>{{ log.source_name }}</strong><br><span style="font-size:0.8em;color:#888;">{{ log.source_type }}</span></td>
  <td><span class="{% if log.status == 'success' %}status-ok{% else %}status-err{% endif %}">{{ log.status|upper }}</span></td>
  <td>{{ log.duration_ms }}ms</td>
  <td>
    {% if log.error_message %}
    <button onclick="showLogDetail({{ log.id }}, this.nextElementSibling)" style="font-size:0.8em;padding:2px 8px;cursor:pointer;background:#fee;border:1px solid #c00;color:#c00;border-radius:3px;">View Error</button>
    <span style="display:none;">{{ log.error_message[:2000] }}</span>
    {% elif log.stdout %}
    <span style="color:#888;font-size:0.85em;">{{ log.stdout[:200] }}</span>
    {% else %}<span style="color:#999;font-size:0.85em;">—</span>{% endif %}
  </td>
</tr>
{% endfor %}
</tbody></table>
</div>
{% if not logs %}<p style="color:#888;">No script or task execution logs yet. Run a script to see results here.</p>{% endif %}
''', logs=logs, total_runs=total_runs, errors=errors, error_rate=error_rate,
        avg_duration=avg_duration, modules=modules, module_id=module_id, limit=limit)

"""Admin routes for extended webhook management."""
from flask import Blueprint, request, redirect, url_for, render_template_string

webhook_extended_bp = Blueprint('webhook_extended', __name__)


@webhook_extended_bp.route('/webhooks/<int:id>/test', methods=['POST'])
@admin_required
@csrf_protect
def test_webhook(id):
    """Test a webhook by sending a sample payload."""
    from app.models import Trigger
    from app.services.triggers import fire_webhook
    
    trigger = db.session.get(Trigger, id)
    if not trigger:
        flash('Trigger not found', 'error')
        return redirect(url_for('admin.list_triggers'))
    
    if trigger.event_type != 'webhook':
        flash('This is not a webhook trigger', 'error')
        return redirect(url_for('admin.list_triggers'))
    
    try:
        fire_webhook(trigger.target_table, {'test': True, 'timestamp': '2026-07-25T00:00:00Z'})
        flash(f'Webhook "{trigger.name}" tested successfully')
    except Exception as e:
        flash(f'Webhook test failed: {e}', 'error')
    
    return redirect(url_for('admin.list_triggers'))


@webhook_extended_bp.route('/webhooks/<int:id>/logs')
@admin_required
def webhook_logs(id):
    """View execution logs for a webhook trigger."""
    from app.models import Trigger, ExecutionLog
    
    trigger = db.session.get(Trigger, id)
    if not trigger:
        flash('Trigger not found', 'error')
        return redirect(url_for('admin.list_triggers'))
    
    logs = db.session.query(ExecutionLog).filter(
        ExecutionLog.source_name == trigger.name,
        ExecutionLog.source_type == 'webhook'
    ).order_by(ExecutionLog.created_at.desc()).limit(50).all()
    
    return render_admin(f'Webhook Logs: {trigger.name}', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.list_triggers') }}">Back to Triggers</a>
</div>
{% if logs %}
<div class="table-wrap">
<table>
<thead><tr>
  <th>Time</th>
  <th>Status</th>
  <th>Duration</th>
  <th>Details</th>
</tr></thead>
<tbody>
{% for log in logs %}
<tr>
  <td style="white-space:nowrap;font-size:0.85em;">{{ log.created_at.strftime('%Y-%m-%d %H:%M:%S') }}</td>
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
<p style="color:#888;">No execution logs for this webhook.</p>
{% endif %}''', trigger=trigger, logs=logs)


@webhook_extended_bp.route('/webhooks/stats')
@admin_required
def webhook_stats():
    """View webhook statistics."""
    from app.models import Trigger, ExecutionLog
    
    total_webhooks = db.session.query(Trigger).filter_by(event_type='webhook').count()
    active_webhooks = db.session.query(Trigger).filter_by(event_type='webhook', enabled=True).count()
    
    # Get recent webhook executions
    recent_logs = db.session.query(ExecutionLog).filter(
        ExecutionLog.source_type == 'webhook'
    ).order_by(ExecutionLog.created_at.desc()).limit(10).all()
    
    success_count = db.session.query(ExecutionLog).filter(
        ExecutionLog.source_type == 'webhook',
        ExecutionLog.status == 'success'
    ).count()
    
    error_count = db.session.query(ExecutionLog).filter(
        ExecutionLog.source_type == 'webhook',
        ExecutionLog.status == 'error'
    ).count()
    
    return render_admin('Webhook Statistics', '''
<div style="display:grid;grid-template-columns:repeat(3, 1fr);gap:1rem;margin-bottom:1.5rem;">
  <div class="dash-card">
    <h3>Total Webhooks</h3>
    <div class="value">{{ total_webhooks }}</div>
  </div>
  <div class="dash-card">
    <h3>Active Webhooks</h3>
    <div class="value" style="color:{% if active_webhooks > 0 %}#080{% else %}#c00{% endif %};">{{ active_webhooks }}</div>
  </div>
  <div class="dash-card">
    <h3>Success Rate</h3>
    <div class="value">{{ '%.1f'|format(success_count / (success_count + error_count) * 100) if (success_count + error_count) > 0 else 'N/A' }}%</div>
  </div>
</div>

<h3>Recent Executions</h3>
{% if recent_logs %}
<div class="table-wrap">
<table>
<thead><tr>
  <th>Time</th>
  <th>Webhook</th>
  <th>Status</th>
  <th>Duration</th>
</tr></thead>
<tbody>
{% for log in recent_logs %}
<tr>
  <td style="white-space:nowrap;font-size:0.85em;">{{ log.created_at.strftime('%Y-%m-%d %H:%M:%S') }}</td>
  <td>{{ log.source_name }}</td>
  <td><span class="{% if log.status == 'success' %}status-ok{% else %}status-err{% endif %}">{{ log.status|upper }}</span></td>
  <td>{{ log.duration_ms }}ms</td>
</tr>
{% endfor %}
</tbody></table>
</div>
{% else %}
<p style="color:#888;">No recent webhook executions.</p>
{% endif %}
''', total_webhooks=total_webhooks, active_webhooks=active_webhooks, success_count=success_count, error_count=error_count, recent_logs=recent_logs)

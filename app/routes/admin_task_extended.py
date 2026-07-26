"""Admin routes for extended task management."""
from flask import Blueprint, request, redirect, url_for, render_template_string

task_extended_bp = Blueprint('task_extended', __name__)


@task_extended_bp.route('/tasks/run-now/<int:id>')
@admin_required
def run_task_now(id):
    """Manually run a scheduled task."""
    from app.models import ScheduledTask
    from app.services.scheduler import run_task_wrapper
    
    task = db.session.get(ScheduledTask, id)
    if not task:
        flash('Task not found', 'error')
        return redirect(url_for('admin.list_tasks'))
    
    try:
        run_task_wrapper(task.id)
        flash(f'Task "{task.name}" triggered manually')
    except Exception as e:
        flash(f'Failed to run task: {e}', 'error')
    
    return redirect(url_for('admin.list_tasks'))


@task_extended_bp.route('/tasks/log/<int:id>')
@admin_required
def task_log(id):
    """View execution log for a specific task."""
    from app.models import ScheduledTask, ExecutionLog
    
    task = db.session.get(ScheduledTask, id)
    if not task:
        flash('Task not found', 'error')
        return redirect(url_for('admin.list_tasks'))
    
    logs = db.session.query(ExecutionLog).filter(
        ExecutionLog.source_name == task.name,
        ExecutionLog.source_type == 'task'
    ).order_by(ExecutionLog.created_at.desc()).limit(50).all()
    
    return render_admin(f'Task Log: {task.name}', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.list_tasks') }}">Back to Tasks</a>
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
<p style="color:#888;">No execution logs for this task.</p>
{% endif %}''', task=task, logs=logs)

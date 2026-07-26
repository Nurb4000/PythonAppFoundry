"""Admin routes for dead letter queue management."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash

dead_letter_bp = Blueprint('dead_letter', __name__)


@dead_letter_bp.route('/dead-letter')
@admin_required
def list_dead_letter():
    """View the dead letter queue for failed webhook executions."""
    from app.services.triggers import get_dead_letter_queue
    queue = get_dead_letter_queue()
    
    return render_admin('Dead Letter Queue', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.list_modules') }}">Back to Modules</a>
  {% if queue %}
  <form method="POST" action="{{ url_for('admin.clear_dead_letter') }}" style="display:inline;margin-left:auto;">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <button type="submit" style="padding:6px 16px;background:#dc3545;color:#fff;border:none;border-radius:4px;cursor:pointer;">Clear Queue</button>
  </form>
  {% endif %}
</div>
{% if queue %}
<div class="table-wrap">
<table>
<thead><tr>
  <th>Time</th>
  <th>Trigger</th>
  <th>Webhook</th>
  <th>Error</th>
  <th>Actions</th>
</tr></thead>
<tbody>
{% for entry in queue %}
<tr>
  <td style="white-space:nowrap;font-size:0.85em;">{{ entry.timestamp }}</td>
  <td>{{ entry.trigger_name }}</td>
  <td><code>{{ entry.target }}</code></td>
  <td style="max-width:400px;overflow:hidden;text-overflow:ellipsis;">{{ entry.error[:200] }}...</td>
  <td>
    <form method="POST" action="{{ url_for('admin.retry_dead_letter', index=loop.index0) }}" style="display:inline">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <button type="submit" style="background:none;border:none;color:#2563eb;cursor:pointer;text-decoration:underline;padding:0;font:inherit;font-size:0.85em;">Retry</button>
    </form>
  </td>
</tr>
{% endfor %}
</tbody></table>
</div>
{% else %}
<p style="color:#888;">Dead letter queue is empty.</p>
{% endif %}''', queue=queue)


@dead_letter_bp.route('/dead-letter/clear', methods=['POST'])
@admin_required
@csrf_protect
def clear_dead_letter():
    """Clear the dead letter queue."""
    from app.services.triggers import clear_dead_letter_queue
    clear_dead_letter_queue()
    flash('Dead letter queue cleared')
    return redirect(url_for('admin.list_dead_letter'))


@dead_letter_bp.route('/dead-letter/retry/<int:index>', methods=['POST'])
@admin_required
@csrf_protect
def retry_dead_letter(index):
    """Retry a specific dead letter entry."""
    from app.services.triggers import retry_dead_letter as _retry
    if _retry(index):
        flash(f'Dead letter #{index} queued for retry')
    else:
        flash('Failed to queue retry', 'error')
    return redirect(url_for('admin.list_dead_letter'))

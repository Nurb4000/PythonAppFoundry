"""Admin routes for performance monitoring."""
from flask import Blueprint, request, redirect, url_for, render_template_string

performance_bp = Blueprint('performance', __name__)


@performance_bp.route('/performance')
@admin_required
def performance_dashboard():
    """View performance metrics and optimization suggestions."""
    from app.models import ExecutionLog
    from datetime import datetime, timedelta
    
    # Calculate performance metrics
    cutoff = datetime.now() - timedelta(hours=24)
    recent_logs = db.session.query(ExecutionLog).filter(
        ExecutionLog.created_at > cutoff
    ).all()
    
    total_runs = len(recent_logs)
    avg_duration = sum(l.duration_ms for l in recent_logs) / total_runs if total_runs else 0
    max_duration = max((l.duration_ms for l in recent_logs), default=0)
    error_count = sum(1 for l in recent_logs if l.status == 'error')
    error_rate = (error_count / total_runs * 100) if total_runs else 0
    
    # Find slow scripts
    slow_scripts = {}
    for log in recent_logs:
        if log.duration_ms > 1000:  # More than 1 second
            slow_scripts[log.source_name] = slow_scripts.get(log.source_name, 0) + 1
    
    return render_admin('Performance Dashboard', '''
<div style="display:grid;grid-template-columns:repeat(4, 1fr);gap:1rem;margin-bottom:1.5rem;">
  <div class="dash-card">
    <h3>Total Runs (24h)</h3>
    <div class="value">{{ total_runs }}</div>
  </div>
  <div class="dash-card">
    <h3>Avg Duration</h3>
    <div class="value">{{ '%.1f'|format(avg_duration) }}ms</div>
  </div>
  <div class="dash-card">
    <h3>Max Duration</h3>
    <div class="value">{{ max_duration }}ms</div>
  </div>
  <div class="dash-card">
    <h3>Error Rate</h3>
    <div class="value" style="color:{% if error_rate > 10 %}#c00{% elif error_rate > 5 %}#856404{% else %}#080{% endif %};">{{ '%.1f'|format(error_rate) }}%</div>
  </div>
</div>

{% if slow_scripts %}
<h3>Slow Scripts (>1s)</h3>
<div class="table-wrap">
<table>
<thead><tr>
  <th>Script</th>
  <th>Occurrences</th>
</tr></thead>
<tbody>
{% for script, count in slow_scripts.items()|sort(reverse=True) %}
<tr>
  <td><code>{{ script }}</code></td>
  <td>{{ count }}</td>
</tr>
{% endfor %}
</tbody></table>
</div>
{% endif %}
''', total_runs=total_runs, avg_duration=avg_duration, max_duration=max_duration, error_rate=error_rate, slow_scripts=slow_scripts)

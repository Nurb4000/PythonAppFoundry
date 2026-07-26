"""Admin routes for structured log viewing."""
from flask import Blueprint, request, redirect, url_for, render_template_string

structured_logs_bp = Blueprint('structured_logs', __name__)


@structured_logs_bp.route('/logs')
@admin_required
def view_logs():
    """View structured application logs."""
    log_dir = current_app.instance_path / 'logs' if hasattr(current_app.instance_path, '__truediv__') else None
    if not log_dir or not log_dir.exists():
        return render_admin('Application Logs', '<p style="color:#888;">No logs found. Enable structured logging to view application logs.</p>')
    
    log_files = list(log_dir.glob('*.log'))
    logs = []
    for log_file in sorted(log_files, key=lambda x: x.stat().st_mtime, reverse=True)[:20]:
        try:
            with open(log_file) as f:
                content = f.read()
            logs.append({
                'filename': log_file.name,
                'size': log_file.stat().st_size,
                'modified': log_file.stat().st_mtime,
                'content': content[-5000:] if len(content) > 5000 else content,  # Last 5KB
            })
        except Exception:
            pass
    
    return render_admin('Application Logs', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.list_modules') }}">Back to Modules</a>
</div>
{% if logs %}
<div class="table-wrap">
<table>
<thead><tr>
  <th>File</th>
  <th>Size</th>
  <th>Last Modified</th>
  <th>Content (last 5KB)</th>
</tr></thead>
<tbody>
{% for log in logs %}
<tr>
  <td><code>{{ log.filename }}</code></td>
  <td>{{ '%0.1f KB'|format(log.size / 1024) }}</td>
  <td>{{ log.modified|timestamp }}</td>
  <td style="max-width:600px;overflow:hidden;text-overflow:ellipsis;"><pre style="margin:0;font-size:0.8em;white-space:pre-wrap;">{{ log.content }}</pre></td>
</tr>
{% endfor %}
</tbody></table>
</div>
{% else %}
<p style="color:#888;">No logs found.</p>
{% endif %}''', logs=logs)

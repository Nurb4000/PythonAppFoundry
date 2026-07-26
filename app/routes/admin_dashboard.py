"""Admin routes for dashboard and system information."""
from flask import Blueprint, request, redirect, url_for, render_template_string
import platform as _platform
import sqlite3 as _sqlite3
import sys as _sys
import flask as _flask
import time as _time
from datetime import timedelta
from app.services.admin_utils import admin_required
from app import db
from app.models import Module, Route, Script, Form, ScheduledTask, Trigger, User, Upload, ExecutionLog, QueryReport

dashboard_bp = Blueprint('dashboard', __name__)

_dashboard_start_time = None


@dashboard_bp.route('/dashboard')
@admin_required
def dashboard():
    global _dashboard_start_time
    if _dashboard_start_time is None:
        _dashboard_start_time = _time.time()
    uptime_seconds = _time.time() - _dashboard_start_time

    total_modules = Module.query.count()
    enabled_modules = Module.query.filter_by(enabled=True).count()
    total_routes = Route.query.count()
    total_scripts = Script.query.count()
    total_forms = Form.query.count()
    total_tasks = ScheduledTask.query.count()
    enabled_tasks = ScheduledTask.query.filter_by(enabled=True).count()
    total_triggers = Trigger.query.count()
    enabled_triggers = Trigger.query.filter_by(enabled=True).count()
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True, is_approved=True).count()
    pending_users = User.query.filter_by(is_approved=False).count()
    total_uploads = Upload.query.count()
    uploads_size = db.session.execute(db.select(db.func.sum(Upload.size))).scalar() or 0

    # Clean up old execution logs
    retention_days = int(Setting.get('log_retention_days', '0'))
    if retention_days > 0:
        from datetime import datetime, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        deleted = db.session.query(ExecutionLog).filter(ExecutionLog.created_at < cutoff).delete()
        if deleted:
            db.session.commit()

    # Clean up old incoming emails
    imap_retention_days = int(Setting.get('imap_retention_days', '0'))
    if imap_retention_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=imap_retention_days)
        deleted = db.session.query(IncomingEmail).filter(
            IncomingEmail.processed == True,
            IncomingEmail.created_at < cutoff,
        ).delete()
        if deleted:
            db.session.commit()

    recent_logs = db.session.query(ExecutionLog).order_by(ExecutionLog.created_at.desc()).limit(20).all()
    log_success = db.session.query(db.func.count(ExecutionLog.id)).filter_by(status='success').scalar() or 0
    log_errors = db.session.query(db.func.count(ExecutionLog.id)).filter_by(status='error').scalar() or 0
    total_logs = db.session.query(db.func.count(ExecutionLog.id)).scalar() or 0

    # Scheduler jobs info
    scheduler_info = _get_scheduler_info()

    # Table stats
    import re as _re
    from sqlalchemy import inspect as _sa_inspect
    platform_tables = {'users', 'user_groups', 'groups', 'modules', 'routes',
                       'scripts', 'forms', 'scheduled_tasks', 'triggers',
                       'settings', 'uploads', 'chat_sessions', 'chat_messages',
                       'execution_logs', 'module_dependencies', 'module_versions',
                       'query_reports', 'incoming_emails', 'credentials'}
    table_stats = []
    bind = db.session.get_bind()
    inspector = _sa_inspect(bind)
    for db_name in sorted(inspector.get_table_names()):
        if db_name.startswith('sqlite_') or db_name == 'alembic_version':
            continue
        try:
            count = db.session.execute(db.text(f'SELECT COUNT(*) FROM "{db_name}"')).scalar()
        except Exception:
            count = 0
        is_platform = db_name in platform_tables
        table_stats.append({'name': db_name, 'count': count, 'is_platform': is_platform})

    total_rows = sum(t['count'] for t in table_stats)

    # Module summary with route/script counts
    module_summary = []
    for m in db.session.query(Module).order_by(Module.name).all():
        module_summary.append({
            'module': m,
            'route_count': m.routes.count() if hasattr(m.routes, 'count') else len(m.routes.all()),
            'script_count': m.scripts.count() if hasattr(m.scripts, 'count') else len(m.scripts.all()),
            'form_count': m.forms.count() if hasattr(m.forms, 'count') else len(m.forms.all()),
            'task_count': m.scheduled_tasks.count() if hasattr(m.scheduled_tasks, 'count') else len(m.scheduled_tasks.all()),
            'trigger_count': m.triggers.count() if hasattr(m.triggers, 'count') else len(m.triggers.all()),
        })

    content = render_template_string(DASHBOARD_TEMPLATE,
        python_version=_platform.python_version(),
        flask_version=_flask.__version__,
        sqlite_version=_sqlite3.sqlite_version,
        uptime=uptime_seconds,
        total_modules=total_modules, enabled_modules=enabled_modules,
        total_routes=total_routes, total_scripts=total_scripts,
        total_forms=total_forms, total_tasks=total_tasks, enabled_tasks=enabled_tasks,
        total_triggers=total_triggers, enabled_triggers=enabled_triggers,
        total_users=total_users, active_users=active_users, pending_users=pending_users,
        total_uploads=total_uploads, uploads_size=uploads_size,
        recent_logs=recent_logs, log_success=log_success, log_errors=log_errors, total_logs=total_logs,
        scheduler_info=scheduler_info,
        table_stats=table_stats, total_rows=total_rows,
        module_summary=module_summary,
    )
    return render_template_string(ADMIN_TEMPLATE, title='Dashboard', content=content)


def _get_scheduler_info():
    from app.services.scheduler import _scheduler as sched
    if sched is None:
        return {'running': False, 'jobs': []}
    jobs = []
    try:
        for job in sched.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': str(job.next_run_time) if job.next_run_time else 'N/A',
                'misfired': job.misfired,
            })
    except Exception:
        pass
    return {'running': True, 'jobs': jobs}


ADMIN_TEMPLATE = '''<!DOCTYPE html>
<html>
<head><title>Admin - {{ title }}</title>
<style>
body { font-family: system-ui, sans-serif; max-width: 1400px; margin: 0 auto; padding: 1rem; }
.dash-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
.dash-card { background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 6px; padding: 1rem; }
.dash-card h3 { margin: 0 0 0.5rem 0; font-size: 0.8em; text-transform: uppercase; color: #666; letter-spacing: 0.5px; }
.dash-card .value { font-size: 1.8em; font-weight: 700; color: #1a1a2e; }
.dash-card .sub { font-size: 0.8em; color: #888; margin-top: 4px; }
.dash-section { margin-bottom: 1.5rem; }
.dash-section h2 { font-size: 1.1em; margin: 0 0 0.75rem 0; padding-bottom: 0.5rem; border-bottom: 2px solid #e94560; }
.status-ok { color: #080; }
.status-warn { color: #856404; }
.status-err { color: #c00; }
.log-success { color: #080; }
.log-error { color: #c00; }
.log-modal { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:9999; }
.log-modal-content { position:absolute; top:50%; left:50%; transform:translate(-50%, -50%); background:#fff; border-radius:8px; padding:1.5rem; max-width:600px; width:90%; max-height:80vh; overflow-y:auto; box-shadow:0 4px 20px rgba(0,0,0,0.3); }
.log-modal-content h3 { margin-top:0; border-bottom:1px solid #eee; padding-bottom:0.5rem; }
.log-modal-content pre { background:#f8f9fa; padding:1rem; border-radius:4px; overflow-x:auto; font-size:0.85em; max-height:400px; overflow-y:auto; white-space:pre-wrap; word-wrap:break-word; }
.log-modal-close { float:right; font-size:1.5em; cursor:pointer; color:#999; }
.log-modal-close:hover { color:#333; }
</style>
<script>
function showLogDetail(id, msgEl) {
  var modal = document.getElementById('logModal');
  var content = document.getElementById('logContent');
  var message = msgEl ? msgEl.textContent || msgEl.innerText : 'No details available.';
  content.innerHTML = '<h3>Execution Log #' + id + '</h3>';
  var pre = document.createElement('pre');
  pre.textContent = message;
  content.appendChild(pre);
  modal.style.display = 'block';
}
document.addEventListener('click', function(e) {
  if (e.target.id === 'logModal' || e.target.className === 'log-modal-close') {
    document.getElementById('logModal').style.display = 'none';
  }
});
</script>
<div id="logModal" class="log-modal"><div class="log-modal-content"><span class="log-modal-close">&times;</span><div id="logContent"></div></div></div>

<div class="dash-grid">
  <div class="dash-card"><h3>Modules</h3><div class="value">{{ total_modules }}</div><div class="sub">{{ enabled_modules }} enabled</div></div>
  <div class="dash-card"><h3>Routes</h3><div class="value">{{ total_routes }}</div></div>
  <div class="dash-card"><h3>Scripts</h3><div class="value">{{ total_scripts }}</div></div>
  <div class="dash-card"><h3>Forms</h3><div class="value">{{ total_forms }}</div></div>
  <div class="dash-card"><h3>Scheduled Tasks</h3><div class="value">{{ total_tasks }}</div><div class="sub">{{ enabled_tasks }} enabled</div></div>
  <div class="dash-card"><h3>Triggers</h3><div class="value">{{ total_triggers }}</div><div class="sub">{{ enabled_triggers }} enabled</div></div>
  <div class="dash-card"><h3>Users</h3><div class="value">{{ total_users }}</div><div class="sub">{{ active_users }} active{% if pending_users %}, {{ pending_users }} pending{% endif %}</div></div>
  <div class="dash-card"><h3>Uploads</h3><div class="value">{{ total_uploads }}</div><div class="sub">{{ '%0.1f MB'|format(uploads_size / 1048576) }}</div></div>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1.5rem;">
  <div class="dash-card">
    <h3>System</h3>
    <div style="font-size:0.9em;line-height:1.8;">
      Python: <strong>{{ python_version }}</strong><br>
      Flask: <strong>{{ flask_version }}</strong><br>
      Uptime: <strong>{{ '%d:%02d:%02d'|format((uptime // 3600)|int, (uptime % 3600 // 60)|int, (uptime % 60)|int) }}</strong>
    </div>
  </div>
  <div class="dash-card">
    <h3>Scheduler</h3>
    <div style="font-size:0.9em;line-height:1.8;">
      Status: <span class="{% if scheduler_info.running %}status-ok{% else %}status-err{% endif %}">{% if scheduler_info.running %}Running{% else %}Stopped{% endif %}</span><br>
      Jobs: <strong>{{ scheduler_info.jobs|length }}</strong>
      {% if scheduler_info.jobs %}
      <div style="margin-top:8px;max-height:120px;overflow-y:auto;">
        {% for job in scheduler_info.jobs %}
        <div style="padding:2px 0;font-size:0.85em;border-bottom:1px solid #eee;">
          <strong>{{ job.name }}</strong> &mdash; next: {{ job.next_run }}
          {% if job.misfired %}<span class="status-warn"> [MISFIRE]</span>{% endif %}
        </div>
        {% endfor %}
      </div>
      {% endif %}
    </div>
  </div>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1.5rem;">
  <div class="dash-section">
    <h2>Execution Logs (Recent)</h2>
    {% if recent_logs %}
    <table>
    <thead><tr><th>Time</th><th>Type</th><th>Name</th><th>Status</th><th>Duration</th><th>Details</th></tr></thead>
    <tbody>
    {% for log in recent_logs %}
    <tr>
      <td style="white-space:nowrap;font-size:0.85em;">{{ log.created_at|localtime }}</td>
      <td>{{ log.source_type }}</td>
      <td>{{ log.source_name }}</td>
      <td><span class="{% if log.status == 'success' %}log-success{% else %}log-error{% endif %}">{{ log.status|upper }}</span></td>
      <td>{{ log.duration_ms }}ms</td>
      <td>
        {% if log.error_message %}
        <button onclick="showLogDetail({{ log.id }}, this.nextElementSibling)" style="font-size:0.8em;padding:2px 8px;cursor:pointer;background:#fee;border:1px solid #c00;color:#c00;border-radius:3px;">View Error</button>
        <span style="display:none;">{{ log.error_message[:2000] }}</span>
        {% elif log.stdout %}
        <button onclick="showLogDetail({{ log.id }}, this.nextElementSibling)" style="font-size:0.8em;padding:2px 8px;cursor:pointer;background:#efe;border:1px solid #080;color:#080;border-radius:3px;">View Output</button>
        <span style="display:none;">{{ log.stdout[:2000] }}</span>
        {% else %}
        <span style="color:#888;font-size:0.85em;">—</span>
        {% endif %}
      </td>
    </tr>
    {% endfor %}
    </tbody></table>
    <div style="font-size:0.85em;color:#888;margin-top:8px;">
      Total: {{ total_logs }} &nbsp;|&nbsp; Success: <span class="log-success">{{ log_success }}</span> &nbsp;|&nbsp; Errors: <span class="log-error">{{ log_errors }}</span>
    </div>
    {% else %}
    <p style="color:#888;">No executions logged yet.</p>
    {% endif %}
  </div>

  <div class="dash-section">
    <h2>Database Tables</h2>
    <table>
    <thead><tr><th>Table</th><th>Rows</th></tr></thead>
    <tbody>
    {% for t in table_stats %}
    <tr>
      <td>{{ t.name }}{% if not t.is_platform %} <span style="color:#888;font-size:0.75em;">(dynamic)</span>{% endif %}</td>
      <td>{{ '%s'|format(t.count)|int }}</td>
    </tr>
    {% endfor %}
    </tbody></table>
    <div style="font-size:0.85em;color:#888;margin-top:8px;">Total rows across all tables: {{ '%d'|format(total_rows) }}</div>
  </div>
</div>

<div class="dash-section">
  <h2>Module Summary</h2>
  {% if module_summary %}
  <table>
  <thead><tr><th>Module</th><th>Version</th><th>Status</th><th>Routes</th><th>Scripts</th><th>Forms</th><th>Tasks</th><th>Triggers</th></tr></thead>
  <tbody>
  {% for ms in module_summary %}
  <tr>
    <td><strong>{{ ms.module.name }}</strong><br><span style="color:#888;font-size:0.8em;">{{ ms.module.slug }}</span></td>
    <td>{{ ms.module.version }}</td>
    <td>{% if ms.module.enabled %}<span class="status-ok">Enabled</span>{% else %}<span class="status-err">Disabled</span>{% endif %}</td>
    <td>{{ ms.route_count }}</td>
    <td>{{ ms.script_count }}</td>
    <td>{{ ms.form_count }}</td>
    <td>{{ ms.task_count }}</td>
    <td>{{ ms.trigger_count }}</td>
  </tr>
  {% endfor %}
  </tbody></table>
  {% else %}
  <p style="color:#888;">No modules created yet.</p>
  {% endif %}
</div>
'''

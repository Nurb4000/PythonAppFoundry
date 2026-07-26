from flask import Blueprint, request, redirect, url_for, render_template, render_template_string, flash
from app.services.admin_utils import admin_required, render_admin, ADMIN_TEMPLATE
from app import db
from app.models import Module, Route, Script, Form, ScheduledTask, Trigger, User, Upload, Setting, ExecutionLog, IncomingEmail

dashboard_bp = Blueprint('dashboard', __name__)

_dashboard_start_time = None

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



@dashboard_bp.route('/')
@admin_required
def dashboard():
    import platform as _platform
    import sqlite3 as _sqlite3
    import sys as _sys
    import flask as _flask
    import time as _time
    from datetime import timedelta

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
        from datetime import datetime, timezone, timedelta
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

    content = render_template('admin/dashboard/dashboard.html',
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







@dashboard_bp.route('/integration-health')
@admin_required
def integration_health():
    # Recent script execution logs — filter by script source_type
    limit = request.args.get('limit', 100, type=int)
    module_id = request.args.get('module_id', type=int)

    logs_q = db.session.query(ExecutionLog).filter(
        ExecutionLog.source_type.in_(['script', 'task'])
    )

    if module_id:
        # Find scripts in this module, then filter logs by their names
        script_names = [
            s.name for s in db.session.query(Script.name).filter(Script.module_id == module_id)
        ]
        if script_names:
            logs_q = logs_q.filter(ExecutionLog.source_name.in_(script_names))

    logs_q = logs_q.order_by(ExecutionLog.created_at.desc()).limit(limit)
    logs = logs_q.all()

    # Aggregated stats
    total_runs = len(logs)
    errors = [l for l in logs if l.status == 'error']
    error_rate = round(len(errors) / total_runs * 100, 1) if total_runs else 0
    avg_duration = sum(l.duration_ms for l in logs) / total_runs if total_runs else 0

    modules = db.session.query(Module).order_by(Module.name).all()

    return render_admin('Integration Health', 'admin/dashboard/integration_health.html',
                        logs=logs, total_runs=total_runs, errors=errors, error_rate=error_rate,
                        avg_duration=avg_duration, modules=modules, module_id=module_id, limit=limit)


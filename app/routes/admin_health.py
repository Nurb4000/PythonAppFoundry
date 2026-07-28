from flask import Blueprint, request, redirect, url_for, flash, jsonify
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required, render_admin
import os
import time
from datetime import datetime, timezone

health_bp = Blueprint('health', __name__)


@health_bp.route('/')
@admin_required
def health_page():
    """Detailed health check page for admins."""
    from flask import current_app
    from app import db
    from app.services.scheduler import _scheduler
    from app.services.async_executor import _pool, _max_workers
    from app.services.triggers import get_dead_letter_queue
    from app.services.credential_store import _get_key_path
    from app.models import ScriptExecution, Setting
    import shutil
    
    now = time.time()
    
    # Calculate uptime from app config
    uptime = now - current_app.config.get('_start_time', now)
    
    # Scheduler status
    scheduler_status = {'status': 'ok', 'jobs': 0}
    if _scheduler:
        scheduler_status['jobs'] = len(_scheduler.get_jobs())
    else:
        scheduler_status['status'] = 'warning'
        scheduler_status['message'] = 'not initialized'
    
    # Async executor status
    async_status = {'status': 'ok', 'pending_tasks': 0, 'max_workers': _max_workers}
    if _pool:
        try:
            pending = _pool._work_queue.qsize() if hasattr(_pool._work_queue, 'qsize') else 0
            async_status['pending_tasks'] = pending
            if pending >= _max_workers * 2:
                async_status['status'] = 'degraded'
        except Exception:
            async_status['status'] = 'error'
            async_status['message'] = 'unable to check queue'
    else:
        try:
            from app.models import ScheduledTask as ST
            st_count = db.session.query(ST).filter_by(enabled=True).count()
            if st_count > 0:
                async_status['status'] = 'warning'
                async_status['message'] = 'not initialized'
            else:
                async_status['status'] = 'ok'
                async_status['message'] = 'idle (no scheduled tasks)'
        except Exception:
            async_status['status'] = 'ok'
            async_status['message'] = 'idle (will initialize on first webhook/task)'
    
    # Dead letter queue
    dlq = get_dead_letter_queue()
    dlq_status = {'count': len(dlq), 'status': 'ok' if len(dlq) == 0 else 'warning'}
    
    # Script execution stats
    queued_count = ScriptExecution.query.filter_by(status='queued').count()
    running_count = ScriptExecution.query.filter_by(status='running').count()
    error_count = ScriptExecution.query.filter_by(status='error').count()
    
    exec_status = {
        'queued': queued_count,
        'running': running_count,
        'error': error_count,
        'status': 'ok' if error_count == 0 else 'warning'
    }
    
    # Credential store
    cred_status = {'status': 'ok'}
    try:
        from app.services.credential_store import _get_key_path
        key_path = _get_key_path(current_app)
        if os.path.exists(key_path):
            cred_status['status'] = 'ok'
        else:
            cred_status['status'] = 'error'
            cred_status['message'] = 'key file missing'
    except Exception as e:
        cred_status['status'] = 'error'
        cred_status['message'] = str(e)
    
    # Filesystem
    upload_dir = os.path.join(current_app.instance_path, 'uploads')
    backup_dir = os.path.join(current_app.instance_path, 'backups')
    
    try:
        disk_usage = shutil.disk_usage('/')
        uploads_writable = os.access(upload_dir, os.W_OK) if os.path.exists(upload_dir) else False
        backups_writable = os.access(backup_dir, os.W_OK) if os.path.exists(backup_dir) else False
        
        fs_status = {
            'uploads_writable': uploads_writable,
            'backups_writable': backups_writable,
            'disk_usage_percent': round(disk_usage.used / disk_usage.total * 100, 1),
            'disk_total_gb': round(disk_usage.total / (1024**3), 1),
            'disk_free_gb': round(disk_usage.free / (1024**3), 1),
            'status': 'ok',
            'upload_dir': upload_dir,
            'backup_dir': backup_dir
        }
        
        if not uploads_writable:
            fs_status['status'] = 'error'
            fs_status['message'] = f'uploads directory not writable: {upload_dir}'
        elif not backups_writable:
            fs_status['status'] = 'error'
            fs_status['message'] = f'backups directory not writable: {backup_dir}'
        elif fs_status['disk_usage_percent'] > 90:
            fs_status['status'] = 'warning'
            fs_status['message'] = f'disk usage high: {fs_status["disk_usage_percent"]}%'
    except Exception as e:
        fs_status = {'status': 'error', 'message': f'filesystem check failed: {str(e)}'}
    
    # IMAP status
    imap_status = {'configured': False, 'status': 'ok'}
    try:
        if Setting.get('imap_enabled', 'false') == 'true':
            imap_status['configured'] = True
    except Exception:
        imap_status['status'] = 'unknown'
    
    # Database
    db_status = {'status': 'ok'}
    try:
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
    except Exception as e:
        db_status['status'] = 'error'
        db_status['message'] = str(e)
    
    health_data = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'uptime_seconds': round(uptime, 1),
        'python_version': os.sys.version.split()[0],
        'flask_version': '3.0.0',
        'components': {
            'database': db_status,
            'scheduler': scheduler_status,
            'async_executor': async_status,
            'dead_letter_queue': dlq_status,
            'script_executions': exec_status,
            'credential_store': cred_status,
            'filesystem': fs_status,
            'imap': imap_status,
        }
    }
    
    # Determine overall status
    statuses = [c['status'] for c in health_data['components'].values()]
    if 'error' in statuses:
        health_data['overall_status'] = 'unhealthy'
    elif 'warning' in statuses or 'degraded' in statuses:
        health_data['overall_status'] = 'degraded'
    else:
        health_data['overall_status'] = 'healthy'
    
    return render_admin('System Health', 'admin/health/index.html', health=health_data)

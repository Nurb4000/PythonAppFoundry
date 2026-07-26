"""Admin routes for health check endpoint."""
from flask import Blueprint, jsonify

health_bp = Blueprint('health', __name__)


@health_bp.route('/healthz')
def health_check():
    """Health check endpoint for Docker and monitoring."""
    from app.services.tenant import get_current_tenant
    tenant = get_current_tenant()
    
    checks = {'status': 'ok', 'tenant': tenant.slug if tenant else 'default'}
    errors = []
    
    # Check database connectivity
    try:
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        checks['database'] = 'connected'
    except Exception as e:
        errors.append(f'database: {e}')
        checks['database'] = 'error'
    
    # Check scheduler status
    try:
        from app.services.scheduler import _scheduler
        if _scheduler is not None:
            checks['scheduler'] = f'running ({len(_scheduler.get_jobs())} jobs)'
        else:
            checks['scheduler'] = 'not initialized'
    except Exception as e:
        errors.append(f'scheduler: {e}')
        checks['scheduler'] = 'error'
    
    # Check IMAP if enabled
    try:
        from app.models import Setting
        if Setting.get('imap_enabled', 'false') == 'true':
            checks['imap'] = 'configured'
        else:
            checks['imap'] = 'disabled'
    except Exception:
        checks['imap'] = 'unknown'
    
    if errors:
        checks['errors'] = errors
        return jsonify(checks), 503
    
    return jsonify(checks), 200

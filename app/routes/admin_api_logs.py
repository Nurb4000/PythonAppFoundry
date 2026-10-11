"""Admin routes for API log viewing."""
from flask import Blueprint, request, redirect, url_for, jsonify
from app.services.admin_utils import admin_required, render_admin
from app import db
from app.models import ApiLog, ApiKey

api_logs_bp = Blueprint('api_logs', __name__)


@api_logs_bp.route('/')
@admin_required
def list_api_logs():
    """List API logs with pagination and filtering."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    method = request.args.get('method', '')
    status_code = request.args.get('status_code', '', type=int)
    api_key_id = request.args.get('api_key_id', type=int)

    q = db.session.query(ApiLog)

    if method:
        q = q.filter_by(method=method.upper())
    if status_code:
        q = q.filter_by(status_code=status_code)
    if api_key_id:
        q = q.filter_by(api_key_id=api_key_id)

    total = q.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    offset = (page - 1) * per_page
    logs = q.order_by(ApiLog.created_at.desc()).offset(offset).limit(per_page).all()

    # Get API keys for filter dropdown
    api_keys = db.session.query(ApiKey).filter_by(is_active=True).order_by(ApiKey.name).all()

    return render_admin('API Logs', 'admin/api_logs/list.html',
                        logs=logs, page=page, per_page=per_page,
                        total=total, total_pages=total_pages,
                        method=method, status_code=status_code,
                        api_key_id=api_key_id, api_keys=api_keys)


@api_logs_bp.route('/<int:log_id>')
@admin_required
def view_api_log(log_id):
    """View a single API log entry."""
    log = db.session.get(ApiLog, log_id)
    if not log:
        from flask import flash
        flash('API log entry not found', 'error')
        return redirect(url_for('admin.api_logs.list_api_logs'))

    return render_admin(f'API Log #{log_id}', 'admin/api_logs/view.html', log=log)


@api_logs_bp.route('/export')
@admin_required
def export_api_logs():
    """Export API logs as JSON."""
    method = request.args.get('method', '')
    status_code = request.args.get('status_code', '', type=int)
    api_key_id = request.args.get('api_key_id', type=int)

    q = db.session.query(ApiLog)

    if method:
        q = q.filter_by(method=method.upper())
    if status_code:
        q = q.filter_by(status_code=status_code)
    if api_key_id:
        q = q.filter_by(api_key_id=api_key_id)

    logs = q.order_by(ApiLog.created_at.desc()).limit(1000).all()

    from flask import Response
    import json

    data = []
    for log in logs:
        data.append({
            'id': log.id,
            'created_at': log.created_at.isoformat() if log.created_at else None,
            'method': log.method,
            'path': log.path,
            'status_code': log.status_code,
            'duration_ms': log.duration_ms,
            'client_ip': log.client_ip,
            'user_agent': log.user_agent,
            'api_key_id': log.api_key_id,
            'request_body': log.request_body,
            'response_summary': log.response_summary,
        })

    return Response(
        json.dumps(data, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment; filename=api_logs.json'},
    )


@api_logs_bp.route('/clear')
@admin_required
def clear_api_logs():
    """Clear all API logs (with confirmation)."""
    if request.args.get('confirm') == 'true':
        count = db.session.query(ApiLog).count()
        db.session.query(ApiLog).delete()
        db.session.commit()
        from flask import flash
        flash(f'Cleared {count} API log entries', 'info')
    return redirect(url_for('admin.api_logs.list_api_logs'))

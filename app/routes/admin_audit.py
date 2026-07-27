from flask import Blueprint, request
from app.services.admin_utils import admin_required, render_admin
from app.services.audit import log_audit
from app import db
from app.models import AuditLog

audit_bp = Blueprint('audit', __name__)


@audit_bp.route('/')
@admin_required
def list_audit():
    entity_type = request.args.get('entity_type', '')
    user_filter = request.args.get('user', '')
    action_filter = request.args.get('action', '')
    limit = request.args.get('limit', 200, type=int)

    q = db.session.query(AuditLog)

    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if user_filter:
        q = q.filter(AuditLog.user_name == user_filter)
    if action_filter:
        q = q.filter(AuditLog.action == action_filter)

    logs = q.order_by(AuditLog.created_at.desc()).limit(limit).all()

    entity_types = db.session.query(AuditLog.entity_type).distinct().order_by(AuditLog.entity_type).all()
    users = db.session.query(AuditLog.user_name).distinct().filter(AuditLog.user_name != '').order_by(AuditLog.user_name).all()
    actions = db.session.query(AuditLog.action).distinct().order_by(AuditLog.action).all()

    content = render_admin('Audit Log', 'admin/audit/list.html',
        logs=logs,
        entity_types=[t[0] for t in entity_types],
        users=[u[0] for u in users],
        actions=[a[0] for a in actions],
        current_entity_type=entity_type,
        current_user_filter=user_filter,
        current_action_filter=action_filter,
        limit=limit,
    )
    from flask import render_template
    return render_template('admin/base.html', title='Audit Log', content=content)

import logging
from flask import request
from flask_login import current_user

logger = logging.getLogger(__name__)


def log_audit(action, entity_type, entity_id=None, entity_name='', details=''):
    try:
        from app import db
        from app.models import AuditLog

        user_id = None
        user_name = ''
        try:
            if current_user and current_user.is_authenticated:
                user_id = current_user.id
                user_name = current_user.username
        except Exception:
            pass

        ip = ''
        try:
            ip = request.remote_addr or ''
            forwarded = request.headers.get('X-Forwarded-For', '')
            if forwarded:
                ip = forwarded.split(',')[0].strip()
        except Exception:
            pass

        entry = AuditLog(
            user_id=user_id,
            user_name=user_name,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=str(entity_name)[:200] if entity_name else '',
            details=str(details)[:2000] if details else '',
            ip_address=ip,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as e:
        logger.warning(f'Audit log failed: {e}')
        try:
            db.session.rollback()
        except Exception:
            pass

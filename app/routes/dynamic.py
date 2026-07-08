from flask import Blueprint, request, redirect, url_for
from flask_login import current_user

from app import db
from app.models import Route, User
from app.services.script_runner import execute_script
from app.services.triggers import fire_triggers

dynamic_bp = Blueprint('dynamic', __name__)


@dynamic_bp.route('/', defaults={'slug': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@dynamic_bp.route('/<path:slug>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def handle_dynamic(slug):
    if not slug:
        slug = '/'
    else:
        slug = '/' + slug

    route = db.session.query(Route).filter_by(slug=slug).first()
    if not route:
        if slug == '/' and db.session.query(Route).count() == 0:
            if db.session.query(User).count() == 0:
                return redirect(url_for('auth.setup'))
            return redirect(url_for('auth.login'))
        return 'Not Found', 404

    if not route.module.enabled:
        return 'Module disabled', 503

    allowed = [m.strip() for m in route.methods.upper().split(',')]
    if request.method not in allowed:
        return 'Method Not Allowed', 405

    if route.auth_required and not current_user.is_authenticated:
        return redirect(url_for('auth.login', next=request.path))

    if route.allowed_groups and current_user.is_authenticated:
        allowed = set(g.strip() for g in route.allowed_groups.split(',') if g.strip())
        if allowed:
            user_group_ids = set(str(g.id) for g in current_user.groups)
            if not allowed.intersection(user_group_ids):
                return 'Forbidden', 403

    if route.script:
        result = execute_script(route.script, route=route)
        fire_triggers('after_route', route.module.slug, {
            'route': route,
            'result': result,
            'user': current_user if current_user.is_authenticated else None,
        })
        return result

    return 'No script configured for this route', 500

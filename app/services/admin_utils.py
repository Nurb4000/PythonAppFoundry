"""Shared admin utilities extracted from the monolithic admin.py.

This module provides common patterns used across admin routes:
- Permission decorators
- Auto-versioning helper
- Cron expression description
- Attribute proxy for list views
- Render helper for admin pages
- List view factory
- Multi-format export utility (CSV, JSON, XLSX, PDF)
"""
from datetime import datetime as _datetime, timezone as _tz
from functools import wraps

from flask import abort, current_app, render_template, render_template_string, request, Response
import csv, io

from app import db
from app.models import Module, Setting
from app.services.exporters import EXPORT_FORMATS


def admin_required(f):
    """Decorator: only admins can access."""
    from flask_login import login_required, current_user
    @wraps(f)
    @login_required
    def wrapper(*a, **kw):
        if current_user.role != 'admin':
            abort(403)
        return f(*a, **kw)
    return wrapper


def developer_or_admin_required(f):
    """Decorator: admins and developers can access."""
    from flask_login import login_required, current_user
    @wraps(f)
    @login_required
    def wrapper(*a, **kw):
        if current_user.role not in ('admin', 'developer'):
            abort(403)
        return f(*a, **kw)
    return wrapper


def create_auto_version(module_id, comment=None):
    """Create an automatic version snapshot after any module change."""
    try:
        from app.services.versioning import create_version as _create_version
        from flask_login import current_user
        user_id = current_user.id if current_user.is_authenticated else None
        if comment is None:
            comment = 'Auto-saved'
        _create_version(module_id, comment=comment, user_id=user_id)
    except Exception:
        pass  # Silently fail - versioning is not critical


def _describe_cron(expr):
    """Convert a cron expression to a human-readable description."""
    parts = expr.strip().split()
    if len(parts) != 5:
        return ''
    minute, hour, day, month, day_of_week = parts
    if minute.startswith('*/') and hour == '*' and day == '*' and month == '*' and day_of_week == '*':
        n = minute[2:]
        return f'Every {n} minute{"s" if n != "1" else ""}'
    if minute == '0' and hour.startswith('*/') and day == '*' and month == '*' and day_of_week == '*':
        n = hour[2:]
        return f'Every {n} hour{"s" if n != "1" else ""}'
    if minute == '0' and hour == '0' and day == '*' and month == '*' and day_of_week == '*':
        return 'Daily at midnight'
    if day == '*' and month == '*' and day_of_week == '*':
        try:
            h, m = int(hour), int(minute)
            return f'Daily at {h % 12 or 12}:{m:02d} {"AM" if h < 12 else "PM"}'
        except ValueError:
            pass
    if minute == '0' and hour == '*' and day == '*' and month == '*' and day_of_week == '*':
        return 'Every hour'
    if minute == '*' and hour == '*' and day == '*' and month == '*' and day_of_week == '*':
        return 'Every minute'
    return ''


class AttrProxy:
    """Proxy that converts model objects to attribute-accessible dicts for templates."""
    def __init__(self, obj):
        self._obj = obj
    def __getattr__(self, name):
        if name == '_module_name':
            mod = getattr(self._obj, 'module', None)
            return getattr(mod, 'name', '') if mod else ''
        if name == 'cron_expression':
            expr = str(getattr(self._obj, 'cron_expression', '') or '')
            desc = _describe_cron(expr)
            return f'{expr}  ({desc})' if desc else expr
        val = getattr(self._obj, name, '')
        if hasattr(val, '__call__'):
            return ''
        if isinstance(val, _datetime):
            if val.tzinfo is not None:
                val = val.astimezone().replace(tzinfo=None)
            else:
                val = val.replace(tzinfo=_tz.utc).astimezone().replace(tzinfo=None)
        return str(val or '')





def render_admin(title, content_template, **kwargs):
    """Render an admin page with the standard layout."""
    if content_template.endswith('.html'):
        content = render_template(content_template, **kwargs)
    else:
        content = render_template_string(content_template, **kwargs)
    return render_template('admin/base.html', title=title, content=content)


def list_view(model, name_plural, columns, edit_endpoint, new_endpoint, show_view=False, has_module=False):
    """Generic list view for admin entities."""
    selected_module_id = request.args.get('module_id', type=int)
    sort_col = request.args.get('sort', 'id')
    sort_order = request.args.get('order', 'asc')

    q = db.session.query(model)
    if selected_module_id and has_module:
        q = q.filter(model.module_id == selected_module_id)

    sort_attr = getattr(model, sort_col, None)
    if sort_attr is not None:
        q = q.order_by(sort_attr.desc() if sort_order == 'desc' else sort_attr.asc())
    else:
        q = q.order_by(model.id)

    rows = q.all()

    fmt = request.args.get('format', '')
    if fmt == 'csv':
        return _export_csv(name_plural, columns, rows, has_module)
    if fmt in EXPORT_FORMATS:
        return EXPORT_FORMATS[fmt](name_plural, columns, rows, has_module)

    modules = db.session.query(Module).order_by(Module.name).all() if has_module else []

    content = render_template('admin/list.html',
        columns=columns,
        rows=[AttrProxy(r) for r in rows],
        new_url=current_app.url_for(new_endpoint),
        edit_url=current_app.url_for(edit_endpoint, id=0).rsplit('/', 1)[0],
        show_view=show_view,
        has_module=has_module,
        modules=modules,
        selected_module_id=selected_module_id,
        sort_col=sort_col,
        sort_order=sort_order,
    )
    return render_template('admin/base.html',
        title=name_plural.title(),
        content=content,
    )


def _export_csv(name_plural, columns, rows, has_module):
    """Export rows as CSV response."""
    buf = io.StringIO()
    w = csv.writer(buf)
    headers = list(columns)
    if has_module:
        headers.insert(0, 'module')
    w.writerow(headers)
    for r in rows:
        vals = []
        if has_module:
            vals.append(getattr(getattr(r, 'module', None), 'name', ''))
        for col in columns:
            vals.append(str(getattr(r, col, '') or ''))
        w.writerow(vals)
    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={name_plural.replace(" ", "_")}.csv'},
    )

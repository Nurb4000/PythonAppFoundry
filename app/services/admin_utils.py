"""Shared admin utilities extracted from the monolithic admin.py.

This module provides common patterns used across admin routes:
- Permission decorators
- Auto-versioning helper
- Cron expression description
- Attribute proxy for list views
- Render helper for admin pages
- List view factory
- CSV export utility
"""
from datetime import datetime as _datetime, timezone as _tz
from functools import wraps

from flask import abort, current_app, render_template_string, request, Response
import csv, io

from app import db
from app.models import Module, Setting


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


ADMIN_TEMPLATE = '''<!DOCTYPE html>
<html>
<head><title>Admin - {{ title }}</title>
<style>
body { font-family: system-ui, sans-serif; max-width: 1400px; margin: 0 auto; padding: 1rem; }
nav a { margin-right: 1rem; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; padding: 0.5rem; border-bottom: 1px solid #ddd; white-space: nowrap; }
th a { color: inherit; text-decoration: none; display: inline-block; }
th a:hover { color: #2563eb; }
.flash { background: #d4edda; padding: 0.5rem; margin: 1rem 0; }
.table-wrap { overflow-x: auto; max-width: 100%; border: 1px solid #eee; border-radius: 4px; }
.table-wrap::-webkit-scrollbar { height: 10px; }
.table-wrap::-webkit-scrollbar-track { background: #f1f1f1; border-radius: 5px; }
.table-wrap::-webkit-scrollbar-thumb { background: #bbb; border-radius: 5px; }
.table-wrap::-webkit-scrollbar-thumb:hover { background: #888; }
</style>
</head>
<body>
<h1>{{ title }}</h1>
{% for msg in get_flashed_messages() %}<div class="flash">{{ msg }}</div>{% endfor %}
{{ content|safe }}
<div style="text-align:center;color:#999;font-size:0.8em;margin-top:2rem;padding:1rem 0;border-top:1px solid #eee;">Copyright 2026 IDS</div>
</body>
</html>
'''

LIST_TEMPLATE = '''<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;flex-wrap:wrap;">
  <a href="{{ new_url }}">+ New</a>
  {% if modules %}
  <form method="GET" style="display:inline;">
    <select name="module_id" onchange="this.form.submit()" style="padding:4px 8px;">
      <option value="">All Modules</option>
      {% for m in modules %}
      <option value="{{ m.id }}" {% if selected_module_id == m.id %}selected{% endif %}>{{ m.name }}</option>
      {% endfor %}
    </select>
    {% if sort_col %}<input name="sort" type="hidden" value="{{ sort_col }}">{% endif %}
    {% if sort_order %}<input name="order" type="hidden" value="{{ sort_order }}">{% endif %}
  </form>
  {% endif %}
  <a href="?format=csv{% if selected_module_id %}&module_id={{ selected_module_id }}{% endif %}{% if sort_col %}&sort={{ sort_col }}&order={{ sort_order }}{% endif %}" style="margin-left:auto;">Export CSV</a>
</div>
<div class="table-wrap">
<table>
<thead><tr>
  {% if has_module %}<th><a href="?sort=module_id&order={% if sort_col == 'module_id' and sort_order == 'asc' %}desc{% else %}asc{% endif %}{% if selected_module_id %}&module_id={{ selected_module_id }}{% endif %}">Module{% if sort_col == 'module_id' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>{% endif %}
  {% for col in columns %}
  <th><a href="?sort={{ col }}&order={% if sort_col == col and sort_order == 'asc' %}desc{% else %}asc{% endif %}{% if selected_module_id %}&module_id={{ selected_module_id }}{% endif %}">{{ col }}{% if sort_col == col %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  {% endfor %}
  <th>Actions</th>
</tr></thead>
<tbody>
{% for row in rows %}
<tr>
  {% if has_module %}<td>{{ row._module_name }}</td>{% endif %}
  {% for col in columns %}<td>{{ row|attr(col) }}</td>{% endfor %}
  <td>
    {% if show_view and row._obj.slug %}<a href="{{ row._obj.slug }}" target="_blank">View</a> | {% endif %}
    <a href="{{ edit_url }}/{{ row.id }}">Edit</a>
  </td>
</tr>
{% endfor %}
</tbody></table>
</div>'''


def render_admin(title, content_template, **kwargs):
    """Render an admin page with the standard layout."""
    content = render_template_string(content_template, **kwargs)
    return render_template_string(ADMIN_TEMPLATE, title=title, content=content)


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

    if request.args.get('format') == 'csv':
        return _export_csv(name_plural, columns, rows, has_module)

    modules = db.session.query(Module).order_by(Module.name).all() if has_module else []

    content = render_template_string(LIST_TEMPLATE,
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
    return render_template_string(ADMIN_TEMPLATE,
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

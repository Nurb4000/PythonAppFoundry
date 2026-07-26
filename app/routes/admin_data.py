"""Admin routes for data browser and table management."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash, Response
from sqlalchemy import func, inspect as sa_inspect, Table, MetaData
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required, developer_or_admin_required
from app import db
from app.models import Module

data_bp = Blueprint('data', __name__)

SENSITIVE_COLUMNS = {'password_hash', '_password'}


@data_bp.route('/data')
@admin_required
def list_tables():
    from app.models import DynamicTableRegistry
    table_modules = {}
    platform_tables = {'users', 'user_groups', 'groups', 'modules', 'routes',
                       'scripts', 'forms', 'scheduled_tasks', 'triggers',
                       'settings', 'uploads', 'chat_sessions', 'chat_messages',
                       'execution_logs', 'module_dependencies', 'module_versions',
                       'query_reports', 'incoming_emails', 'dynamic_table_registry', 'credentials'}
    for t in platform_tables:
        table_modules[t] = 'Platform'

    for reg in DynamicTableRegistry.query.all():
        mod = reg.module
        mod_name = mod.name if mod else '?'
        tname = reg.table_name
        if tname not in table_modules:
            table_modules[tname] = mod_name
        elif isinstance(table_modules.get(tname), list):
            if mod_name not in table_modules[tname]:
                table_modules[tname].append(mod_name)
        elif table_modules.get(tname) != mod_name:
            table_modules[tname] = [table_modules[tname], mod_name]

    _all_scripts = db.session.query(Script).all()
    def _find_module_for_table(tname):
        for _s in _all_scripts:
            if _s.module_id and tname in _s.source_code.lower():
                mod = _s.module
                return mod.name if mod else '?'
        return ''

    filter_module = request.args.get('module', '')
    sort_col = request.args.get('sort', 'name')
    sort_order = request.args.get('order', 'asc')

    tables = []
    seen = set()
    bind = db.session.get_bind()
    inspector = sa_inspect(bind)
    for db_name in inspector.get_table_names():
        if db_name.startswith('sqlite_') or db_name == 'alembic_version':
            continue
        seen.add(db_name)
    for name in db.metadata.tables:
        seen.add(name)

    for name in sorted(seen):
        table = db.metadata.tables.get(name)
        if table is None:
            table = Table(name, db.metadata, autoload_with=bind, extend_existing=True)
        try:
            pk_col = list(table.primary_key)[0] if table.primary_key else table.columns[0]
            count = db.session.execute(func.count(pk_col)).scalar()
        except Exception:
            count = '?'
        cols = [{'name': c.name, 'type': str(c.type), 'pk': c.primary_key, 'nullable': c.nullable}
                for c in table.columns if c.name not in SENSITIVE_COLUMNS]
        module_info = table_modules.get(name, '')
        if not module_info:
            module_info = _find_module_for_table(name)
        if isinstance(module_info, list):
            module_info = ', '.join(module_info)
        if filter_module and module_info != filter_module:
            continue
        tables.append({'name': name, 'count': count, 'columns': cols, 'module': module_info,
                       'is_platform': name in platform_tables})

    rev = sort_order == 'desc'
    if sort_col == 'name':
        tables.sort(key=lambda t: t['name'], reverse=rev)
    elif sort_col == 'rows':
        tables.sort(key=lambda t: str(t['count']), reverse=rev)
    elif sort_col == 'module':
        tables.sort(key=lambda t: t['module'], reverse=rev)

    if request.args.get('format') == 'csv':
        import csv, io
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['table', 'rows', 'module'])
        for t in tables:
            w.writerow([t['name'], t['count'], t['module']])
        return Response(buf.getvalue(), mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=tables.csv'})

    module_names = sorted(set(
        v for vv in table_modules.values()
        for v in (vv if isinstance(vv, list) else [vv])
    ))

    return render_admin('Database Tables', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;flex-wrap:wrap;">
  <form method="GET" style="display:inline;">
    <select name="module" onchange="this.form.submit()" style="padding:4px 8px;">
      <option value="">All Modules</option>
      {% for m in module_names %}
      <option value="{{ m }}" {% if filter_module == m %}selected{% endif %}>{{ m }}</option>
      {% endfor %}
    </select>
    {% if sort_col %}<input name="sort" type="hidden" value="{{ sort_col }}">{% endif %}
    {% if sort_order %}<input name="order" type="hidden" value="{{ sort_order }}">{% endif %}
  </form>
  <a href="?format=csv{% if filter_module %}&module={{ filter_module }}{% endif %}" style="margin-left:auto;">Export CSV</a>
</div>
<div class="table-wrap">
<table>
<thead><tr>
  <th><a href="?sort=module&order={% if sort_col == 'module' and sort_order == 'asc' %}desc{% else %}asc{% endif %}{% if filter_module %}&module={{ filter_module }}{% endif %}">Module{% if sort_col == 'module' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th><a href="?sort=name&order={% if sort_col == 'name' and sort_order == 'asc' %}desc{% else %}asc{% endif %}{% if filter_module %}&module={{ filter_module }}{% endif %}">Table{% if sort_col == 'name' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</th>
  <th><a href="?sort=rows&order={% if sort_col == 'rows' and sort_order == 'asc' %}desc{% else %}asc{% endif %}{% if filter_module %}&module={{ filter_module }}{% endif %}">Rows{% if sort_col == 'rows' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</th>
  <th>Columns</th>
  <th></th>
</tr></thead>
<tbody>
{% for t in tables %}
<tr>
  <td>{% if t.module %}{{ t.module }}{% else %}<span style="color:#c00;">Orphaned</span>{% endif %}</td>
  <td><strong>{{ t.name }}</strong></td>
  <td>{{ t.count }}</td>
  <td style="font-size:0.85em;max-width:400px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
    {% for c in t.columns %}{{ c.name }} <span style="color:#888;">{{ c.type }}</span>{% if c.pk %} <span style="color:#c00;">PK</span>{% endif %}{% if not loop.last %}, {% endif %}{% endfor %}
  </td>
  <td>
    <a href="{{ url_for('admin.browse_table', table_name=t.name) }}">Browse</a>
    {% if not t.is_platform %}
    <form method="POST" action="{{ url_for('admin.delete_table', table_name=t.name) }}" style="display:inline" onsubmit="return confirm('Drop table &quot;{{ t.name }}&quot; and all its data?')">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <button type="submit" style="background:none;border:none;color:#d00;cursor:pointer;text-decoration:underline;padding:0;font:inherit">Delete</button>
    </form>
    {% endif %}
  </td>
</tr>
{% endfor %}
</tbody></table>
</div>''', tables=tables, module_names=module_names, filter_module=filter_module,
       sort_col=sort_col, sort_order=sort_order)


@data_bp.route('/data/<table_name>/')
@admin_required
def browse_table(table_name):
    if table_name not in db.metadata.tables:
        return 'Table not found', 404
    table = db.metadata.tables[table_name]
    page = request.args.get('page', 1, type=int)
    per_page = 50

    columns = [c for c in table.columns if c.name not in SENSITIVE_COLUMNS]
    pk_col = list(table.primary_key)[0] if table.primary_key else table.columns[0]
    total = db.session.execute(func.count(pk_col)).scalar()
    rows = db.session.execute(
        table.select().limit(per_page).offset((page - 1) * per_page)
    ).mappings().fetchall()

    total_pages = max(1, (total + per_page - 1) // per_page)

    if request.args.get('format') == 'csv':
        import csv, io
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow([c.name for c in columns])
        all_rows = db.session.execute(table.select()).mappings().fetchall()
        for row in all_rows:
            w.writerow([str(row.get(c.name, '') or '') for c in columns])
        return Response(
            buf.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename="{table_name}.csv"'},
        )

    return render_admin('Browse: ' + table_name, '''
<div style="margin-bottom:1rem;">
  <a href="{{ url_for('admin.list_tables') }}">&larr; All Tables</a>
  | <a href="{{ url_for('admin.new_row', table_name=table_name) }}">+ New Row</a>
  | <a href="?format=csv">Export CSV</a>
  <span style="float:right;">Page {{ page }} / {{ total_pages }} ({{ total }} rows)</span>
</div>
<table>
<thead><tr>{% for c in columns %}<th>{{ c.name }}<br><span style="font-weight:normal;font-size:0.75em;color:#888;">{{ c.type }}</span></th>{% endfor %}<th></th></tr></thead>
<tbody>
{% for row in rows %}
<tr>
  {% for c in columns %}
  <td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:0.9em;">
    {{ row[c.name] if row[c.name] is not none else '<span style="color:#ccc;">NULL</span>'|safe }}
  </td>
  {% endfor %}
  <td style="white-space:nowrap;">
    <a href="{{ url_for('admin.edit_row', table_name=table_name, id=row['id']) }}">Edit</a>
    <form method="POST" action="{{ url_for('admin.delete_row', table_name=table_name, id=row['id']) }}" style="display:inline" onsubmit="return confirm('Delete row {{ row['id'] }}?')">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <button style="background:none;border:none;color:#c00;cursor:pointer;text-decoration:underline;padding:0;font:inherit;font-size:0.9em;">Delete</button>
    </form>
  </td>
</tr>
{% endfor %}
</tbody></table>
{% if total_pages > 1 %}
<div style="margin-top:1rem;">
{% for p in range(1, total_pages + 1) %}
  <a href="?page={{ p }}" style="padding:0.25rem 0.5rem;{% if p == page %}background:#2563eb;color:#fff;{% endif %}">{{ p }}</a>
{% endfor %}
</div>
{% endif %}''', table_name=table_name, columns=columns, rows=rows, page=page, total=total, total_pages=total_pages)


@data_bp.route('/data/<table_name>/new', methods=['GET', 'POST'])
@admin_required
def new_row(table_name):
    if table_name not in db.metadata.tables:
        return 'Table not found', 404
    table = db.metadata.tables[table_name]
    columns = [c for c in table.columns if c.name != 'id' and c.name not in SENSITIVE_COLUMNS]

    if request.method == 'POST':
        values = {}
        for c in columns:
            val = request.form.get(c.name)
            if val == '':
                values[c.name] = None
            else:
                col_type = str(c.type).lower()
                if 'integer' in col_type:
                    values[c.name] = int(val) if val else None
                elif 'float' in col_type or 'double' in col_type:
                    values[c.name] = float(val) if val else None
                elif 'boolean' in col_type or 'bool' in col_type:
                    values[c.name] = val == '1'
                elif 'datetime' in col_type:
                    from datetime import datetime
                    try:
                        values[c.name] = datetime.fromisoformat(val) if val else None
                    except Exception:
                        values[c.name] = None
                else:
                    values[c.name] = val
        db.session.execute(table.insert().values(**values))
        db.session.commit()
        return redirect(url_for('admin.browse_table', table_name=table_name))

    return render_admin('New Row: ' + table_name, '''
<form method="POST">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
{% for c in columns %}
<label style="display:block;margin-bottom:8px;">
  <strong>{{ c.name }}</strong>
  {% set t = c.type|string|lower %}
  {% if 'text' in t and 'char' not in t %}
    <textarea name="{{ c.name }}" style="width:100%;padding:6px;font-family:monospace;" {% if not c.nullable %}required{% endif %}></textarea>
  {% elif 'bool' in t %}
    <select name="{{ c.name }}"><option value="">--</option><option value="1">True</option><option value="0">False</option></select>
  {% elif 'datetime' in t or 'timestamp' in t %}
    <input name="{{ c.name }}" type="datetime-local" style="width:100%;padding:6px;">
  {% elif 'int' in t or 'float' in t or 'double' in t or 'numeric' in t or 'decimal' in t %}
    <input name="{{ c.name }}" type="number" step="any" style="width:100%;padding:6px;" {% if not c.nullable %}required{% endif %}>
  {% else %}
    <input name="{{ c.name }}" style="width:100%;padding:6px;" {% if not c.nullable %}required{% endif %}>
  {% endif %}
  {% if c.nullable %}<span style="color:#888;font-size:0.85em;">optional</span>{% endif %}
</label>
{% endfor %}
<button style="padding:8px 20px;">Save</button>
<a href="{{ url_for('admin.browse_table', table_name=table_name) }}" style="margin-left:1rem;">Cancel</a>
</form>''', table_name=table_name, columns=columns)


@data_bp.route('/data/<table_name>/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_row(table_name, id):
    if table_name not in db.metadata.tables:
        return 'Table not found', 404
    table = db.metadata.tables[table_name]
    if 'id' not in table.columns:
        return 'Table has no id column', 400
    row = db.session.execute(table.select().where(table.c.id == id)).mappings().first()
    if not row:
        return 'Row not found', 404

    columns = []
    for c in table.columns:
        if c.name == 'id' or c.name in SENSITIVE_COLUMNS:
            continue
        raw = row[c.name]
        col_type = str(c.type).lower()
        info = {'name': c.name, 'nullable': c.nullable}
        if 'bool' in col_type:
            info['kind'] = 'bool'
            info['val'] = '1' if raw else '0'
        elif 'datetime' in col_type or 'timestamp' in col_type:
            info['kind'] = 'datetime'
            if raw:
                info['val'] = raw.isoformat()[:19] if hasattr(raw, 'isoformat') else str(raw)
            else:
                info['val'] = ''
        elif 'int' in col_type or 'float' in col_type or 'double' in col_type or 'numeric' in col_type or 'decimal' in col_type:
            info['kind'] = 'number'
            info['val'] = str(raw) if raw is not None else ''
        elif 'text' in col_type and 'char' not in col_type:
            info['kind'] = 'textarea'
            info['val'] = str(raw) if raw is not None else ''
        else:
            info['kind'] = 'text'
            info['val'] = str(raw) if raw is not None else ''
        columns.append(info)

    if request.method == 'POST':
        values = {}
        for info in columns:
            val = request.form.get(info['name'])
            if val == '':
                values[info['name']] = None
            else:
                if info['kind'] == 'number':
                    try:
                        values[info['name']] = int(val)
                    except ValueError:
                        values[info['name']] = float(val)
                elif info['kind'] == 'bool':
                    values[info['name']] = val == '1'
                elif info['kind'] == 'datetime':
                    from datetime import datetime
                    try:
                        values[info['name']] = datetime.fromisoformat(val)
                    except Exception:
                        values[info['name']] = None
                else:
                    values[info['name']] = val
        db.session.execute(table.update().where(table.c.id == id).values(**values))
        db.session.commit()
        return redirect(url_for('admin.browse_table', table_name=table_name))

    return render_admin('Edit Row: ' + table_name, '''
<form method="POST">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
{% for info in columns %}
<label style="display:block;margin-bottom:8px;">
  <strong>{{ info.name }}</strong>
  {% if info.kind == 'textarea' %}
    <textarea name="{{ info.name }}" style="width:100%;padding:6px;font-family:monospace;" {% if not info.nullable %}required{% endif %}>{{ info.val }}</textarea>
  {% elif info.kind == 'bool' %}
    <select name="{{ info.name }}"><option value="">--</option><option value="1" {% if info.val == '1' %}selected{% endif %}>True</option><option value="0" {% if info.val == '0' %}selected{% endif %}>False</option></select>
  {% elif info.kind == 'datetime' %}
    <input name="{{ info.name }}" type="datetime-local" value="{{ info.val }}" style="width:100%;padding:6px;">
  {% elif info.kind == 'number' %}
    <input name="{{ info.name }}" type="number" step="any" value="{{ info.val }}" style="width:100%;padding:6px;" {% if not info.nullable %}required{% endif %}>
  {% else %}
    <input name="{{ info.name }}" value="{{ info.val }}" style="width:100%;padding:6px;" {% if not info.nullable %}required{% endif %}>
  {% endif %}
  {% if info.nullable %}<span style="color:#888;font-size:0.85em;">optional</span>{% endif %}
</label>
{% endfor %}
<button style="padding:8px 20px;">Save</button>
<a href="{{ url_for('admin.browse_table', table_name=table_name) }}" style="margin-left:1rem;">Cancel</a>
</form>''', table_name=table_name, columns=columns)


@data_bp.route('/data/<table_name>/<int:id>/delete', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def delete_row(table_name, id):
    if table_name not in db.metadata.tables:
        return 'Table not found', 404
    table = db.metadata.tables[table_name]
    if 'id' not in table.columns:
        return 'Table has no id column', 400
    db.session.execute(table.delete().where(table.c.id == id))
    db.session.commit()
    return redirect(url_for('admin.browse_table', table_name=table_name))


@data_bp.route('/data/<table_name>/delete', methods=['POST'])
@admin_required
@csrf_protect
def delete_table(table_name):
    platform_tables = {'users', 'user_groups', 'groups', 'modules', 'routes',
                       'scripts', 'forms', 'scheduled_tasks', 'triggers',
                       'settings', 'uploads', 'chat_sessions', 'chat_messages',
                       'execution_logs', 'module_dependencies', 'module_versions',
                       'query_reports', 'incoming_emails', 'credentials'}
    if table_name in platform_tables:
        flash(f'Cannot drop platform table "{table_name}"', 'error')
        return redirect(url_for('admin.list_tables'))
    if table_name not in db.metadata.tables:
        flash(f'Table "{table_name}" not found', 'error')
        return redirect(url_for('admin.list_tables'))
    table = db.metadata.tables[table_name]
    bind = db.session.get_bind()
    table.drop(bind, checkfirst=True)
    db.metadata.remove(table)
    flash(f'Table "{table_name}" dropped')
    return redirect(url_for('admin.list_tables'))

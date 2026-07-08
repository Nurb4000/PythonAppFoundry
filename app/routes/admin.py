from flask import Blueprint, request, redirect, url_for, render_template_string, abort, jsonify, flash, Response
from flask_login import login_required, current_user
from sqlalchemy import func, inspect as sa_inspect
from sqlalchemy import Table, MetaData
import csv, io

from app import db
from app.models import User, Module, Route, Script, Form, ScheduledTask, Trigger, ChatSession, ChatMessage, Upload, Setting, Group, ExecutionLog, ModuleVersion

admin_bp = Blueprint('admin', __name__)

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


def admin_required(f):
    from functools import wraps
    @wraps(f)
    @login_required
    def wrapper(*a, **kw):
        if current_user.role != 'admin':
            abort(403)
        return f(*a, **kw)
    return wrapper


def developer_or_admin_required(f):
    from functools import wraps
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
        user_id = current_user.id if current_user.is_authenticated else None
        if comment is None:
            comment = 'Auto-saved'
        _create_version(module_id, comment=comment, user_id=user_id)
    except Exception:
        pass  # Silently fail - versioning is not critical


class AttrProxy:
    def __init__(self, obj):
        self._obj = obj
    def __getattr__(self, name):
        if name == '_module_name':
            mod = getattr(self._obj, 'module', None)
            return getattr(mod, 'name', '') if mod else ''
        val = getattr(self._obj, name, '')
        if hasattr(val, '__call__'):
            return ''
        return str(val or '')


def render_admin(title, content_template, **kwargs):
    content = render_template_string(content_template, **kwargs)
    return render_template_string(ADMIN_TEMPLATE, title=title, content=content)


def list_view(model, name_plural, columns, edit_endpoint, new_endpoint, show_view=False, has_module=False):
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
        new_url=url_for(new_endpoint),
        edit_url=url_for(edit_endpoint, id=0).rsplit('/', 1)[0],
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


# ── Modules ──

@admin_bp.route('/modules')
@developer_or_admin_required
def list_modules():
    sort_col = request.args.get('sort', 'id')
    sort_order = request.args.get('order', 'asc')
    q = db.session.query(Module)
    sort_attr = getattr(Module, sort_col, None)
    if sort_attr is not None:
        q = q.order_by(sort_attr.desc() if sort_order == 'desc' else sort_attr.asc())
    else:
        q = q.order_by(Module.id)
    rows = q.all()

    # Pre-calculate dependency counts for each module
    from app.services.dependencies import get_dependency_count
    dep_counts = {}
    for m in rows:
        dep_counts[m.id] = get_dependency_count(m.id)

    if request.args.get('format') == 'csv':
        return _export_csv('modules', ['id', 'name', 'slug', 'version', 'author', 'enabled', 'created_at'], rows, False)

    content = render_template_string(MODULE_LIST_TEMPLATE,
        modules=rows,
        dep_counts=dep_counts,
        new_url=url_for('admin.new_module'),
        edit_url=url_for('admin.edit_module', id=0).rsplit('/', 1)[0],
        export_url=url_for('api.api_export', slug='').rsplit('/', 1)[0],
        chat_url=url_for('chat.refine_module', id=0).rsplit('/', 1)[0],
        delete_url=url_for('admin.delete_module', id=0).rsplit('/', 1)[0],
        bpmn_url=url_for('bpmn.designer', module_id=0).replace('module_id=0', 'module_id='),
        sort_col=sort_col,
        sort_order=sort_order,
    )
    return render_template_string(ADMIN_TEMPLATE,
        title='Modules', content=content)

MODULE_LIST_TEMPLATE = '''<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ new_url }}">+ New</a>
  <a href="?format=csv{% if sort_col %}&sort={{ sort_col }}&order={{ sort_order }}{% endif %}" style="margin-left:auto;">Export CSV</a>
</div>
<div class="table-wrap">
<table>
<thead><tr>
  <th><a href="?sort=id&order={% if sort_col == 'id' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">id{% if sort_col == 'id' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th><a href="?sort=name&order={% if sort_col == 'name' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">name{% if sort_col == 'name' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th><a href="?sort=slug&order={% if sort_col == 'slug' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">slug{% if sort_col == 'slug' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th><a href="?sort=version&order={% if sort_col == 'version' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">version{% if sort_col == 'version' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th><a href="?sort=author&order={% if sort_col == 'author' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">author{% if sort_col == 'author' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th><a href="?sort=enabled&order={% if sort_col == 'enabled' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">enabled{% if sort_col == 'enabled' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th>Deps</th>
  <th>Actions</th>
</tr></thead>
<tbody>
{% for m in modules %}
<tr>
<td>{{ m.id }}</td><td>{{ m.name }}</td><td>{{ m.slug }}</td><td>{{ m.version }}</td><td>{{ m.author }}</td><td>{{ m.enabled }}</td>
<td>
  {% if dep_counts[m.id] > 0 %}
    <span style="color:#d00;font-weight:bold;">{{ dep_counts[m.id] }}</span>
  {% else %}
    <span style="color:#999;">—</span>
  {% endif %}
</td>
<td>
  <a href="{{ edit_url }}/{{ m.id }}">Edit</a>
  <a href="{{ url_for('admin.list_versions', module_id=m.id) }}">Versions</a>
  <a href="{{ export_url }}/{{ m.slug }}">Export XML</a>
  <a href="{{ chat_url }}/{{ m.id }}">Refine in AI</a>
  {% if m.bpmn_xml %}<a href="{{ bpmn_url }}{{ m.id }}">BPMN</a>{% endif %}
  <form method="POST" action="{{ url_for('admin.scan_dependencies', module_id=m.id) }}" style="display:inline">
    <button type="submit" style="background:none;border:none;color:#06c;cursor:pointer;text-decoration:underline;padding:0;font:inherit" title="Scan for dependencies">Scan</button>
  </form>
  <form method="POST" action="{{ delete_url }}/{{ m.id }}" style="display:inline" onsubmit="var c=this.querySelector('[name=drop_tables]');return confirm('Delete module &quot;{{ m.name }}&quot;'+(c&&c.checked?' including its database tables?':' and all its routes, scripts, forms?'))">
    <label style="font-weight:normal;font-size:0.85em;"><input name="drop_tables" type="checkbox"> Drop tables</label>
    <button type="submit" style="background:none;border:none;color:#d00;cursor:pointer;text-decoration:underline;padding:0;font:inherit">Delete</button>
  </form>
</td></tr>
{% endfor %}
</tbody></table>
</div>'''

@admin_bp.route('/modules/new', methods=['GET', 'POST'])
@developer_or_admin_required
def new_module():
    if request.method == 'POST':
        m = Module(
            name=request.form['name'],
            slug=request.form['slug'],
            description=request.form.get('description', ''),
            version=request.form.get('version', '1.0.0'),
            author=request.form.get('author', ''),
        )
        db.session.add(m)
        db.session.commit()
        return redirect(url_for('admin.list_modules'))
    return render_admin('New Module', '''
<form method="POST">
<label>Name <input name="name" required></label>
<label>Slug <input name="slug" required></label>
<label>Description <textarea name="description"></textarea></label>
<label>Version <input name="version" value="1.0.0"></label>
<label>Author <input name="author"></label>
<button>Save</button>
</form>''')

@admin_bp.route('/modules/delete/<int:id>', methods=['GET', 'POST'])
@developer_or_admin_required
def delete_module(id):
    m = Module.query.get_or_404(id)
    name = m.name

    # Check for dependencies (other modules referencing this one)
    from app.services.dependencies import get_dependencies, has_dependencies
    dependencies = []
    if has_dependencies(id):
        dependencies = get_dependencies(id)

    # If there are dependencies and this is a GET request, show warning page
    if dependencies and request.method == 'GET':
        return render_admin(f'Delete Module: {name}', '''
<h2>Warning: Module Has Dependencies</h2>
<p>The module "<strong>{{ name }}</strong>" is referenced by other modules. Deleting it may break those modules.</p>

{% if dependencies %}
<div style="background:#fff3cd;border:1px solid #ffc107;padding:1rem;border-radius:6px;margin:1rem 0;">
<h3 style="margin-top:0;color:#856404;">Referenced by {{ dependencies|length }} module(s):</h3>
<ul style="margin:0.5rem 0;">
{% for dep in dependencies %}
<li><strong>{{ dep.source_module.name }}</strong> — {{ dep.dependency_type }} ({{ dep.reference_value }})</li>
{% endfor %}
</ul>
</div>
{% endif %}

<form method="POST" onsubmit="return confirm('Are you sure you want to delete this module? This cannot be undone.');">
  <div style="margin:1.5rem 0;">
    <label style="display:block;margin-bottom:0.5rem;"><input type="checkbox" name="drop_tables"> Also drop DynamicModel tables created by this module</label>
  </div>
  <div style="display:flex;gap:0.5rem;">
    <button type="submit" style="background:#dc3545;color:#fff;border:none;padding:0.5rem 1.5rem;border-radius:4px;cursor:pointer;">Yes, Delete Module</button>
    <a href="{{ url_for('admin.list_modules') }}" style="padding:0.5rem 1.5rem;color:#666;text-decoration:none;border:1px solid #ddd;border-radius:4px;">Cancel</a>
  </div>
</form>
''', name=name, dependencies=dependencies)

    # POST: Actually delete the module
    # Collect DynamicModel table names used by this module's scripts
    import re
    dyn_tables = set()
    for script in m.scripts.all():
        for match in re.finditer(r'DynamicModel\.get_or_create\s*\(\s*["\'](\w+)["\']', script.source_code):
            dyn_tables.add(match.group(1).lower())

    drop_tables = request.form.get('drop_tables') == 'on'
    if drop_tables and dyn_tables:
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(db.engine)
        existing = set(inspector.get_table_names())
        for tname in dyn_tables:
            if tname in existing:
                table = db.metadata.tables.get(tname)
                if table is not None:
                    table.drop(db.engine, checkfirst=True)
                    db.metadata.remove(table)

    m.routes.delete()
    m.scripts.delete()
    m.forms.delete()
    m.scheduled_tasks.delete()
    m.triggers.delete()
    db.session.delete(m)
    db.session.commit()
    tbl_msg = f' and dropped {len(dyn_tables)} table(s)' if drop_tables and dyn_tables else ''
    flash(f'Module "{name}" deleted{tbl_msg}')
    return redirect(url_for('admin.list_modules'))


@admin_bp.route('/modules/<int:module_id>/scan-dependencies', methods=['POST'])
@developer_or_admin_required
def scan_dependencies(module_id):
    """Scan a module's scripts for references to other modules and create dependency records."""
    m = db.session.get(Module, module_id)
    if not m:
        flash(f'Module #{module_id} not found', 'error')
        return redirect(url_for('admin.list_modules'))

    from app.services.dependencies import detect_dependencies
    try:
        deps_found = detect_dependencies(module_id)
        if deps_found:
            flash(f'Scanned "{m.name}": found {len(deps_found)} dependency reference(s)')
        else:
            flash(f'Scanned "{m.name}": no dependencies detected')
    except Exception as e:
        flash(f'Error scanning dependencies: {str(e)}', 'error')

    return redirect(url_for('admin.list_modules'))


@admin_bp.route('/modules/edit/<int:id>', methods=['GET', 'POST'])
@developer_or_admin_required
def edit_module(id):
    m = Module.query.get_or_404(id)
    if request.method == 'POST':
        m.name = request.form['name']
        m.slug = request.form['slug']
        m.description = request.form.get('description', '')
        m.version = request.form.get('version', '1.0.0')
        m.author = request.form.get('author', '')
        m.enabled = 'enabled' in request.form
        db.session.commit()
        flash(f'Module "{m.name}" saved')
        return redirect(url_for('admin.edit_module', id=id))
    from app.services.bundle import export_module
    full_xml = export_module(m)
    return render_admin('Edit Module', '''
<form method="POST">
  <div style="display:flex;gap:12px;flex-wrap:wrap;">
    <label style="flex:2;min-width:140px;">Name <input name="name" value="{{ m.name }}" required style="width:100%;"></label>
    <label style="flex:2;min-width:140px;">Slug <input name="slug" value="{{ m.slug }}" required style="width:100%;"></label>
    <label style="flex:1;min-width:80px;">Version <input name="version" value="{{ m.version }}" style="width:100%;"></label>
    <label style="flex:1;min-width:80px;">Author <input name="author" value="{{ m.author }}" style="width:100%;"></label>
  </div>
  <label style="display:block;margin-top:12px;">Description
    <textarea name="description" style="width:100%;min-height:100px;resize:vertical;">{{ m.description }}</textarea>
  </label>
  <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:12px;padding-top:12px;border-top:1px solid #ddd;">
    <label style="font-weight:normal;display:flex;align-items:center;gap:4px;font-size:13px;"><input name="enabled" type="checkbox" {% if m.enabled %}checked{% endif %}> Enabled</label>
    <button style="padding:6px 16px;">Save</button>
    <a href="{{ url_for('admin.list_routes', module_id=m.id) }}" class="btn">Edit Routes</a>
    <a href="{{ url_for('admin.list_scripts', module_id=m.id) }}" class="btn">Edit Scripts</a>
    <a href="{{ url_for('admin.list_forms', module_id=m.id) }}" class="btn">Edit Forms</a>
    <a href="{{ url_for('admin.list_triggers', module_id=m.id) }}" class="btn">Edit Triggers</a>
    <a href="{{ url_for('admin.list_tasks', module_id=m.id) }}" class="btn">Edit Tasks</a>
    <a href="{{ url_for('api.api_export', slug=m.slug) }}" class="btn">Export XML</a>
    <a href="{{ url_for('chat.refine_module', id=m.id) }}" class="btn">Refine in AI</a>
    <label style="font-weight:normal;cursor:pointer;" class="btn" onclick="document.getElementById('importFileInput').click()">Import XML
      <form method="POST" action="{{ url_for('admin.import_module_xml', id=m.id) }}" enctype="multipart/form-data" style="display:none;">
        <input type="file" name="file" accept=".xml" id="importFileInput" onchange="this.form.submit()">
      </form>
    </label>
    <form method="POST" action="{{ url_for('admin.delete_module', id=m.id) }}" style="display:inline" onsubmit="var c=this.querySelector('[name=drop_tables]');return confirm('Delete module &quot;{{ m.name }}&quot;'+(c&&c.checked?' including its database tables?':' and all its routes, scripts, forms?'))">
      <label style="font-weight:normal;font-size:0.85em;cursor:pointer;"><input name="drop_tables" type="checkbox"> Drop tables</label>
      <button type="submit" style="background:none;border:none;color:#d00;cursor:pointer;text-decoration:underline;padding:0;font:inherit">Delete</button>
    </form>
  </div>
</form>
<details style="margin-top:1rem;"><summary>XML Preview</summary>
<pre style="background:#f4f4f4;padding:0.5rem;overflow:auto;font-size:0.85rem;max-height:400px;white-space:pre;word-wrap:normal;">{{ full_xml }}</pre>
</details>
''', m=m, full_xml=full_xml)


@admin_bp.route('/modules/import_xml/<int:id>', methods=['POST'])
@developer_or_admin_required
def import_module_xml(id):
    m = Module.query.get_or_404(id)
    if 'file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('admin.edit_module', id=id))
    xml_file = request.files['file']
    if not xml_file.filename:
        flash('Empty filename', 'error')
        return redirect(url_for('admin.edit_module', id=id))
    try:
        from app.services.bundle import import_module
        import_module(xml_file.read().decode('utf-8'), update_existing=True, module_id=id)
        create_auto_version(id)
        flash(f'Module "{m.name}" updated from XML')
    except Exception as e:
        flash(f'Import failed: {e}', 'error')
    return redirect(url_for('admin.edit_module', id=id))


# ── Module Versions ──

@admin_bp.route('/modules/<int:module_id>/versions')
@developer_or_admin_required
def list_versions(module_id):
    m = Module.query.get_or_404(module_id)
    versions = m.versions.order_by(ModuleVersion.created_at.desc()).all()
    return render_admin(f'Versions - {m.name}', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.edit_module', id=m.id) }}">Back to Module</a>
  <form method="POST" action="{{ url_for('admin.create_version', module_id=m.id) }}" style="display:inline;flex:1;max-width:400px;">
    <input type="text" name="comment" placeholder="Version comment (e.g., 'Added contact form')" style="flex:1;padding:6px 12px;border:1px solid #ddd;border-radius:4px;">
    <button type="submit" style="padding:6px 16px;background:#2563eb;color:white;border:none;border-radius:4px;cursor:pointer;">Create Version</button>
  </form>
</div>
<div class="table-wrap">
<table>
<thead><tr>
  <th>Version</th>
  <th>Comment</th>
  <th>Author</th>
  <th>Date</th>
  <th>Status</th>
  <th>Actions</th>
</tr></thead>
<tbody>
{% for v in versions %}
<tr>
  <td><strong>{{ v.version_number }}</strong></td>
  <td>{{ v.comment or '-' }}</td>
  <td>{{ v.created_by.username if v.created_by else 'System' }}</td>
  <td style="white-space:nowrap;">{{ v.created_at|localtime }}</td>
  <td>{% if v.is_current %}<span style="color:#16a34a;font-weight:bold;">Current</span>{% else %}<span style="color:#888;">Past</span>{% endif %}</td>
  <td>
    {% if not v.is_current %}
    <form method="POST" action="{{ url_for('admin.restore_version', version_id=v.id) }}" style="display:inline" onsubmit="return confirm('Restore module to version {{ v.version_number }}? This will replace the current state.')">
      <button type="submit" style="background:none;border:none;color:#2563eb;cursor:pointer;text-decoration:underline;padding:0;font:inherit;">Restore</button>
    </form>
    {% endif %}
    |
    {% if loop.length > 1 %}
    <a href="{{ url_for('admin.diff_version', version_id=v.id) }}">Diff</a>
    {% endif %}
  </td>
</tr>
{% endfor %}
</tbody></table>
</div>
{% if not versions %}
<p style="color:#888;">No versions created yet. Create a version to start tracking changes.</p>
{% endif %}
''', m=m, versions=versions)


@admin_bp.route('/modules/<int:module_id>/versions/create', methods=['POST'])
@developer_or_admin_required
def create_version(module_id):
    m = Module.query.get_or_404(module_id)
    comment = request.form.get('comment', '')
    try:
        from app.services.versioning import create_version as _create_version
        _create_version(module_id, comment=comment, user_id=current_user.id if current_user.is_authenticated else None)
        flash(f'Version created for "{m.name}"')
    except Exception as e:
        flash(f'Failed to create version: {e}', 'error')
    return redirect(url_for('admin.list_versions', module_id=module_id))


@admin_bp.route('/modules/versions/<int:version_id>/restore', methods=['POST'])
@developer_or_admin_required
def restore_version(version_id):
    v = ModuleVersion.query.get_or_404(version_id)
    try:
        from app.services.versioning import restore_version as _restore_version
        _restore_version(version_id)
        flash(f'Restored "{v.module.name}" to version {v.version_number}')
    except Exception as e:
        flash(f'Failed to restore version: {e}', 'error')
    return redirect(url_for('admin.list_versions', module_id=v.module_id))


@admin_bp.route('/modules/versions/<int:version_id>/diff')
@developer_or_admin_required
def diff_version(version_id):
    v = ModuleVersion.query.get_or_404(version_id)
    versions = v.module.versions.order_by(ModuleVersion.created_at.desc()).all()
    
    # Find the previous version for diffing
    v_index = next((i for i, ver in enumerate(versions) if ver.id == version_id), None)
    prev_version = None
    if v_index is not None and v_index + 1 < len(versions):
        prev_version = versions[v_index + 1]
    
    diff_text = ''
    if prev_version:
        try:
            from app.services.versioning import diff_versions as _diff_versions
            diff_text = _diff_versions(version_id, prev_version.id)
        except Exception as e:
            diff_text = f'Error generating diff: {e}'
    
    return render_admin(f'Diff - Version {v.version_number}', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.list_versions', module_id=m.id) }}">Back to Versions</a>
</div>
<h2>Diff: Version {{ v.version_number }}</h2>
{% if prev_version %}
<p style="color:#888;margin-bottom:1rem;">Comparing against version {{ prev_version.version_number }} ({{ prev_version.created_at|localtime }})</p>
{% endif %}
<div class="table-wrap">
<pre style="background:#f4f4f4;padding:1rem;overflow:auto;font-size:0.85rem;max-height:600px;white-space:pre-wrap;word-wrap:break-word;">{{ diff_text or 'No changes to display.' }}</pre>
</div>
{% if not diff_text %}
<p style="color:#888;">This is the first version, or unable to generate diff.</p>
{% endif %}
''', m=v.module, v=v, prev_version=prev_version, diff_text=diff_text)


# ── Routes ──

@admin_bp.route('/routes')
@developer_or_admin_required
def list_routes():
    return list_view(Route, 'routes',
        ['id', 'slug', 'methods', 'auth_required', 'title'],
        'admin.edit_route', 'admin.new_route', show_view=True, has_module=True)

@admin_bp.route('/routes/new', methods=['GET', 'POST'])
@developer_or_admin_required
def new_route():
    modules = db.session.query(Module).all()
    scripts = db.session.query(Script).all()
    forms = db.session.query(Form).all()
    if request.method == 'POST':
        slug = request.form['slug']
        existing = db.session.query(Route).filter_by(slug=slug).first()
        if existing:
            flash(f'Route slug "{slug}" already in use by module "{existing.module.name}"')
            return redirect(url_for('admin.list_routes'))
        r = Route(
            module_id=int(request.form['module_id']),
            slug=slug,
            methods=request.form.get('methods', 'GET'),
            script_id=int(request.form['script_id']) if request.form.get('script_id') else None,
            form_id=int(request.form['form_id']) if request.form.get('form_id') else None,
            auth_required='auth_required' in request.form,
            title=request.form.get('title', ''),
        )
        db.session.add(r)
        db.session.commit()
        return redirect(url_for('admin.list_routes'))
    return render_admin('New Route', '''
<form method="POST">
<label>Slug <input name="slug" required></label>
<label>Methods <input name="methods" value="GET"></label>
<label>Module <select name="module_id">{% for m in modules %}<option value="{{ m.id }}">{{ m.name }}</option>{% endfor %}</select></label>
<label>Script <select name="script_id"><option value="">-- none --</option>{% for s in scripts %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}</select></label>
<label>Form <select name="form_id"><option value="">-- none --</option>{% for f in forms %}<option value="{{ f.id }}">{{ f.name }}</option>{% endfor %}</select></label>
<label><input name="auth_required" type="checkbox"> Auth Required</label>
<label>Title <input name="title"></label>
<button>Save</button>
</form>''', modules=modules, scripts=scripts, forms=forms)

@admin_bp.route('/routes/edit/<int:id>', methods=['GET', 'POST'])
@developer_or_admin_required
def edit_route(id):
    r = Route.query.get_or_404(id)
    modules = db.session.query(Module).all()
    scripts = db.session.query(Script).all()
    forms = db.session.query(Form).all()
    if request.method == 'POST':
        r.module_id = int(request.form['module_id'])
        slug = request.form['slug']
        existing = db.session.query(Route).filter(Route.slug == slug, Route.id != id).first()
        if existing:
            flash(f'Route slug "{slug}" already in use by module "{existing.module.name}"')
            return redirect(url_for('admin.list_routes'))
        r.slug = slug
        r.methods = request.form.get('methods', 'GET')
        r.script_id = int(request.form['script_id']) if request.form.get('script_id') else None
        r.form_id = int(request.form['form_id']) if request.form.get('form_id') else None
        r.auth_required = 'auth_required' in request.form
        r.title = request.form.get('title', '')
        db.session.commit()
        return redirect(url_for('admin.list_routes'))
    return render_admin('Edit Route', '''
<form method="POST">
<label>Slug <input name="slug" value="{{ r.slug }}" required></label>
<label>Methods <input name="methods" value="{{ r.methods }}"></label>
<label>Module <select name="module_id">{% for m in modules %}<option value="{{ m.id }}" {% if m.id == r.module_id %}selected{% endif %}>{{ m.name }}</option>{% endfor %}</select></label>
<label>Script <select name="script_id"><option value="">-- none --</option>{% for s in scripts %}<option value="{{ s.id }}" {% if s.id == r.script_id %}selected{% endif %}>{{ s.name }}</option>{% endfor %}</select></label>
<label>Form <select name="form_id"><option value="">-- none --</option>{% for f in forms %}<option value="{{ f.id }}" {% if f.id == r.form_id %}selected{% endif %}>{{ f.name }}</option>{% endfor %}</select></label>
<label><input name="auth_required" type="checkbox" {% if r.auth_required %}checked{% endif %}> Auth Required</label>
<label>Title <input name="title" value="{{ r.title }}"></label>
<button>Save</button>
</form>''', r=r, modules=modules, scripts=scripts, forms=forms)

# ── Scripts ──

@admin_bp.route('/scripts')
@developer_or_admin_required
def list_scripts():
    return list_view(Script, 'scripts',
        ['id', 'name', 'language'],
        'admin.edit_script', 'admin.new_script', has_module=True)

@admin_bp.route('/scripts/new', methods=['GET', 'POST'])
@developer_or_admin_required
def new_script():
    modules = db.session.query(Module).all()
    if request.method == 'POST':
        s = Script(
            module_id=int(request.form['module_id']),
            name=request.form['name'],
            language=request.form.get('language', 'python'),
            source_code=request.form.get('source_code', ''),
            description=request.form.get('description', ''),
        )
        db.session.add(s)
        db.session.commit()
        return redirect(url_for('admin.list_scripts'))
    return render_admin('New Script', '''
<form method="POST">
<label>Name <input name="name" required></label>
<label>Language <input name="language" value="python"></label>
<label>Module <select name="module_id">{% for m in modules %}<option value="{{ m.id }}">{{ m.name }}</option>{% endfor %}</select></label>
<label>Description <textarea name="description"></textarea></label>
<label>Source Code <textarea name="source_code" rows="15" style="width:100%;font-family:monospace"></textarea></label>
<button>Save</button>
</form>''', modules=modules)

@admin_bp.route('/scripts/edit/<int:id>', methods=['GET', 'POST'])
@developer_or_admin_required
def edit_script(id):
    s = Script.query.get_or_404(id)
    modules = db.session.query(Module).all()
    if request.method == 'POST':
        s.module_id = int(request.form['module_id'])
        s.name = request.form['name']
        s.language = request.form.get('language', 'python')
        s.source_code = request.form.get('source_code', '')
        s.description = request.form.get('description', '')
        db.session.commit()
        return redirect(url_for('admin.list_scripts'))
    return render_admin('Edit Script', '''
<form method="POST">
  <div style="display:flex;gap:12px;flex-wrap:wrap;">
    <label style="flex:2;min-width:140px;">Name <input name="name" value="{{ s.name }}" required style="width:100%;"></label>
    <label style="flex:1;min-width:100px;">Language <input name="language" value="{{ s.language }}" style="width:100%;"></label>
    <label style="flex:2;min-width:140px;">Module <select name="module_id" style="width:100%;">{% for m in modules %}<option value="{{ m.id }}" {% if m.id == s.module_id %}selected{% endif %}>{{ m.name }}</option>{% endfor %}</select></label>
  </div>
  <label style="display:block;margin-top:12px;">Description
    <textarea name="description" style="width:100%;min-height:80px;resize:vertical;">{{ s.description }}</textarea>
  </label>
  <label style="display:block;margin-top:12px;">Source Code
    <textarea name="source_code" rows="15" style="width:100%;font-family:monospace;">{{ s.source_code }}</textarea>
  </label>
  <button style="margin-top:12px;padding:6px 16px;">Save</button>
</form>''', s=s, modules=modules)

# ── Forms ──

@admin_bp.route('/forms')
@developer_or_admin_required
def list_forms():
    return list_view(Form, 'forms', ['id', 'name'],
        'admin.edit_form', 'admin.new_form', has_module=True)

@admin_bp.route('/forms/new', methods=['GET', 'POST'])
@developer_or_admin_required
def new_form():
    modules = db.session.query(Module).all()
    if request.method == 'POST':
        f = Form(
            module_id=int(request.form['module_id']),
            name=request.form['name'],
            schema_json=request.form.get('schema_json', '[]'),
        )
        db.session.add(f)
        db.session.commit()
        return redirect(url_for('admin.list_forms'))
    return render_admin('New Form', '''
<form method="POST">
<label>Name <input name="name" required></label>
<label>Module <select name="module_id">{% for m in modules %}<option value="{{ m.id }}">{{ m.name }}</option>{% endfor %}</select></label>
<label>Schema (JSON) <textarea name="schema_json" rows="10" style="width:100%;font-family:monospace">[{"name":"field1","type":"text","label":"Field 1","required":true}]</textarea></label>
<button>Save</button>
</form>''', modules=modules)

@admin_bp.route('/forms/edit/<int:id>', methods=['GET', 'POST'])
@developer_or_admin_required
def edit_form(id):
    f = Form.query.get_or_404(id)
    modules = db.session.query(Module).all()
    if request.method == 'POST':
        f.module_id = int(request.form['module_id'])
        f.name = request.form['name']
        f.schema_json = request.form.get('schema_json', '[]')
        db.session.commit()
        return redirect(url_for('admin.list_forms'))
    return render_admin('Edit Form', '''
<style>
.split-editor { display:grid; grid-template-columns:1fr 1fr; gap:1rem; margin-top:1rem; }
.split-pane { border:1px solid #ddd; border-radius:6px; overflow:hidden; }
.split-pane-header { background:#f8f9fa; padding:8px 12px; border-bottom:1px solid #ddd; font-weight:600; font-size:0.9em; }
.split-pane-content { padding:12px; height:400px; overflow-y:auto; }
.editor-textarea { width:100%; height:100%; border:none; resize:none; font-family:monospace; font-size:13px; line-height:1.5; outline:none; }
.preview-form { max-width:100%; }
.preview-error { color:#c00; padding:1rem; background:#fff5f5; border-radius:4px; }
@media (max-width: 768px) { .split-editor { grid-template-columns:1fr; } }
</style>
<form method="POST" id="formEditor">
<label>Name <input name="name" value="{{ f.name }}" required></label>
<label>Module <select name="module_id">{% for m in modules %}<option value="{{ m.id }}" {% if m.id == f.module_id %}selected{% endif %}>{{ m.name }}</option>{% endfor %}</select></label>
<div class="split-editor">
  <div class="split-pane">
    <div class="split-pane-header">Schema JSON</div>
    <div class="split-pane-content">
      <textarea name="schema_json" id="schemaEditor" class="editor-textarea" style="font-family:monospace;">{{ f.schema_json|safe }}</textarea>
    </div>
  </div>
  <div class="split-pane">
    <div class="split-pane-header">Live Preview</div>
    <div class="split-pane-content" id="previewPane">
      <div id="previewContent" class="preview-form"></div>
    </div>
  </div>
</div>
<div style="margin-top:1rem;">
<button>Save</button>
<a href="{{ url_for('admin.preview_form', id=f.id) }}" style="margin-left:1rem;">Full Preview Page</a>
</div>
</form>
<script>
(function() {
  var editor = document.getElementById('schemaEditor');
  var preview = document.getElementById('previewContent');
  var debounceTimer;
  
  console.log('Form editor init - editor:', !!editor, 'preview:', !!preview);
  if (!editor || !preview) {
    console.error('Form editor elements not found');
    return;
  }
  
  function renderPreview() {
    var json = editor.value.trim();
    console.log('Render preview - json length:', json.length, 'first 100:', json.substring(0, 100));
    
    if (!json || json === '[]') {
      preview.innerHTML = '<p style="color:#888;">No fields defined</p>';
      return;
    }
    
    try {
      var fields = JSON.parse(json);
      console.log('Parsed', fields.length, 'fields');
      if (!Array.isArray(fields)) throw new Error('Expected array');
      
      var html = '<form onsubmit="event.preventDefault(); alert(' + JSON.stringify('Form submitted (preview only)') + ');">';
      for (var i = 0; i < fields.length; i++) {
        var field = fields[i];
        var name = field.name || '';
        var label = field.label || name;
        var type = field.type || 'text';
        var required = field.required ? 'required' : '';
        var placeholder = field.placeholder || '';
        
        html += '<div style="margin-bottom:12px;">';
        html += '<label for="' + name + '" style="display:block;font-weight:600;margin-bottom:4px;">' + label + '</label>';
        
        if (type === 'textarea') {
          html += '<textarea id="' + name + '" name="' + name + '" ' + required + ' placeholder="' + placeholder + '" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;min-height:80px;"></textarea>';
        } else if (type === 'select') {
          var opts = (field.options || '').split(',').map(function(o) { return o.trim(); }).filter(Boolean);
          html += '<select id="' + name + '" name="' + name + '" ' + required + ' style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;">';
          for (var j = 0; j < opts.length; j++) {
            html += '<option value="' + opts[j] + '">' + opts[j] + '</option>';
          }
          html += '</select>';
        } else if (type === 'checkbox') {
          html += '<div style="margin-top:4px;"><input type="checkbox" id="' + name + '" name="' + name + '" ' + required + '> <span style="font-weight:normal;">' + label + '</span></div>';
        } else if (type === 'file') {
          html += '<input type="file" id="' + name + '" name="' + name + '" ' + required + ' style="width:100%;padding:6px;border:1px solid #ccc;border-radius:4px;">';
        } else {
          html += '<input type="' + type + '" id="' + name + '" name="' + name + '" ' + required + ' placeholder="' + placeholder + '" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;">';
        }
        html += '</div>';
      }
      html += '<button type="submit" style="padding:8px 16px;background:#080;color:#fff;border:none;border-radius:4px;cursor:pointer;">Submit</button>';
      html += '</form>';
      preview.innerHTML = html;
      console.log('Rendered preview with', fields.length, 'fields');
    } catch (e) {
      console.error('JSON parse error:', e);
      preview.innerHTML = '<div class="preview-error">Invalid JSON: ' + e.message + '</div>';
    }
  }
  
  editor.addEventListener('input', function() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(renderPreview, 300);
  });
  
  renderPreview();
})();
</script>''', f=f, modules=modules)

# ── Tasks ──

@admin_bp.route('/tasks')
@admin_required
def list_tasks():
    return list_view(ScheduledTask, 'scheduled tasks',
        ['id', 'name', 'cron_expression', 'enabled', 'last_run', 'next_run'],
        'admin.edit_task', 'admin.new_task', has_module=True)

@admin_bp.route('/tasks/new', methods=['GET', 'POST'])
@admin_required
def new_task():
    modules = db.session.query(Module).all()
    scripts = db.session.query(Script).all()
    if request.method == 'POST':
        t = ScheduledTask(
            module_id=int(request.form['module_id']),
            name=request.form['name'],
            script_id=int(request.form['script_id']),
            cron_expression=request.form['cron_expression'],
        )
        db.session.add(t)
        db.session.commit()
        return redirect(url_for('admin.list_tasks'))
    return render_admin('New Scheduled Task', '''
<form method="POST">
<label>Name <input name="name" required></label>
<label>Module <select name="module_id">{% for m in modules %}<option value="{{ m.id }}">{{ m.name }}</option>{% endfor %}</select></label>
<label>Script <select name="script_id">{% for s in scripts %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}</select></label>
<label>Cron Expression <input name="cron_expression" placeholder="*/5 * * * *" required></label>
<button>Save</button>
</form>''', modules=modules, scripts=scripts)

@admin_bp.route('/tasks/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_task(id):
    t = ScheduledTask.query.get_or_404(id)
    modules = db.session.query(Module).all()
    scripts = db.session.query(Script).all()
    if request.method == 'POST':
        t.module_id = int(request.form['module_id'])
        t.name = request.form['name']
        t.script_id = int(request.form['script_id'])
        t.cron_expression = request.form['cron_expression']
        t.enabled = 'enabled' in request.form
        db.session.commit()
        return redirect(url_for('admin.list_tasks'))
    return render_admin('Edit Scheduled Task', '''
<form method="POST">
<label>Name <input name="name" value="{{ t.name }}" required></label>
<label>Module <select name="module_id">{% for m in modules %}<option value="{{ m.id }}" {% if m.id == t.module_id %}selected{% endif %}>{{ m.name }}</option>{% endfor %}</select></label>
<label>Script <select name="script_id">{% for s in scripts %}<option value="{{ s.id }}" {% if s.id == t.script_id %}selected{% endif %}>{{ s.name }}</option>{% endfor %}</select></label>
<label>Cron Expression <input name="cron_expression" value="{{ t.cron_expression }}" required></label>
<label><input name="enabled" type="checkbox" {% if t.enabled %}checked{% endif %}> Enabled</label>
<button>Save</button>
</form>''', t=t, modules=modules, scripts=scripts)

# ── Triggers ──

@admin_bp.route('/triggers')
@admin_required
def list_triggers():
    return list_view(Trigger, 'triggers',
        ['id', 'name', 'event_type', 'target_table', 'enabled'],
        'admin.edit_trigger', 'admin.new_trigger', has_module=True)

@admin_bp.route('/triggers/new', methods=['GET', 'POST'])
@admin_required
def new_trigger():
    modules = db.session.query(Module).all()
    scripts = db.session.query(Script).all()
    if request.method == 'POST':
        tg = Trigger(
            module_id=int(request.form['module_id']),
            name=request.form['name'],
            event_type=request.form['event_type'],
            target_table=request.form['target_table'],
            script_id=int(request.form['script_id']),
        )
        db.session.add(tg)
        db.session.commit()
        return redirect(url_for('admin.list_triggers'))
    return render_admin('New Trigger', '''
<form method="POST">
<label>Name <input name="name" required></label>
<label>Module <select name="module_id">{% for m in modules %}<option value="{{ m.id }}">{{ m.name }}</option>{% endfor %}</select></label>
<label>Event Type <select name="event_type"><option>on_insert</option><option>on_update</option><option>on_delete</option><option>after_route</option><option>webhook</option></select></label>
<label>Target Table <input name="target_table" placeholder="table_name or webhook-slug"></label>
<label>Script <select name="script_id">{% for s in scripts %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}</select></label>
<button>Save</button>
</form>''', modules=modules, scripts=scripts)

@admin_bp.route('/triggers/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_trigger(id):
    tg = Trigger.query.get_or_404(id)
    modules = db.session.query(Module).all()
    scripts = db.session.query(Script).all()
    if request.method == 'POST':
        tg.module_id = int(request.form['module_id'])
        tg.name = request.form['name']
        tg.event_type = request.form['event_type']
        tg.target_table = request.form['target_table']
        tg.script_id = int(request.form['script_id'])
        tg.enabled = 'enabled' in request.form
        db.session.commit()
        return redirect(url_for('admin.list_triggers'))
    return render_admin('Edit Trigger', '''
<form method="POST">
<label>Name <input name="name" value="{{ tg.name }}" required></label>
<label>Module <select name="module_id">{% for m in modules %}<option value="{{ m.id }}" {% if m.id == tg.module_id %}selected{% endif %}>{{ m.name }}</option>{% endfor %}</select></label>
<label>Event Type <select name="event_type"><option {% if tg.event_type=='on_insert' %}selected{% endif %}>on_insert</option><option {% if tg.event_type=='on_update' %}selected{% endif %}>on_update</option><option {% if tg.event_type=='on_delete' %}selected{% endif %}>on_delete</option><option {% if tg.event_type=='after_route' %}selected{% endif %}>after_route</option><option {% if tg.event_type=='webhook' %}selected{% endif %}>webhook</option></select></label>
<label>Target Table <input name="target_table" value="{{ tg.target_table }}"></label>
<label>Script <select name="script_id">{% for s in scripts %}<option value="{{ s.id }}" {% if s.id == tg.script_id %}selected{% endif %}>{{ s.name }}</option>{% endfor %}</select></label>
<label><input name="enabled" type="checkbox" {% if tg.enabled %}checked{% endif %}> Enabled</label>
<button>Save</button>
</form>''', tg=tg, modules=modules, scripts=scripts)

# ── Users ──

@admin_bp.route('/users')
@admin_required
def list_users():
    sort_col = request.args.get('sort', 'created_at')
    sort_order = request.args.get('order', 'desc')
    q = db.session.query(User)
    sort_attr = getattr(User, sort_col, None)
    if sort_attr is not None:
        q = q.order_by(sort_attr.desc() if sort_order == 'desc' else sort_attr.asc())
    else:
        q = q.order_by(User.created_at.desc())
    users = q.all()
    pending = db.session.query(User).filter_by(is_approved=False).count()

    if request.args.get('format') == 'csv':
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['id', 'username', 'role', 'is_active', 'is_approved', 'created_at'])
        for u in users:
            w.writerow([u.id, u.username, u.role, u.is_active, u.is_approved, u.created_at])
        return Response(buf.getvalue(), mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=users.csv'})

    return render_admin('Users', '''
{% if pending %}
<div style="background:#fff3cd;padding:0.5rem;margin-bottom:1rem;">
  <strong>{{ pending }} pending approval</strong>
</div>
{% endif %}
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.new_user') }}">+ New User</a>
  <a href="?format=csv{% if sort_col %}&sort={{ sort_col }}&order={{ sort_order }}{% endif %}" style="margin-left:auto;">Export CSV</a>
</div>
<div class="table-wrap">
<table>
<thead><tr>
  <th><a href="?sort=id&order={% if sort_col == 'id' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">ID{% if sort_col == 'id' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th><a href="?sort=username&order={% if sort_col == 'username' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">Username{% if sort_col == 'username' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th><a href="?sort=role&order={% if sort_col == 'role' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">Role{% if sort_col == 'role' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th>Status</th>
  <th><a href="?sort=created_at&order={% if sort_col == 'created_at' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">Created{% if sort_col == 'created_at' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th></th>
</tr></thead>
<tbody>
{% for u in users %}
<tr>
  <td>{{ u.id }}</td>
  <td>{{ u.username }}</td>
  <td>{{ u.role }}</td>
  <td>
    {% if not u.is_approved %}<span style="color:#856404;">Pending</span>
    {% elif not u.is_active %}<span style="color:#c00;">Disabled</span>
    {% else %}<span style="color:#080;">Active</span>{% endif %}
  </td>
  <td>{{ u.created_at|localtime }}</td>
  <td>
    <a href="{{ url_for('admin.edit_user', id=u.id) }}">Edit</a>
    {% if not u.is_approved %}
      <form method="POST" action="{{ url_for('admin.approve_user', id=u.id) }}" style="display:inline">
        <button style="background:none;border:none;color:#080;cursor:pointer;text-decoration:underline;padding:0;font:inherit;font-size:0.9em;">Approve</button>
      </form>
    {% endif %}
    {% if u.is_active and u.is_approved %}
      <form method="POST" action="{{ url_for('admin.disable_user', id=u.id) }}" style="display:inline">
        <button style="background:none;border:none;color:#c00;cursor:pointer;text-decoration:underline;padding:0;font:inherit;font-size:0.9em;">Disable</button>
      </form>
    {% elif not u.is_active %}
      <form method="POST" action="{{ url_for('admin.enable_user', id=u.id) }}" style="display:inline">
        <button style="background:none;border:none;color:#080;cursor:pointer;text-decoration:underline;padding:0;font:inherit;font-size:0.9em;">Enable</button>
      </form>
    {% endif %}
  </td>
</tr>
{% endfor %}
</tbody></table>
</div>''', users=users, pending=pending, sort_col=sort_col, sort_order=sort_order)

@admin_bp.route('/users/<int:id>/approve', methods=['POST'])
@admin_required
def approve_user(id):
    u = db.session.get(User, id)
    if u:
        u.is_approved = True
        u.is_active = True
        db.session.commit()
    return redirect(url_for('admin.list_users'))

@admin_bp.route('/users/<int:id>/disable', methods=['POST'])
@admin_required
def disable_user(id):
    u = db.session.get(User, id)
    if u:
        u.is_active = False
        db.session.commit()
    return redirect(url_for('admin.list_users'))

@admin_bp.route('/users/<int:id>/enable', methods=['POST'])
@admin_required
def enable_user(id):
    u = db.session.get(User, id)
    if u:
        u.is_active = True
        db.session.commit()
    return redirect(url_for('admin.list_users'))

@admin_bp.route('/users/new', methods=['GET', 'POST'])
@admin_required
def new_user():
    import bcrypt
    if request.method == 'POST':
        pw = bcrypt.hashpw(request.form['password'].encode(), bcrypt.gensalt()).decode()
        u = User(
            username=request.form['username'],
            password_hash=pw,
            role=request.form.get('role', 'user'),
            is_approved='is_approved' in request.form,
            is_active='is_active' in request.form,
        )
        db.session.add(u)
        db.session.commit()
        return redirect(url_for('admin.list_users'))
    return render_admin('New User', '''
<form method="POST">
<label>Username <input name="username" required></label>
<label>Password <input name="password" type="password" required></label>
<label>Role <select name="role"><option>admin</option><option>developer</option><option>user</option></select></label>
<label><input name="is_approved" type="checkbox" checked> Approved</label>
<label><input name="is_active" type="checkbox" checked> Active</label>
<button>Save</button>
</form>''')

@admin_bp.route('/users/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_user(id):
    u = User.query.get_or_404(id)
    import bcrypt
    if request.method == 'POST':
        u.username = request.form['username']
        u.role = request.form.get('role', 'user')
        u.is_approved = 'is_approved' in request.form
        u.is_active = 'is_active' in request.form
        if request.form.get('password'):
            u.password_hash = bcrypt.hashpw(request.form['password'].encode(), bcrypt.gensalt()).decode()
        db.session.commit()
        return redirect(url_for('admin.list_users'))
    return render_admin('Edit User', '''
<form method="POST">
<label>Username <input name="username" value="{{ u.username }}" required></label>
<label>Password <input name="password" type="password" placeholder="Leave blank to keep"></label>
<label>Role <select name="role"><option {% if u.role=='admin' %}selected{% endif %}>admin</option><option {% if u.role=='developer' %}selected{% endif %}>developer</option><option {% if u.role=='user' %}selected{% endif %}>user</option></select></label>
<label><input name="is_approved" type="checkbox" {% if u.is_approved %}checked{% endif %}> Approved</label>
<label><input name="is_active" type="checkbox" {% if u.is_active %}checked{% endif %}> Active</label>
<button>Save</button>
</form>''', u=u)

# ── Data (table browser) ──

SENSITIVE_COLUMNS = {'password_hash', '_password'}

@admin_bp.route('/data')
@admin_required
def list_tables():
    import re
    # Build table→modules mapping from script source_code
    table_modules = {}
    platform_tables = {'users', 'user_groups', 'groups', 'modules', 'routes',
                       'scripts', 'forms', 'scheduled_tasks', 'triggers',
                       'settings', 'uploads', 'chat_sessions', 'chat_messages'}
    for t in platform_tables:
        table_modules[t] = 'Platform'

    scripts = db.session.query(Script).all()
    for s in scripts:
        mod = s.module
        mod_name = mod.name if mod else '?'
        for m in re.finditer(r'DynamicModel\.get_or_create\s*\(\s*["\'](\w+)["\']', s.source_code):
            tname = m.group(1).lower()
            if tname not in table_modules:
                table_modules[tname] = []
            if isinstance(table_modules.get(tname), list):
                if mod_name not in table_modules[tname]:
                    table_modules[tname].append(mod_name)
            elif table_modules.get(tname) != mod_name:
                table_modules[tname] = [table_modules[tname], mod_name]

    filter_module = request.args.get('module', '')
    sort_col = request.args.get('sort', 'name')
    sort_order = request.args.get('order', 'asc')

    tables = []
    # Collect all table names: from metadata AND from actual DB tables
    seen = set()
    inspector = sa_inspect(db.engine)
    for db_name in inspector.get_table_names():
        if db_name.startswith('sqlite_') or db_name == 'alembic_version':
            continue
        seen.add(db_name)
    # Also include metadata-only tables
    for name in db.metadata.tables:
        seen.add(name)

    for name in sorted(seen):
        # Get or reflect the table object
        table = db.metadata.tables.get(name)
        if table is None:
            table = Table(name, db.metadata, autoload_with=db.engine, extend_existing=True)
        try:
            pk_col = list(table.primary_key)[0] if table.primary_key else table.columns[0]
            count = db.session.execute(func.count(pk_col)).scalar()
        except Exception:
            count = '?'
        cols = [{'name': c.name, 'type': str(c.type), 'pk': c.primary_key, 'nullable': c.nullable}
                for c in table.columns if c.name not in SENSITIVE_COLUMNS]
        module_info = table_modules.get(name, '')
        if isinstance(module_info, list):
            module_info = ', '.join(module_info)
        if filter_module and module_info != filter_module:
            continue
        tables.append({'name': name, 'count': count, 'columns': cols, 'module': module_info,
                       'is_platform': name in platform_tables})

    # Sort
    rev = sort_order == 'desc'
    if sort_col == 'name':
        tables.sort(key=lambda t: t['name'], reverse=rev)
    elif sort_col == 'rows':
        tables.sort(key=lambda t: str(t['count']), reverse=rev)
    elif sort_col == 'module':
        tables.sort(key=lambda t: t['module'], reverse=rev)

    if request.args.get('format') == 'csv':
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
  <th><a href="?sort=name&order={% if sort_col == 'name' and sort_order == 'asc' %}desc{% else %}asc{% endif %}{% if filter_module %}&module={{ filter_module }}{% endif %}">Table{% if sort_col == 'name' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th><a href="?sort=rows&order={% if sort_col == 'rows' and sort_order == 'asc' %}desc{% else %}asc{% endif %}{% if filter_module %}&module={{ filter_module }}{% endif %}">Rows{% if sort_col == 'rows' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
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
      <button type="submit" style="background:none;border:none;color:#d00;cursor:pointer;text-decoration:underline;padding:0;font:inherit">Delete</button>
    </form>
    {% endif %}
  </td>
</tr>
{% endfor %}
</tbody></table>
</div>''', tables=tables, module_names=module_names, filter_module=filter_module,
       sort_col=sort_col, sort_order=sort_order)

@admin_bp.route('/data/<table_name>/')
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
    {{ row[c.name] if row[c.name] is not none else '<span style="color:#ccc;">NULL</span>' }}
  </td>
  {% endfor %}
  <td style="white-space:nowrap;">
    <a href="{{ url_for('admin.edit_row', table_name=table_name, id=row['id']) }}">Edit</a>
    <form method="POST" action="{{ url_for('admin.delete_row', table_name=table_name, id=row['id']) }}" style="display:inline" onsubmit="return confirm('Delete row {{ row['id'] }}?')">
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

@admin_bp.route('/data/<table_name>/new', methods=['GET', 'POST'])
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

@admin_bp.route('/data/<table_name>/<int:id>/edit', methods=['GET', 'POST'])
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

@admin_bp.route('/data/<table_name>/<int:id>/delete', methods=['POST'])
@developer_or_admin_required
def delete_row(table_name, id):
    if table_name not in db.metadata.tables:
        return 'Table not found', 404
    table = db.metadata.tables[table_name]
    if 'id' not in table.columns:
        return 'Table has no id column', 400
    db.session.execute(table.delete().where(table.c.id == id))
    db.session.commit()
    return redirect(url_for('admin.browse_table', table_name=table_name))

# ── Form preview ──

import json as _json

@admin_bp.route('/forms/<int:id>/preview')
@developer_or_admin_required
def preview_form(id):
    f = Form.query.get_or_404(id)
    try:
        fields = _json.loads(f.schema_json)
    except Exception:
        fields = []
    if not isinstance(fields, list):
        fields = []

    from flask import request as _flask_request
    html_parts = ['<form>']
    for field in fields:
        fname = field.get('name', '')
        flabel = field.get('label', fname)
        ftype = field.get('type', 'text')
        required = 'required' if field.get('required', False) else ''
        placeholder = field.get('placeholder', '')
        html_parts.append('<div style="margin-bottom:12px;">')
        html_parts.append('<label for="%s" style="display:block;font-weight:600;margin-bottom:4px;">%s</label>' % (fname, flabel))
        if ftype == 'textarea':
            html_parts.append('<textarea id="%s" name="%s" %s placeholder="%s" style="width:100%%;padding:8px;border:1px solid #ccc;border-radius:4px;min-height:100px;"></textarea>' % (fname, fname, required, placeholder))
        elif ftype == 'select':
            opts = field.get('options', '')
            html_parts.append('<select id="%s" name="%s" %s style="width:100%%;padding:8px;border:1px solid #ccc;border-radius:4px;">' % (fname, fname, required))
            for opt in opts.split(','):
                opt = opt.strip()
                html_parts.append('<option value="%s">%s</option>' % (opt, opt))
            html_parts.append('</select>')
        elif ftype == 'checkbox':
            html_parts.append('<input type="checkbox" id="%s" name="%s" %s style="margin-top:4px;">' % (fname, fname, required))
        elif ftype == 'file':
            html_parts.append('<input type="file" id="%s" name="%s" %s style="width:100%%;padding:6px;border:1px solid #ccc;border-radius:4px;">' % (fname, fname, required))
        else:
            html_parts.append('<input type="%s" id="%s" name="%s" %s placeholder="%s" style="width:100%%;padding:8px;border:1px solid #ccc;border-radius:4px;">' % (ftype, fname, fname, required, placeholder))
        html_parts.append('</div>')
    html_parts.append('</form>')

    return render_admin('Form Preview: ' + f.name, '''
<div style="margin-bottom:1rem;"><a href="{{ url_for('admin.edit_form', id=f.id) }}">&larr; Back to Edit</a></div>
<div style="max-width:500px;padding:1rem;border:1px solid #ddd;border-radius:8px;">
  {{ preview|safe }}
</div>
<div style="margin-top:1rem;padding:1rem;background:#f8f9fa;border-radius:8px;">
  <strong>Schema JSON:</strong>
  <pre style="white-space:pre-wrap;word-break:break-word;">{{ f.schema_json }}</pre>
</div>''', f=f, preview='\n'.join(html_parts))

# ── Uploads ──

import os as _os
from flask import current_app as _current_app
import secrets as _secrets

@admin_bp.route('/uploads')
@developer_or_admin_required
def list_uploads():
    # Get search/filter parameters
    search = request.args.get('search', '')
    file_type = request.args.get('type', '')

    query = db.session.query(Upload).order_by(Upload.created_at.desc())

    # Apply filters
    if search:
        query = query.filter(
            db.or_(
                Upload.original_name.ilike(f'%{search}%'),
                Upload.filename.ilike(f'%{search}%')
            )
        )

    if file_type:
        if file_type == 'image':
            query = query.filter(Upload.mime_type.like('image/%'))
        elif file_type == 'document':
            query = query.filter(Upload.mime_type.in_(['application/pdf', 'application/msword',
                                                      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                                                      'text/plain']))
        elif file_type == 'video':
            query = query.filter(Upload.mime_type.like('video/%'))
        elif file_type == 'audio':
            query = query.filter(Upload.mime_type.like('audio/%'))

    uploads = query.all()

    # Calculate total size
    total_size = sum(u.size for u in uploads)

    return render_admin('File Manager', '''
<div style="margin-bottom:1rem;display:flex;gap:1rem;align-items:center;flex-wrap:wrap;">
  <form method="POST" action="{{ url_for('admin.upload_file') }}" enctype="multipart/form-data" style="display:flex;gap:8px;align-items:center;flex:1;min-width:300px;">
    <input type="file" name="file" required style="flex:1;">
    <button type="submit" style="padding:6px 16px;background:#007bff;color:#fff;border:none;border-radius:4px;cursor:pointer;">Upload</button>
  </form>
  <form method="GET" style="display:flex;gap:8px;align-items:center;">
    <input type="text" name="search" placeholder="Search files..." value="{{ search }}" style="padding:6px 12px;border:1px solid #ddd;border-radius:4px;">
    <select name="type" style="padding:6px 12px;border:1px solid #ddd;border-radius:4px;">
      <option value="">All Types</option>
      <option value="image" {% if file_type == 'image' %}selected{% endif %}>Images</option>
      <option value="document" {% if file_type == 'document' %}selected{% endif %}>Documents</option>
      <option value="video" {% if file_type == 'video' %}selected{% endif %}>Videos</option>
      <option value="audio" {% if file_type == 'audio' %}selected{% endif %}>Audio</option>
    </select>
    <button type="submit" style="padding:6px 12px;background:#6c757d;color:#fff;border:none;border-radius:4px;cursor:pointer;">Filter</button>
    {% if search or file_type %}
      <a href="{{ url_for('admin.list_uploads') }}" style="padding:6px 12px;color:#007bff;text-decoration:none;">Clear</a>
    {% endif %}
  </form>
</div>

<div style="margin-bottom:1rem;padding:0.75rem;background:#f8f9fa;border-radius:4px;font-size:0.9rem;color:#666;">
  Showing {{ uploads|length }} file(s), total size: {{ '%0.2f MB'|format(total_size / 1048576) }}
</div>

<table>
<thead><tr>
  <th>Preview</th>
  <th>Original Name</th>
  <th>Type</th>
  <th>Size</th>
  <th>Uploaded</th>
  <th>Actions</th>
</tr></thead>
<tbody>
{% for u in uploads %}
<tr>
  <td>
    {% if 'image' in u.mime_type %}
      <img src="/uploads/{{ u.filename }}" style="width:50px;height:50px;object-fit:cover;border-radius:4px;" alt="{{ u.original_name }}">
    {% elif 'pdf' in u.mime_type %}
      <span style="font-size:1.5rem;">📄</span>
    {% elif 'video' in u.mime_type %}
      <span style="font-size:1.5rem;">🎥</span>
    {% elif 'audio' in u.mime_type %}
      <span style="font-size:1.5rem;">🎵</span>
    {% else %}
      <span style="font-size:1.5rem;">📎</span>
    {% endif %}
  </td>
  <td>
    <strong>{{ u.original_name }}</strong><br>
    <code style="font-size:0.8em;color:#666;">{{ u.filename }}</code>
  </td>
  <td>{{ u.mime_type }}</td>
  <td>{{ '%0.1f KB'|format(u.size / 1024) }}</td>
  <td>{{ u.created_at|localtime }}</td>
  <td>
    <a href="/uploads/{{ u.filename }}" target="_blank" style="margin-right:0.5rem;">View</a>
    <a href="/uploads/{{ u.filename }}" download style="margin-right:0.5rem;">Download</a>
    <form method="POST" action="{{ url_for('admin.delete_upload', id=u.id) }}" style="display:inline" onsubmit="return confirm('Delete {{ u.original_name }}?')">
      <button type="submit" style="background:none;border:none;color:#c00;cursor:pointer;text-decoration:underline;padding:0;font:inherit;font-size:0.9em;">Delete</button>
    </form>
  </td>
</tr>
{% endfor %}
</tbody></table>
{% if not uploads %}<p style="color:#888;">No files uploaded yet.</p>{% endif %}''', uploads=uploads, total_size=total_size, search=search, file_type=file_type)

@admin_bp.route('/uploads/upload', methods=['POST'])
@developer_or_admin_required
def upload_file():
    if 'file' not in request.files:
        flash('No file')
        return redirect(url_for('admin.list_uploads'))
    f = request.files['file']
    if not f.filename:
        flash('No file selected')
        return redirect(url_for('admin.list_uploads'))

    try:
        from app.services.file_upload import upload_file as upload_service
        upload = upload_service(f)
        flash(f'Uploaded {upload.original_name}')
    except Exception as e:
        flash(f'Upload failed: {str(e)}', 'error')

    return redirect(url_for('admin.list_uploads'))

@admin_bp.route('/uploads/<int:id>/delete', methods=['POST'])
@developer_or_admin_required
def delete_upload(id):
    upload = db.session.get(Upload, id)
    if not upload:
        abort(404)

    try:
        from app.services.file_upload import delete_upload_file
        delete_upload_file(upload)
        flash(f'Deleted {upload.original_name}')
    except Exception as e:
        flash(f'Delete failed: {str(e)}', 'error')

    return redirect(url_for('admin.list_uploads'))

# ── Groups ──

@admin_bp.route('/groups')
@admin_required
def list_groups():
    groups = db.session.query(Group).order_by(Group.name).all()
    return render_admin('Groups', '''
<a href="{{ url_for('admin.new_group') }}">+ New Group</a>
<table>
<thead><tr><th>ID</th><th>Name</th><th>Description</th><th>Members</th><th></th></tr></thead>
<tbody>
{% for g in groups %}
<tr>
  <td>{{ g.id }}</td>
  <td>{{ g.name }}</td>
  <td>{{ g.description[:60] if g.description else '' }}</td>
  <td>{{ g.users|length }}</td>
  <td>
    <a href="{{ url_for('admin.edit_group', id=g.id) }}">Edit</a>
    <form method="POST" action="{{ url_for('admin.delete_group', id=g.id) }}" style="display:inline" onsubmit="return confirm('Delete group {{ g.name }}?')">
      <button style="background:none;border:none;color:#c00;cursor:pointer;text-decoration:underline;padding:0;font:inherit;font-size:0.9em;">Delete</button>
    </form>
  </td>
</tr>
{% endfor %}
</tbody></table>''', groups=groups)

@admin_bp.route('/groups/new', methods=['GET', 'POST'])
@admin_required
def new_group():
    if request.method == 'POST':
        g = Group(name=request.form['name'], description=request.form.get('description', ''))
        db.session.add(g)
        db.session.commit()
        return redirect(url_for('admin.list_groups'))
    return render_admin('New Group', '''
<form method="POST">
<label>Name <input name="name" required></label>
<label>Description <textarea name="description" rows="3" style="width:100%;max-width:400px;"></textarea></label>
<button>Save</button>
</form>''')

@admin_bp.route('/groups/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_group(id):
    g = Group.query.get_or_404(id)
    users = db.session.query(User).order_by(User.username).all()
    if request.method == 'POST':
        g.name = request.form['name']
        g.description = request.form.get('description', '')
        selected_ids = [int(x) for x in request.form.getlist('user_ids')]
        g.users = [u for u in users if u.id in selected_ids]
        db.session.commit()
        return redirect(url_for('admin.list_groups'))
    selected_ids = {u.id for u in g.users}
    return render_admin('Edit Group', '''
<form method="POST">
<label>Name <input name="name" value="{{ g.name }}" required></label>
<label>Description <textarea name="description" rows="3" style="width:100%;max-width:400px;">{{ g.description }}</textarea></label>
<p><strong>Members</strong></p>
{% for u in users %}
<label style="display:block;font-weight:normal;">
  <input name="user_ids" type="checkbox" value="{{ u.id }}" {% if u.id in selected_ids %}checked{% endif %}>
  {{ u.username }} ({{ u.role }})
</label>
{% endfor %}
<button>Save</button>
</form>''', g=g, users=users, selected_ids=selected_ids)

@admin_bp.route('/groups/<int:id>/delete', methods=['POST'])
@admin_required
def delete_group(id):
    g = Group.query.get_or_404(id)
    db.session.delete(g)
    db.session.commit()
    return redirect(url_for('admin.list_groups'))


@admin_bp.route('/data/<table_name>/delete', methods=['POST'])
@admin_required
def delete_table(table_name):
    platform_tables = {'users', 'user_groups', 'groups', 'modules', 'routes',
                       'scripts', 'forms', 'scheduled_tasks', 'triggers',
                       'settings', 'uploads', 'chat_sessions', 'chat_messages'}
    if table_name in platform_tables:
        flash(f'Cannot drop platform table "{table_name}"', 'error')
        return redirect(url_for('admin.list_tables'))
    if table_name not in db.metadata.tables:
        flash(f'Table "{table_name}" not found', 'error')
        return redirect(url_for('admin.list_tables'))
    table = db.metadata.tables[table_name]
    table.drop(db.engine, checkfirst=True)
    db.metadata.remove(table)
    flash(f'Table "{table_name}" dropped')
    return redirect(url_for('admin.list_tables'))


# ── Settings ──

@admin_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def edit_settings():
    if request.method == 'POST':
        Setting.set('registration_disabled', 'true' if 'registration_disabled' in request.form else 'false')
        Setting.set('registration_require_approval', 'true' if 'registration_require_approval' in request.form else 'false')
        Setting.set('site_name', request.form.get('site_name', ''))
        Setting.set('llm_provider', request.form.get('llm_provider', 'llamacpp'))
        Setting.set('llm_endpoint', request.form.get('llm_endpoint', 'http://localhost:8080'))
        Setting.set('llm_api_key', request.form.get('llm_api_key', ''))
        Setting.set('llm_model', request.form.get('llm_model', ''))
        Setting.set('llm_temperature', request.form.get('llm_temperature', '0.3'))
        Setting.set('llm_max_tokens', request.form.get('llm_max_tokens', '4096'))
        Setting.set('llm_timeout', request.form.get('llm_timeout', '300'))
        Setting.set('smtp_host', request.form.get('smtp_host', 'localhost'))
        Setting.set('smtp_port', request.form.get('smtp_port', '587'))
        Setting.set('smtp_user', request.form.get('smtp_user', ''))
        Setting.set('smtp_password', request.form.get('smtp_password', ''))
        Setting.set('smtp_from', request.form.get('smtp_from', 'noreply@example.com'))
        Setting.set('smtp_tls', 'true' if 'smtp_tls' in request.form else 'false')
        flash('Settings saved')
        return redirect(url_for('admin.edit_settings'))
    disabled = Setting.get('registration_disabled', 'false') == 'true'
    require_approval = Setting.get('registration_require_approval', 'false') == 'true'
    site_name = Setting.get('site_name', '')
    llm_provider = Setting.get('llm_provider', 'llamacpp')
    llm_endpoint = Setting.get('llm_endpoint', 'http://localhost:8080')
    llm_api_key = Setting.get('llm_api_key', '')
    llm_model = Setting.get('llm_model', '')
    llm_temperature = Setting.get('llm_temperature', '0.3')
    llm_max_tokens = Setting.get('llm_max_tokens', '4096')
    llm_timeout = Setting.get('llm_timeout', '300')
    smtp_host = Setting.get('smtp_host', 'localhost')
    smtp_port = Setting.get('smtp_port', '587')
    smtp_user = Setting.get('smtp_user', '')
    smtp_password = Setting.get('smtp_password', '')
    smtp_from = Setting.get('smtp_from', 'noreply@example.com')
    smtp_tls = Setting.get('smtp_tls', 'true') == 'true'
    return render_admin('Settings', '''
<form method="POST">
<h3 style="margin-top:0;">Registration</h3>
<label style="display:block;margin-bottom:12px;">
  <strong>Site Name</strong><br>
  <input name="site_name" type="text" value="{{ site_name }}" style="padding:6px 10px;width:100%;max-width:400px;"><br>
  <span style="color:#888;font-size:0.85em;">Shown in the admin bar next to your role label.</span>
</label>
<label style="display:block;margin-bottom:12px;">
  <input name="registration_disabled" type="checkbox" {% if disabled %}checked{% endif %}>
  <strong>Disable registration</strong><br>
  <span style="color:#888;font-size:0.85em;">No new accounts can be created via the register page.</span>
</label>
<label style="display:block;margin-bottom:12px;">
  <input name="registration_require_approval" type="checkbox" {% if require_approval %}checked{% endif %}>
  <strong>Require approval for new users</strong><br>
  <span style="color:#888;font-size:0.85em;">Self-registered users must be approved by an admin before they can log in.</span>
</label>

<h3>LLM / AI Provider</h3>
<label style="display:block;margin-bottom:12px;">
  <strong>Provider</strong><br>
  <select name="llm_provider" style="padding:6px 10px;width:100%;max-width:400px;">
    <option value="llamacpp" {% if llm_provider == 'llamacpp' %}selected{% endif %}>llama.cpp (local)</option>
    <option value="openai" {% if llm_provider == 'openai' %}selected{% endif %}>OpenAI-compatible API</option>
  </select>
</label>
<label style="display:block;margin-bottom:12px;">
  <strong>API Endpoint URL</strong><br>
  <input name="llm_endpoint" type="text" value="{{ llm_endpoint }}" style="padding:6px 10px;width:100%;max-width:400px;"><br>
  <span style="color:#888;font-size:0.85em;">llama.cpp: <code>http://localhost:8080</code> &nbsp;|&nbsp; OpenAI: <code>https://api.openai.com</code></span>
</label>
<label style="display:block;margin-bottom:12px;">
  <strong>API Key</strong> <em style="color:#888;">(required for OpenAI)</em><br>
  <input name="llm_api_key" type="password" value="{{ llm_api_key }}" style="padding:6px 10px;width:100%;max-width:400px;">
</label>
<label style="display:block;margin-bottom:12px;">
  <strong>Model</strong> <em style="color:#888;">(OpenAI: e.g. <code>gpt-4o-mini</code>)</em><br>
  <input name="llm_model" type="text" value="{{ llm_model }}" style="padding:6px 10px;width:100%;max-width:400px;">
</label>
<label style="display:block;margin-bottom:12px;">
  <strong>Temperature</strong> &nbsp;<span style="color:#888;">0 – 2</span><br>
  <input name="llm_temperature" type="number" step="0.1" min="0" max="2" value="{{ llm_temperature }}" style="padding:6px 10px;width:120px;">
</label>
<label style="display:block;margin-bottom:12px;">
  <strong>Max Tokens</strong><br>
  <input name="llm_max_tokens" type="number" min="1" step="1" value="{{ llm_max_tokens }}" style="padding:6px 10px;width:120px;">
</label>
<label style="display:block;margin-bottom:12px;">
  <strong>Timeout (seconds)</strong><br>
  <input name="llm_timeout" type="number" min="1" step="1" value="{{ llm_timeout }}" style="padding:6px 10px;width:120px;">
</label>

<h3>SMTP / Email</h3>
<label style="display:block;margin-bottom:12px;">
  <strong>SMTP Host</strong><br>
  <input name="smtp_host" type="text" value="{{ smtp_host }}" style="padding:6px 10px;width:100%;max-width:400px;">
</label>
<label style="display:block;margin-bottom:12px;">
  <strong>SMTP Port</strong><br>
  <input name="smtp_port" type="number" min="1" step="1" value="{{ smtp_port }}" style="padding:6px 10px;width:120px;">
</label>
<label style="display:block;margin-bottom:12px;">
  <strong>Username</strong><br>
  <input name="smtp_user" type="text" value="{{ smtp_user }}" style="padding:6px 10px;width:100%;max-width:400px;">
</label>
<label style="display:block;margin-bottom:12px;">
  <strong>Password</strong><br>
  <input name="smtp_password" type="password" value="{{ smtp_password }}" style="padding:6px 10px;width:100%;max-width:400px;">
</label>
<label style="display:block;margin-bottom:12px;">
  <strong>From Address</strong><br>
  <input name="smtp_from" type="text" value="{{ smtp_from }}" style="padding:6px 10px;width:100%;max-width:400px;">
</label>
<label style="display:block;margin-bottom:12px;">
  <input name="smtp_tls" type="checkbox" {% if smtp_tls %}checked{% endif %}>
  <strong>Use TLS</strong>
</label>
<div style="margin-top:16px;">
  <button style="padding:8px 20px;">Save All Settings</button>
</div>
</form>''',
        disabled=disabled, require_approval=require_approval,
        site_name=site_name,
        llm_provider=llm_provider, llm_endpoint=llm_endpoint,
        llm_api_key=llm_api_key, llm_model=llm_model,
        llm_temperature=llm_temperature, llm_max_tokens=llm_max_tokens,
        llm_timeout=llm_timeout,
        smtp_host=smtp_host, smtp_port=smtp_port,
        smtp_user=smtp_user, smtp_password=smtp_password,
        smtp_from=smtp_from, smtp_tls=smtp_tls)


# ── Dashboard ──

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    import platform as _platform
    import sys as _sys
    import time as _time
    from datetime import timedelta

    app_start_time = getattr(dashboard, '_start_time', None)
    if app_start_time is None:
        dashboard._start_time = _time.time()
        app_start_time = _time.time()
    uptime_seconds = _time.time() - app_start_time

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
                       'execution_logs'}
    table_stats = []
    inspector = _sa_inspect(db.engine)
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

    content = render_template_string(DASHBOARD_TEMPLATE,
        python_version=_platform.python_version(),
        flask_version='3.0',
        sqlite_version=_platform.python_version(),
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


DASHBOARD_TEMPLATE = '''
<style>
.dash-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
.dash-card { background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 6px; padding: 1rem; }
.dash-card h3 { margin: 0 0 0.5rem 0; font-size: 0.8em; text-transform: uppercase; color: #666; letter-spacing: 0.5px; }
.dash-card .value { font-size: 1.8em; font-weight: 700; color: #1a1a2e; }
.dash-card .sub { font-size: 0.8em; color: #888; margin-top: 4px; }
.dash-section { margin-bottom: 1.5rem; }
.dash-section h2 { font-size: 1.1em; margin: 0 0 0.75rem 0; padding-bottom: 0.5rem; border-bottom: 2px solid #e94560; }
.status-ok { color: #080; }
.status-warn { color: #856404; }
.status-err { color: #c00; }
.log-success { color: #080; }
.log-error { color: #c00; }
.log-modal { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:9999; }
.log-modal-content { position:absolute; top:50%; left:50%; transform:translate(-50%, -50%); background:#fff; border-radius:8px; padding:1.5rem; max-width:600px; width:90%; max-height:80vh; overflow-y:auto; box-shadow:0 4px 20px rgba(0,0,0,0.3); }
.log-modal-content h3 { margin-top:0; border-bottom:1px solid #eee; padding-bottom:0.5rem; }
.log-modal-content pre { background:#f8f9fa; padding:1rem; border-radius:4px; overflow-x:auto; font-size:0.85em; max-height:400px; overflow-y:auto; white-space:pre-wrap; word-wrap:break-word; }
.log-modal-close { float:right; font-size:1.5em; cursor:pointer; color:#999; }
.log-modal-close:hover { color:#333; }
</style>
<script>
function showLogDetail(id, message) {
  var modal = document.getElementById('logModal');
  var content = document.getElementById('logContent');
  content.innerHTML = '<h3>Execution Log #' + id + '</h3><pre>' + (message || 'No details available.') + '</pre>';
  modal.style.display = 'block';
}
document.addEventListener('click', function(e) {
  if (e.target.id === 'logModal' || e.target.className === 'log-modal-close') {
    document.getElementById('logModal').style.display = 'none';
  }
});
</script>
<div id="logModal" class="log-modal"><div class="log-modal-content"><span class="log-modal-close">&times;</span><div id="logContent"></div></div></div>

<div class="dash-grid">
  <div class="dash-card"><h3>Modules</h3><div class="value">{{ total_modules }}</div><div class="sub">{{ enabled_modules }} enabled</div></div>
  <div class="dash-card"><h3>Routes</h3><div class="value">{{ total_routes }}</div></div>
  <div class="dash-card"><h3>Scripts</h3><div class="value">{{ total_scripts }}</div></div>
  <div class="dash-card"><h3>Forms</h3><div class="value">{{ total_forms }}</div></div>
  <div class="dash-card"><h3>Scheduled Tasks</h3><div class="value">{{ total_tasks }}</div><div class="sub">{{ enabled_tasks }} enabled</div></div>
  <div class="dash-card"><h3>Triggers</h3><div class="value">{{ total_triggers }}</div><div class="sub">{{ enabled_triggers }} enabled</div></div>
  <div class="dash-card"><h3>Users</h3><div class="value">{{ total_users }}</div><div class="sub">{{ active_users }} active{% if pending_users %}, {{ pending_users }} pending{% endif %}</div></div>
  <div class="dash-card"><h3>Uploads</h3><div class="value">{{ total_uploads }}</div><div class="sub">{{ '%0.1f MB'|format(uploads_size / 1048576) }}</div></div>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1.5rem;">
  <div class="dash-card">
    <h3>System</h3>
    <div style="font-size:0.9em;line-height:1.8;">
      Python: <strong>{{ python_version }}</strong><br>
      Flask: <strong>{{ flask_version }}</strong><br>
      Uptime: <strong>{{ '%d:%02d:%02d'|format((uptime // 3600)|int, (uptime % 3600 // 60)|int, (uptime % 60)|int) }}</strong>
    </div>
  </div>
  <div class="dash-card">
    <h3>Scheduler</h3>
    <div style="font-size:0.9em;line-height:1.8;">
      Status: <span class="{% if scheduler_info.running %}status-ok{% else %}status-err{% endif %}">{% if scheduler_info.running %}Running{% else %}Stopped{% endif %}</span><br>
      Jobs: <strong>{{ scheduler_info.jobs|length }}</strong>
      {% if scheduler_info.jobs %}
      <div style="margin-top:8px;max-height:120px;overflow-y:auto;">
        {% for job in scheduler_info.jobs %}
        <div style="padding:2px 0;font-size:0.85em;border-bottom:1px solid #eee;">
          <strong>{{ job.name }}</strong> &mdash; next: {{ job.next_run }}
          {% if job.misfired %}<span class="status-warn"> [MISFIRE]</span>{% endif %}
        </div>
        {% endfor %}
      </div>
      {% endif %}
    </div>
  </div>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1.5rem;">
  <div class="dash-section">
    <h2>Execution Logs (Recent)</h2>
    {% if recent_logs %}
    <table>
    <thead><tr><th>Time</th><th>Type</th><th>Name</th><th>Status</th><th>Duration</th><th>Details</th></tr></thead>
    <tbody>
    {% for log in recent_logs %}
    <tr>
      <td style="white-space:nowrap;font-size:0.85em;">{{ log.created_at|localtime }}</td>
      <td>{{ log.source_type }}</td>
      <td>{{ log.source_name }}</td>
      <td><span class="{% if log.status == 'success' %}log-success{% else %}log-error{% endif %}">{{ log.status|upper }}</span></td>
      <td>{{ log.duration_ms }}ms</td>
      <td>
        {% if log.error_message %}
        <button onclick="showLogDetail({{ log.id }}, {{ log.error_message[:500]|tojson }})" style="font-size:0.8em;padding:2px 8px;cursor:pointer;background:#fee;border:1px solid #c00;color:#c00;border-radius:3px;">View Error</button>
        {% elif log.stdout %}
        <button onclick="showLogDetail({{ log.id }}, {{ log.stdout[:500]|tojson }})" style="font-size:0.8em;padding:2px 8px;cursor:pointer;background:#efe;border:1px solid #080;color:#080;border-radius:3px;">View Output</button>
        {% else %}
        <span style="color:#888;font-size:0.85em;">—</span>
        {% endif %}
      </td>
    </tr>
    {% endfor %}
    </tbody></table>
    <div style="font-size:0.85em;color:#888;margin-top:8px;">
      Total: {{ total_logs }} &nbsp;|&nbsp; Success: <span class="log-success">{{ log_success }}</span> &nbsp;|&nbsp; Errors: <span class="log-error">{{ log_errors }}</span>
    </div>
    {% else %}
    <p style="color:#888;">No executions logged yet.</p>
    {% endif %}
  </div>

  <div class="dash-section">
    <h2>Database Tables</h2>
    <table>
    <thead><tr><th>Table</th><th>Rows</th></tr></thead>
    <tbody>
    {% for t in table_stats %}
    <tr>
      <td>{{ t.name }}{% if not t.is_platform %} <span style="color:#888;font-size:0.75em;">(dynamic)</span>{% endif %}</td>
      <td>{{ '%s'|format(t.count)|int }}</td>
    </tr>
    {% endfor %}
    </tbody></table>
    <div style="font-size:0.85em;color:#888;margin-top:8px;">Total rows across all tables: {{ '%d'|format(total_rows) }}</div>
  </div>
</div>

<div class="dash-section">
  <h2>Module Summary</h2>
  {% if module_summary %}
  <table>
  <thead><tr><th>Module</th><th>Version</th><th>Status</th><th>Routes</th><th>Scripts</th><th>Forms</th><th>Tasks</th><th>Triggers</th></tr></thead>
  <tbody>
  {% for ms in module_summary %}
  <tr>
    <td><strong>{{ ms.module.name }}</strong><br><span style="color:#888;font-size:0.8em;">{{ ms.module.slug }}</span></td>
    <td>{{ ms.module.version }}</td>
    <td>{% if ms.module.enabled %}<span class="status-ok">Enabled</span>{% else %}<span class="status-err">Disabled</span>{% endif %}</td>
    <td>{{ ms.route_count }}</td>
    <td>{{ ms.script_count }}</td>
    <td>{{ ms.form_count }}</td>
    <td>{{ ms.task_count }}</td>
    <td>{{ ms.trigger_count }}</td>
  </tr>
  {% endfor %}
  </tbody></table>
  {% else %}
  <p style="color:#888;">No modules created yet.</p>
  {% endif %}
</div>
'''

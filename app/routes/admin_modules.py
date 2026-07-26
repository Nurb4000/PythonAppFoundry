"""Admin routes for module management."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import developer_or_admin_required, admin_required, create_auto_version
from app import db
from app.models import Module, Route, Script, Form, ScheduledTask, Trigger, QueryReport

modules_bp = Blueprint('modules', __name__)


@modules_bp.route('/')
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

    from app.services.dependencies import get_dependency_count
    dep_counts = {}
    for m in rows:
        dep_counts[m.id] = get_dependency_count(m.id)

    if request.args.get('format') == 'csv':
        from app.services.admin_utils import _export_csv
        return _export_csv('modules', ['id', 'name', 'slug', 'version', 'author', 'enabled', 'created_at'], rows, False)

    content = render_template_string(MODULE_LIST_TEMPLATE,
        modules=rows, dep_counts=dep_counts,
        new_url=url_for('admin.new_module'),
        edit_url=url_for('admin.edit_module', id=0).rsplit('/', 1)[0],
        export_url=url_for('api.api_export', slug='').replace('//export', ''),
        chat_url=url_for('chat.refine_module', id=0).rsplit('/', 1)[0],
        delete_url=url_for('admin.delete_module', id=0).rsplit('/', 1)[0],
        bpmn_url=url_for('bpmn.designer', module_id=0).replace('module_id=0', 'module_id='),
        sort_col=sort_col, sort_order=sort_order)
    return render_template_string(ADMIN_TEMPLATE, title='Modules', content=content)


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
<td>{{ m.id }}</td>
<td>{{ m.name }}{% if m.is_system %}&nbsp;<span style="background:#6c757d;color:#fff;font-size:0.75em;padding:1px 6px;border-radius:3px;">system</span>{% endif %}</td>
<td>{{ m.slug }}</td><td>{{ m.version }}</td><td>{{ m.author }}</td><td>{{ m.enabled }}</td>
<td>{% if dep_counts[m.id] > 0 %}<a href="{{ url_for('admin.view_dependencies', module_id=m.id) }}" style="color:#d00;font-weight:bold;text-decoration:underline;">{{ dep_counts[m.id] }}</a>{% else %}<span style="color:#999;">—</span>{% endif %}</td>
<td>
  <a href="{{ edit_url }}/{{ m.id }}">Edit</a>
  <a href="{{ url_for('admin.list_versions', module_id=m.id) }}">Versions</a>
  <a href="{{ export_url }}/{{ m.slug }}/export">Export XML</a>
  <form method="POST" action="{{ url_for('admin.clone_module', id=m.id) }}" style="display:inline"><button type="submit" style="background:none;border:none;color:#06c;cursor:pointer;text-decoration:underline;padding:0;font:inherit" title="Clone module">Clone</button></form>
  <a href="{{ chat_url }}/{{ m.id }}">Refine in AI</a>
  {% if m.bpmn_xml %}<a href="{{ bpmn_url }}{{ m.id }}">BPMN</a>{% endif %}
  <form method="POST" action="{{ url_for('admin.scan_dependencies', module_id=m.id) }}" style="display:inline"><button type="submit" style="background:none;border:none;color:#06c;cursor:pointer;text-decoration:underline;padding:0;font:inherit" title="Scan for dependencies">Scan</button></form>
  {% if m.is_system %}
  <form method="POST" action="{{ url_for('admin.reset_system_module', id=m.id) }}" style="display:inline"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><button type="submit" style="background:none;border:none;color:#856404;cursor:pointer;text-decoration:underline;padding:0;font:inherit" onclick="return confirm('Reset &quot;{{ m.name }}&quot; to default?');">Reset</button></form>
  {% else %}
  <form method="POST" action="{{ delete_url }}/{{ m.id }}" style="display:inline" onsubmit="var c=this.querySelector('[name=drop_tables]');return confirm('Delete module &quot;{{ m.name }}&quot;'+(c&&c.checked?' including its database tables?':' and all its routes, scripts, forms?'))"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><label style="font-weight:normal;font-size:0.85em;"><input name="drop_tables" type="checkbox"> Drop tables</label><button type="submit" style="background:none;border:none;color:#d00;cursor:pointer;text-decoration:underline;padding:0;font:inherit">Delete</button></form>
  {% endif %}
</td></tr>
{% endfor %}
</tbody></table>
</div>'''


@modules_bp.route('/new', methods=['GET', 'POST'])
@developer_or_admin_required
@csrf_protect
def new_module():
    if request.method == 'POST':
        if 'import_xml' in request.files and request.files['import_xml'].filename:
            from app.services.bundle import import_module
            try:
                xml_file = request.files['import_xml']
                m = import_module(xml_file.read().decode('utf-8'))
                flash(f'Module "{m.name}" imported from XML')
                return redirect(url_for('admin.list_modules'))
            except Exception as e:
                flash(f'Import failed: {e}', 'error')
                return redirect(url_for('admin.list_modules'))
        slug = request.form['slug'].strip()
        valid, err = validate_slug(slug)
        if not valid:
            flash(f'Slug validation failed: {err}', 'error')
            return redirect(url_for('admin.new_module'))
        m = Module(name=request.form['name'], slug=slug, description=request.form.get('description', ''), version=request.form.get('version', '1.0.0'), author=request.form.get('author', ''))
        db.session.add(m)
        db.session.commit()
        return redirect(url_for('admin.list_modules'))
    return render_admin('New Module', NEW_MODULE_TEMPLATE)


NEW_MODULE_TEMPLATE = '''<details style="margin-bottom:1rem;"><summary style="cursor:pointer;color:#06c;">Import from XML</summary>
<div style="margin:0.5rem 0 0 1rem;">
<form id="importForm" enctype="multipart/form-data">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <label>XML file <input name="import_xml" type="file" accept=".xml" id="xmlFileInput"></label>
  <button type="button" onclick="previewImport()">Preview Import</button>
</form>
<div id="importPreview" style="margin-top:1rem;display:none;">
  <div style="background:#f4f4f4;border:1px solid #ddd;padding:1rem;border-radius:4px;">
    <h4 style="margin-top:0;">Import Preview</h4>
    <div id="previewContent"></div>
    <form method="POST" enctype="multipart/form-data" id="importSubmitForm" style="margin-top:1rem;">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <button type="submit">Confirm Import</button>
      <button type="button" onclick="document.getElementById('importPreview').style.display='none'" style="margin-left:0.5rem;background:#6c757d;color:#fff;border:none;padding:6px 16px;border-radius:4px;cursor:pointer;">Cancel</button>
    </form>
  </div>
</div>
</div>
</details>
<form method="POST">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>Name <input name="name" required></label>
<label>Slug <input name="slug" required></label>
<label>Description <textarea name="description"></textarea></label>
<label>Version <input name="version" value="1.0.0"></label>
<label>Author <input name="author"></label>
<button>Save</button>
</form>
<script>
function previewImport() {
  var fileInput = document.getElementById('xmlFileInput');
  if (!fileInput.files[0]) { alert('Please select a file first'); return; }
  var formData = new FormData();
  formData.append('import_xml', fileInput.files[0]);
  formData.append('csrf_token', document.querySelector('[name=csrf_token]').value);
  fetch('/__admin/import-preview', { method: 'POST', body: formData })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.error) { alert('Preview failed: ' + data.error); return; }
      var p = data.preview;
      var html = '<p><strong>' + p.name + '</strong> (slug: <code>' + p.slug + '</code>)';
      if (p.existing) html += ' <span style="color:#856404;">[Already exists - will update]</span>';
      html += '</p><ul><li>Scripts: ' + p.counts.scripts + '</li><li>Routes: ' + p.counts.routes + '</li><li>Forms: ' + p.counts.forms + '</li><li>Tasks: ' + p.counts.tasks + '</li><li>Triggers: ' + p.counts.triggers + '</li></ul>';
      document.getElementById('previewContent').innerHTML = html;
      document.getElementById('importPreview').style.display = 'block';
    })
    .catch(function(err) { alert('Request failed: ' + err.message); });
}
</script>'''


@modules_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
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
    return render_admin('Edit Module', EDIT_MODULE_TEMPLATE, m=m, full_xml=full_xml)


EDIT_MODULE_TEMPLATE = '''<form method="POST">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<div style="display:flex;gap:12px;flex-wrap:wrap;">
  <label style="flex:2;min-width:140px;">Name <input name="name" value="{{ m.name }}" required style="width:100%;"></label>
  <label style="flex:2;min-width:140px;">Slug <input name="slug" value="{{ m.slug }}" required style="width:100%;"></label>
  <label style="flex:1;min-width:80px;">Version <input name="version" value="{{ m.version }}" style="width:100%;"></label>
  <label style="flex:1;min-width:80px;">Author <input name="author" value="{{ m.author }}" style="width:100%;"></label>
</div>
<label style="display:block;margin-top:12px;">Description<textarea name="description" style="width:100%;min-height:100px;resize:vertical;">{{ m.description }}</textarea></label>
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
  <label style="font-weight:normal;cursor:pointer;" class="btn" onclick="document.getElementById('importFileInput').click()">Import XML<form method="POST" action="{{ url_for('admin.import_module_xml', id=m.id) }}" enctype="multipart/form-data" style="display:none;"><input type="file" name="file" accept=".xml" id="importFileInput" onchange="this.form.submit()"></form></label>
  <form method="POST" action="{{ url_for('admin.delete_module', id=m.id) }}" style="display:inline" onsubmit="var c=this.querySelector('[name=drop_tables]');return confirm('Delete module &quot;{{ m.name }}&quot;'+(c&&c.checked?' including its database tables?':' and all its routes, scripts, forms?'))"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><label style="font-weight:normal;font-size:0.85em;cursor:pointer;"><input name="drop_tables" type="checkbox"> Drop tables</label><button type="submit" style="background:none;border:none;color:#d00;cursor:pointer;text-decoration:underline;padding:0;font:inherit">Delete</button></form>
</div>
</form>
<details style="margin-top:1rem;"><summary>XML Preview</summary><pre style="background:#f4f4f4;padding:0.5rem;overflow:auto;font-size:0.85rem;max-height:400px;white-space:pre;word-wrap:normal;">{{ full_xml }}</pre></details>'''


@modules_bp.route('/delete/<int:id>', methods=['GET', 'POST'])
@developer_or_admin_required
@csrf_protect
def delete_module(id):
    m = Module.query.get_or_404(id)
    name = m.name
    if m.is_system:
        flash(f'Cannot delete system module "{name}". It is required by the platform.')
        return redirect(url_for('admin.list_modules'))
    from app.services.dependencies import get_dependencies, has_dependencies
    dependencies = []
    if has_dependencies(id):
        dependencies = get_dependencies(id)
    if dependencies and request.method == 'GET':
        return render_admin(f'Delete Module: {name}', DELETE_CONFIRM_TEMPLATE, name=name, dependencies=dependencies)
    from app.models import DynamicTableRegistry
    dyn_tables = {r.table_name for r in DynamicTableRegistry.query.filter_by(module_id=m.id)}
    if not dyn_tables:
        import re as _re
        bind = db.session.get_bind()
        _all_db_tables = set(db.engine_inspect(bind).get_table_names())
        for _s in m.scripts.all():
            for _match in _re.finditer(r'["\'](\w+)["\']', _s.source_code):
                _name = _match.group(1).lower()
                if _name in _all_db_tables:
                    dyn_tables.add(_name)
    drop_tables = request.form.get('drop_tables') == 'on'
    if drop_tables and dyn_tables:
        from sqlalchemy import inspect as sa_inspect
        bind = db.session.get_bind()
        inspector = sa_inspect(bind)
        existing = set(inspector.get_table_names())
        for tname in dyn_tables:
            if tname in existing:
                table = db.metadata.tables.get(tname)
                if table is not None:
                    table.drop(bind, checkfirst=True)
                    db.metadata.remove(table)
    DynamicTableRegistry.query.filter_by(module_id=m.id).delete()
    for route in m.routes.all(): db.session.delete(route)
    for script in m.scripts.all(): db.session.delete(script)
    for form in m.forms.all(): db.session.delete(form)
    for task in m.scheduled_tasks.all(): db.session.delete(task)
    for trigger in m.triggers.all(): db.session.delete(trigger)
    for credential in m.credentials.all(): db.session.delete(credential)
    for version in m.versions.all(): db.session.delete(version)
    for dep in m.dependencies_from.all(): db.session.delete(dep)
    for dep in m.dependencies_to.all(): db.session.delete(dep)
    db.session.delete(m)
    db.session.commit()
    from app.services.scheduler import refresh_tasks
    refresh_tasks()
    tbl_msg = f' and dropped {len(dyn_tables)} table(s)' if drop_tables and dyn_tables else ''
    flash(f'Module "{name}" deleted{tbl_msg}')
    return redirect(url_for('admin.list_modules'))


DELETE_CONFIRM_TEMPLATE = '''<h2>Warning: Module Has Dependencies</h2>
<p>The module "<strong>{{ name }}</strong>" is referenced by other modules. Deleting it may break those modules.</p>
{% if dependencies %}
<div style="background:#fff3cd;border:1px solid #ffc107;padding:1rem;border-radius:6px;margin:1rem 0;">
<h3 style="margin-top:0;color:#856404;">Referenced by {{ dependencies|length }} module(s):</h3>
<ul style="margin:0.5rem 0;">{% for dep in dependencies %}<li><strong>{{ dep.source_module.name }}</strong> — {{ dep.dependency_type }} ({{ dep.reference_value }})</li>{% endfor %}</ul>
</div>
{% endif %}
<form method="POST" onsubmit="return confirm('Are you sure you want to delete this module? This cannot be undone.');">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <div style="margin:1.5rem 0;"><label style="display:block;margin-bottom:0.5rem;"><input type="checkbox" name="drop_tables"> Also drop DynamicModel tables created by this module</label></div>
  <div style="display:flex;gap:0.5rem;">
    <button type="submit" style="background:#dc3545;color:#fff;border:none;padding:0.5rem 1.5rem;border-radius:4px;cursor:pointer;">Yes, Delete Module</button>
    <a href="{{ url_for('admin.list_modules') }}" style="padding:0.5rem 1.5rem;color:#666;text-decoration:none;border:1px solid #ddd;border-radius:4px;">Cancel</a>
  </div>
</form>'''


@modules_bp.route('/<int:id>/reset', methods=['POST'])
@admin_required
@csrf_protect
def reset_system_module(id):
    m = Module.query.get_or_404(id)
    if not m.is_system:
        flash(f'Module "{m.name}" is not a system module and cannot be reset.')
        return redirect(url_for('admin.list_modules'))
    for route in m.routes.all(): db.session.delete(route)
    for script in m.scripts.all(): db.session.delete(script)
    for form in m.forms.all(): db.session.delete(form)
    for task in m.scheduled_tasks.all(): db.session.delete(task)
    for trigger in m.triggers.all(): db.session.delete(trigger)
    for query in m.query_reports.all(): db.session.delete(query)
    for credential in m.credentials.all(): db.session.delete(credential)
    db.session.commit()
    from app.services.scheduler import refresh_tasks
    refresh_tasks()
    flash(f'System module "{m.name}" reset to default (empty).')
    return redirect(url_for('admin.list_modules'))


@modules_bp.route('/<int:module_id>/scan-dependencies', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def scan_dependencies(module_id):
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


@modules_bp.route('/<int:module_id>/dependencies')
@developer_or_admin_required
def view_dependencies(module_id):
    m = db.session.get(Module, module_id)
    if not m:
        flash(f'Module #{module_id} not found', 'error')
        return redirect(url_for('admin.list_modules'))
    from app.services.dependencies import get_dependencies
    deps = get_dependencies(module_id)
    return render_admin(f'Dependencies: {m.name}', DEPENDENCIES_TEMPLATE, m=m, deps=deps)


DEPENDENCIES_TEMPLATE = '''<h2>Module: {{ m.name }} <span style="font-weight:normal;font-size:0.9em;color:#888;">v{{ m.version }}</span></h2>
<p style="margin-top:-0.5rem;color:#666;">Slug: <code>{{ m.slug }}</code></p>
{% if deps %}
<div style="background:#fff3cd;border:1px solid #ffc107;padding:1rem;border-radius:6px;margin:1rem 0;">
<h3 style="margin-top:0;color:#856404;">Referenced by {{ deps|length }} module(s):</h3>
<p style="margin:0.5rem 0 1rem;color:#666;">These modules reference this module. Deleting it may break them.</p>
<table style="width:100%;border-collapse:collapse;">
<thead><tr><th style="text-align:left;padding:0.5rem;border-bottom:2px solid #e0c060;">Module</th><th style="text-align:left;padding:0.5rem;border-bottom:2px solid #e0c060;">Type</th><th style="text-align:left;padding:0.5rem;border-bottom:2px solid #e0c060;">Reference</th><th style="text-align:left;padding:0.5rem;border-bottom:2px solid #e0c060;">Detected</th></tr></thead>
<tbody>{% for dep in deps %}<tr><td style="padding:0.5rem;border-bottom:1px solid #f0d080;"><strong>{{ dep.source_module.name }}</strong></td><td style="padding:0.5rem;border-bottom:1px solid #f0d080;"><code>{{ dep.dependency_type }}</code></td><td style="padding:0.5rem;border-bottom:1px solid #f0d080;"><code>{{ dep.reference_value }}</code></td><td style="padding:0.5rem;border-bottom:1px solid #f0d080;">{{ dep.detected_at.strftime('%Y-%m-%d %H:%M') }}</td></tr>{% endfor %}</tbody></table>
</div>
{% else %}
<div style="background:#d4edda;border:1px solid #c3e6cb;padding:1rem;border-radius:6px;margin:1rem 0;"><p style="margin:0;color:#155724;">No modules currently depend on this module.</p></div>
{% endif %}
<p><a href="{{ url_for('admin.list_modules') }}">&larr; Back to modules</a></p>'''


@modules_bp.route('/clone/<int:id>', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def clone_module(id):
    m = Module.query.get_or_404(id)
    from app.services.bundle import export_module, import_module
    import xml.etree.ElementTree as ET
    xml_str = export_module(m)
    root = ET.fromstring(xml_str)
    root.set('name', m.name + ' (copy)')
    root.set('slug', m.slug + '-copy')
    try:
        new_m = import_module(ET.tostring(root, encoding='unicode', xml_declaration=True))
        flash(f'Module cloned as "{new_m.name}"')
    except Exception as e:
        flash(f'Clone failed: {e}', 'error')
    return redirect(url_for('admin.list_modules'))


@modules_bp.route('/import_xml/<int:id>', methods=['POST'])
@developer_or_admin_required
@csrf_protect
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

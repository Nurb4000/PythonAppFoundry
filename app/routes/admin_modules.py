"""Admin routes for module management."""
from flask import Blueprint, request, redirect, url_for, render_template, render_template_string, flash
from app.services.csrf import csrf_protect
from app.services.validation import validate_slug
from app.services.admin_utils import developer_or_admin_required, admin_required, create_auto_version, render_admin, ADMIN_TEMPLATE
from app.services.scheduler import refresh_tasks
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

    content = render_template('admin/modules/list.html',
        modules=rows, dep_counts=dep_counts,
        new_url=url_for('admin.modules.new_module'),
        edit_url=url_for('admin.modules.edit_module', id=0).rsplit('/', 1)[0],
        export_url=url_for('api.api_export', slug='').replace('//export', ''),
        chat_url=url_for('chat.refine_module', id=0).rsplit('/', 1)[0],
        delete_url=url_for('admin.modules.delete_module', id=0).rsplit('/', 1)[0],
        bpmn_url=url_for('bpmn.designer', module_id=0).replace('module_id=0', 'module_id='),
        sort_col=sort_col, sort_order=sort_order)
    return render_template_string(ADMIN_TEMPLATE, title='Modules', content=content)


MODULE_LIST_TEMPLATE_REMOVED = True


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
                return redirect(url_for('admin.modules.list_modules'))
            except Exception as e:
                flash(f'Import failed: {e}', 'error')
                return redirect(url_for('admin.modules.list_modules'))
        slug = request.form['slug'].strip()
        valid, err = validate_slug(slug)
        if not valid:
            flash(f'Slug validation failed: {err}', 'error')
            return redirect(url_for('admin.modules.new_module'))
        m = Module(name=request.form['name'], slug=slug, description=request.form.get('description', ''), version=request.form.get('version', '1.0.0'), author=request.form.get('author', ''))
        db.session.add(m)
        db.session.commit()
        return redirect(url_for('admin.modules.list_modules'))
    return render_admin('New Module', 'admin/modules/new.html')


NEW_MODULE_TEMPLATE_REMOVED = True


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
        return redirect(url_for('admin.modules.edit_module', id=id))
    from app.services.bundle import export_module
    full_xml = export_module(m)
    return render_admin('Edit Module', 'admin/modules/edit.html', m=m, full_xml=full_xml)


EDIT_MODULE_TEMPLATE_REMOVED = True


@modules_bp.route('/delete/<int:id>', methods=['GET', 'POST'])
@developer_or_admin_required
@csrf_protect
def delete_module(id):
    m = Module.query.get_or_404(id)
    name = m.name
    if m.is_system:
        flash(f'Cannot delete system module "{name}". It is required by the platform.')
        return redirect(url_for('admin.modules.list_modules'))
    from app.services.dependencies import get_dependencies, has_dependencies
    dependencies = []
    if has_dependencies(id):
        dependencies = get_dependencies(id)
    if dependencies and request.method == 'GET':
        return render_admin(f'Delete Module: {name}', 'admin/modules/delete_confirm.html', name=name, dependencies=dependencies)
    from app.models import DynamicTableRegistry
    dyn_tables = {r.table_name for r in DynamicTableRegistry.query.filter_by(module_id=m.id)}
    if not dyn_tables:
        import re as _re
        from sqlalchemy import inspect as sa_inspect
        bind = db.session.get_bind()
        _all_db_tables = set(sa_inspect(bind).get_table_names())
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
    refresh_tasks()
    tbl_msg = f' and dropped {len(dyn_tables)} table(s)' if drop_tables and dyn_tables else ''
    flash(f'Module "{name}" deleted{tbl_msg}')
    return redirect(url_for('admin.modules.list_modules'))


DELETE_CONFIRM_TEMPLATE_REMOVED = True


@modules_bp.route('/<int:id>/reset', methods=['POST'])
@admin_required
@csrf_protect
def reset_system_module(id):
    m = Module.query.get_or_404(id)
    if not m.is_system:
        flash(f'Module "{m.name}" is not a system module and cannot be reset.')
        return redirect(url_for('admin.modules.list_modules'))
    for route in m.routes.all(): db.session.delete(route)
    for script in m.scripts.all(): db.session.delete(script)
    for form in m.forms.all(): db.session.delete(form)
    for task in m.scheduled_tasks.all(): db.session.delete(task)
    for trigger in m.triggers.all(): db.session.delete(trigger)
    for query in m.query_reports.all(): db.session.delete(query)
    for credential in m.credentials.all(): db.session.delete(credential)
    db.session.commit()
    refresh_tasks()
    flash(f'System module "{m.name}" reset to default (empty).')
    return redirect(url_for('admin.modules.list_modules'))


@modules_bp.route('/<int:module_id>/scan-dependencies', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def scan_dependencies(module_id):
    m = db.session.get(Module, module_id)
    if not m:
        flash(f'Module #{module_id} not found', 'error')
        return redirect(url_for('admin.modules.list_modules'))
    from app.services.dependencies import detect_dependencies
    try:
        deps_found = detect_dependencies(module_id)
        if deps_found:
            flash(f'Scanned "{m.name}": found {len(deps_found)} dependency reference(s)')
        else:
            flash(f'Scanned "{m.name}": no dependencies detected')
    except Exception as e:
        flash(f'Error scanning dependencies: {str(e)}', 'error')
    return redirect(url_for('admin.modules.list_modules'))


@modules_bp.route('/<int:module_id>/dependencies')
@developer_or_admin_required
def view_dependencies(module_id):
    m = db.session.get(Module, module_id)
    if not m:
        flash(f'Module #{module_id} not found', 'error')
        return redirect(url_for('admin.modules.list_modules'))
    from app.services.dependencies import get_dependencies
    deps = get_dependencies(module_id)
    return render_admin(f'Dependencies: {m.name}', 'admin/modules/dependencies.html', m=m, deps=deps)


DEPENDENCIES_TEMPLATE_REMOVED = True


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
    return redirect(url_for('admin.modules.list_modules'))


@modules_bp.route('/import_xml/<int:id>', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def import_module_xml(id):
    m = Module.query.get_or_404(id)
    if 'file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('admin.modules.edit_module', id=id))
    xml_file = request.files['file']
    if not xml_file.filename:
        flash('Empty filename', 'error')
        return redirect(url_for('admin.modules.edit_module', id=id))
    try:
        from app.services.bundle import import_module
        import_module(xml_file.read().decode('utf-8'), update_existing=True, module_id=id)
        create_auto_version(id)
        flash(f'Module "{m.name}" updated from XML')
    except Exception as e:
        flash(f'Import failed: {e}', 'error')
    return redirect(url_for('admin.modules.edit_module', id=id))


@modules_bp.route('/<int:module_id>/executions')
@developer_or_admin_required
def module_executions(module_id):
    module = db.session.get(Module, module_id)
    if not module:
        flash('Module not found', 'error')
        return redirect(url_for('admin.modules.list_modules'))
    scripts = db.session.query(Script).filter_by(module_id=module_id).all()
    script_names = [s.name for s in scripts]
    from app.models import ExecutionLog
    limit = request.args.get('limit', 50, type=int)
    logs = db.session.query(ExecutionLog).filter(
        ExecutionLog.source_name.in_(script_names),
        ExecutionLog.source_type == 'script'
    ).order_by(ExecutionLog.created_at.desc()).limit(limit).all()
    return render_admin(f'Executions: {module.name}', 'admin/modules/executions.html', m=module, logs=logs, limit=limit)


EXECUTIONS_TEMPLATE_REMOVED = True

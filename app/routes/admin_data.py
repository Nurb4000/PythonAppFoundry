"""Admin routes for data (table browser) management."""
from flask import Blueprint, request, redirect, url_for, Response, flash
import io
import csv
import sqlalchemy as sa
from sqlalchemy.sql import func
from sqlalchemy import Table
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required, developer_or_admin_required, render_admin
from app import db
from app.models import Script, DynamicTableRegistry, Module
from app.services.audit import log_audit

data_bp = Blueprint('data', __name__)

SENSITIVE_COLUMNS = {'password_hash', '_password'}

@data_bp.route('/')
@admin_required
def list_tables():
    # Build table→modules mapping
    table_modules = {}
    platform_tables = {'users', 'user_groups', 'groups', 'modules', 'routes',
                       'scripts', 'forms', 'templates', 'scheduled_tasks', 'triggers',
                       'settings', 'uploads', 'chat_sessions', 'chat_messages',
                       'execution_logs', 'module_dependencies', 'module_versions',
                       'query_reports', 'incoming_emails', 'dynamic_table_registry',
                       'credentials', 'audit_logs', 'script_executions'}
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

    # Build script substring fallback: for any table not in the registry,
    # scan all script source code for the table name as a substring
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
    # Collect all table names: from metadata AND from actual DB tables
    seen = set()
    bind = db.session.get_bind()
    inspector = sa.inspect(bind)
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
        m.name for m in Module.query.order_by(Module.name).all()
    ))

    return render_admin('Database Tables', 'admin/data/list.html', tables=tables, module_names=module_names, filter_module=filter_module,
       sort_col=sort_col, sort_order=sort_order)

@data_bp.route('/<table_name>/')
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

    return render_admin('Browse: ' + table_name, 'admin/data/browse.html', table_name=table_name, columns=columns, rows=rows, page=page, total=total, total_pages=total_pages)

@data_bp.route('/<table_name>/new', methods=['GET', 'POST'])
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
        log_audit('create', 'data', details=f'table={table_name}')
        return redirect(url_for('admin.data.browse_table', table_name=table_name))

    return render_admin('New Row: ' + table_name, 'admin/data/new_row.html', table_name=table_name, columns=columns)

@data_bp.route('/<table_name>/<int:id>/edit', methods=['GET', 'POST'])
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
        log_audit('edit', 'data', entity_id=id, details=f'table={table_name}')
        return redirect(url_for('admin.data.browse_table', table_name=table_name))

    return render_admin('Edit Row: ' + table_name, 'admin/data/edit_row.html', table_name=table_name, columns=columns)

@data_bp.route('/<table_name>/<int:id>/delete', methods=['POST'])
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
    log_audit('delete', 'data', entity_id=id, details=f'table={table_name}')
    return redirect(url_for('admin.data.browse_table', table_name=table_name))

@data_bp.route('/<table_name>/delete', methods=['POST'])
@admin_required
@csrf_protect
def delete_table(table_name):
    platform_tables = {'users', 'user_groups', 'groups', 'modules', 'routes',
                       'scripts', 'forms', 'templates', 'scheduled_tasks', 'triggers',
                       'settings', 'uploads', 'chat_sessions', 'chat_messages',
                       'execution_logs', 'module_dependencies', 'module_versions',
                       'query_reports', 'incoming_emails', 'credentials', 'audit_logs', 'script_executions'}
    if table_name in platform_tables:
        flash(f'Cannot drop platform table "{table_name}"', 'error')
        return redirect(url_for('admin.data.list_tables'))
    if table_name not in db.metadata.tables:
        flash(f'Table "{table_name}" not found', 'error')
        return redirect(url_for('admin.data.list_tables'))
    table = db.metadata.tables[table_name]
    bind = db.session.get_bind()
    table.drop(bind, checkfirst=True)
    db.metadata.remove(table)
    log_audit('drop', 'data', details=f'table={table_name}')
    flash(f'Table "{table_name}" dropped')
    return redirect(url_for('admin.data.list_tables'))

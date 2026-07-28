from flask import Blueprint, request, redirect, url_for, render_template, flash, jsonify
from app.services.csrf import csrf_protect
from app.services.admin_utils import developer_or_admin_required, render_admin
from app import db
from app.models import Module, QueryReport
from app.services.audit import log_audit
from app.services.sql_builder import describe_tables, natural_language_to_sql, validate_sql, build_visual_query, build_query_with_joins

queries_bp = Blueprint('queries', __name__)






@queries_bp.route('/')
@developer_or_admin_required
def list_queries():
    selected_module_id = request.args.get('module_id', type=int)
    sort_col = request.args.get('sort', 'name')
    sort_order = request.args.get('order', 'asc')

    q = db.session.query(QueryReport)
    if selected_module_id:
        q = q.filter(QueryReport.module_id == selected_module_id)

    sort_attr = getattr(QueryReport, sort_col, None)
    if sort_attr is not None:
        q = q.order_by(sort_attr.desc() if sort_order == 'desc' else sort_attr.asc())
    else:
        q = q.order_by(QueryReport.name)

    queries = q.all()
    modules = db.session.query(Module).order_by(Module.name).all()
    return render_admin('Query Reports', 'admin/queries/list.html',
                        queries=queries, modules=modules,
                        selected_module_id=selected_module_id,
                        sort_col=sort_col, sort_order=sort_order)


@queries_bp.route('/new', methods=['GET', 'POST'])
@developer_or_admin_required
@csrf_protect
def new_query():
    modules = db.session.query(Module).order_by(Module.name).all()
    if request.method == 'POST':
        q = QueryReport(
            module_id=int(request.form.get('module_id', 0)),
            name=request.form.get('name', ''),
            description=request.form.get('description', ''),
            sql=request.form.get('sql', ''),
            chart_type=request.form.get('chart_type', 'none'),
            label_column=request.form.get('label_column', ''),
            data_columns=request.form.get('data_columns', ''),
            chart_title=request.form.get('chart_title', ''),
            schedule_cron=request.form.get('schedule_cron', ''),
            email_to=request.form.get('email_to', ''),
            email_subject=request.form.get('email_subject', ''),
        )
        db.session.add(q)
        db.session.commit()
        log_audit('create', 'query', q.id, q.name)
        flash(f'Query "{q.name}" created')
        return redirect(url_for('admin.queries.edit_query', id=q.id))
    q = QueryReport(module_id=modules[0].id if modules else 0, name='', description='', sql='SELECT * FROM modules LIMIT 10', chart_type='none',
                    label_column='', data_columns='', chart_title='',
                    schedule_cron='', email_to='', email_subject='')
    return render_admin('New Query', 'admin/queries/form.html', q=q, modules=modules, action=url_for('admin.queries.new_query'))


@queries_bp.route('/<int:id>', methods=['GET', 'POST'])
@developer_or_admin_required
@csrf_protect
def edit_query(id):
    q = QueryReport.query.get_or_404(id)
    modules = db.session.query(Module).order_by(Module.name).all()
    if request.method == 'POST':
        q.module_id = int(request.form.get('module_id', q.module_id))
        q.name = request.form.get('name', q.name)
        q.description = request.form.get('description', q.description)
        q.sql = request.form.get('sql', q.sql)
        q.chart_type = request.form.get('chart_type', q.chart_type)
        q.label_column = request.form.get('label_column', q.label_column)
        q.data_columns = request.form.get('data_columns', q.data_columns)
        q.chart_title = request.form.get('chart_title', q.chart_title)
        q.schedule_cron = request.form.get('schedule_cron', q.schedule_cron)
        q.email_to = request.form.get('email_to', q.email_to)
        q.email_subject = request.form.get('email_subject', q.email_subject)
        db.session.commit()
        log_audit('edit', 'query', q.id, q.name)
        flash('Query updated')
        return redirect(url_for('admin.queries.edit_query', id=q.id))
    return render_admin('Edit: ' + q.name, 'admin/queries/form.html', q=q, modules=modules, action=url_for('admin.queries.edit_query', id=q.id))


@queries_bp.route('/<int:id>/delete', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def delete_query(id):
    q = QueryReport.query.get_or_404(id)
    name = q.name
    db.session.delete(q)
    db.session.commit()
    log_audit('delete', 'query', q.id, name)
    flash('Query deleted')
    return redirect(url_for('admin.queries.list_queries'))


@queries_bp.route('/<int:id>/run')
@developer_or_admin_required
def run_query(id):
    q = QueryReport.query.get_or_404(id)
    import time as _t
    t0 = _t.time()
    error = None
    columns = []
    rows = []
    chart_labels = []
    chart_datasets = []
    try:
        result = db.session.execute(db.text(q.sql))
        if result.returns_rows:
            columns = list(result.keys())
            rows = [list(r) for r in result.fetchall()]
        if q.chart_type != 'none' and q.label_column and q.data_columns:
            label_idx = None
            for i, c in enumerate(columns):
                if c.lower() == q.label_column.lower():
                    label_idx = i
                    break
            data_col_indices = []
            data_col_names = []
            for dc in q.data_columns.split(','):
                dc = dc.strip()
                for i, c in enumerate(columns):
                    if c.lower() == dc.lower():
                        data_col_indices.append(i)
                        data_col_names.append(c)
                        break
            if label_idx is not None and data_col_indices:
                chart_labels = [str(r[label_idx]) for r in rows]
                colors = ['#2563eb', '#e94560', '#28a745', '#ffc107', '#6f42c1', '#fd7e14', '#20c997', '#dc3545']
                for j, dc_idx in enumerate(data_col_indices):
                    chart_datasets.append({
                        'label': data_col_names[j],
                        'data': [float(r[dc_idx]) if r[dc_idx] is not None else 0 for r in rows],
                        'backgroundColor': colors[j % len(colors)],
                        'borderColor': colors[j % len(colors)],
                        'borderWidth': 1,
                    })
        duration = int((_t.time() - t0) * 1000)
    except Exception as e:
        duration = int((_t.time() - t0) * 1000)
        error = str(e)
    html = render_template('admin/queries/result.html',
        columns=columns, rows=rows, duration=duration, error=error,
        chart_type=q.chart_type if q.chart_type != 'none' else None,
        chart_labels=chart_labels, chart_datasets=chart_datasets,
        chart_title=q.chart_title, q=q)
    return render_admin('Results: ' + q.name, html)


@queries_bp.route('/describe_tables')
@developer_or_admin_required
def describe_tables_endpoint():
    """Return JSON list of all tables and their columns for the SQL Builder UI."""
    tables = describe_tables()
    return jsonify(tables)


@queries_bp.route('/generate_sql', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def generate_sql():
    """Generate SQL from natural language input via the LLM."""
    user_input = request.form.get('input', '').strip()
    selected_tables = request.form.getlist('tables[]')

    if not user_input:
        return jsonify({'sql': None, 'error': 'Please enter a query description.'})

    result = natural_language_to_sql(user_input, selected_tables or None)

    if result['error']:
        return jsonify({'sql': None, 'error': result['error']})

    validation = validate_sql(result['sql'])
    if not validation['valid']:
        return jsonify({
            'sql': result['sql'],
            'error': f'Generated SQL failed validation: {validation["error"]}',
            'warning': True,
        })

    return jsonify({'sql': result['sql'], 'error': None})


@queries_bp.route('/visual_query', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def visual_query():
    """Build SQL from visual query builder form data."""
    table_name = request.form.get('table_name', '').strip()
    columns = request.form.getlist('columns[]')
    select_all = request.form.get('select_all') == 'on'

    conditions = []
    cond_cols = request.form.getlist('condition_column[]')
    cond_ops = request.form.getlist('condition_operator[]')
    cond_vals = request.form.getlist('condition_value[]')
    for i in range(len(cond_cols)):
        if cond_cols[i] and cond_cols[i] != '---':
            conditions.append({
                'column': cond_cols[i],
                'operator': cond_ops[i] if i < len(cond_ops) else '=',
                'value': cond_vals[i] if i < len(cond_vals) else '',
            })

    order_by = []
    ob_cols = request.form.getlist('order_column[]')
    ob_dirs = request.form.getlist('order_direction[]')
    for i in range(len(ob_cols)):
        if ob_cols[i]:
            order_by.append({
                'column': ob_cols[i],
                'direction': ob_dirs[i] if i < len(ob_dirs) else 'asc',
            })

    joins = []
    join_tables = request.form.getlist('join_table[]')
    join_on_cols = request.form.getlist('join_on_column[]')
    join_ref_cols = request.form.getlist('join_ref_column[]')
    join_types = request.form.getlist('join_type[]')
    for i in range(len(join_tables)):
        if join_tables[i]:
            joins.append({
                'table': join_tables[i],
                'on_column': join_on_cols[i] if i < len(join_on_cols) else '',
                'on_ref_column': join_ref_cols[i] if i < len(join_ref_cols) else '',
                'type': join_types[i] if i < len(join_types) else 'INNER',
            })

    limit = request.form.get('limit', '100', type=int)

    if joins:
        sql = build_query_with_joins(
            table_name, columns or None, conditions or None,
            joins, order_by or None, limit
        )
    else:
        sql = build_visual_query(
            table_name, columns or None, conditions or None,
            order_by or None, limit, select_all
        )

    validation = validate_sql(sql)
    if not validation['valid']:
        return jsonify({'sql': sql, 'error': f'Query validation failed: {validation["error"]}'})

    return jsonify({'sql': sql, 'error': None})


@queries_bp.route('/execute_sql', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def execute_sql():
    """Execute a SQL query (from NL generation or visual builder) and return results."""
    sql = request.form.get('sql', '').strip()
    if not sql:
        return jsonify({'error': 'No SQL provided.', 'columns': [], 'rows': []})

    import time as _t
    t0 = _t.time()
    error = None
    columns = []
    rows = []

    try:
        result = db.session.execute(db.text(sql))
        if result.returns_rows:
            columns = list(result.keys())
            rows = [list(r) for r in result.fetchall()]
        duration = int((_t.time() - t0) * 1000)
    except Exception as e:
        duration = int((_t.time() - t0) * 1000)
        error = str(e)

    return jsonify({'columns': columns, 'rows': rows, 'duration_ms': duration, 'error': error})

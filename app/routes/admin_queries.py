"""Admin routes for query report management."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import developer_or_admin_required
from app import db
from app.models import QueryReport, Module

queries_bp = Blueprint('queries', __name__)


@queries_bp.route('/queries')
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
    return render_admin('Query Reports', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;flex-wrap:wrap;">
  <a href="{{ url_for('admin.new_query') }}">+ New Query</a>
  <form method="GET" style="display:inline;margin-left:auto;">
    <select name="module_id" onchange="this.form.submit()" style="padding:6px;border:1px solid #ccc;border-radius:4px;">
      <option value="">All modules</option>
      {% for m in modules %}
      <option value="{{ m.id }}" {% if selected_module_id == m.id %}selected{% endif %}>{{ m.name }}</option>
      {% endfor %}
    </select>
    <noscript><button type="submit">Filter</button></noscript>
  </form>
</div>
{% if queries %}
<div class="table-wrap">
<table>
<thead><tr>
  <th><a href="?sort=id&order={% if sort_col == 'id' and sort_order == 'asc' %}desc{% else %}asc{% endif %}{% if selected_module_id %}&module_id={{ selected_module_id }}{% endif %}">id{% if sort_col == 'id' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th><a href="?sort=name&order={% if sort_col == 'name' and sort_order == 'asc' %}desc{% else %}asc{% endif %}{% if selected_module_id %}&module_id={{ selected_module_id }}{% endif %}">Name{% if sort_col == 'name' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th>Module</th>
  <th><a href="?sort=chart_type&order={% if sort_col == 'chart_type' and sort_order == 'asc' %}desc{% else %}asc{% endif %}{% if selected_module_id %}&module_id={{ selected_module_id }}{% endif %}">Chart{% if sort_col == 'chart_type' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th>Schedule</th>
  <th><a href="?sort=last_run&order={% if sort_col == 'last_run' and sort_order == 'asc' %}desc{% else %}asc{% endif %}{% if selected_module_id %}&module_id={{ selected_module_id }}{% endif %}">Last Run{% if sort_col == 'last_run' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th>Actions</th>
</tr></thead>
<tbody>
{% for q in queries %}
<tr>
  <td>{{ q.id }}</td>
  <td><strong>{{ q.name }}</strong></td>
  <td>{% if q.module %}<a href="{{ url_for('admin.edit_module', id=q.module.id) }}">{{ q.module.name }}</a>{% else %}<span style="color:#999;">—</span>{% endif %}</td>
  <td>{% if q.chart_type != 'none' %}{{ q.chart_type }}{% else %}<span style="color:#999;">—</span>{% endif %}</td>
  <td>{% if q.schedule_cron %}<code>{{ q.schedule_cron }}</code>{% else %}<span style="color:#999;">—</span>{% endif %}</td>
  <td>{{ q.last_run|localtime if q.last_run else '<span style="color:#999;">never</span>'|safe }}</td>
  <td style="white-space:nowrap;">
    <a href="{{ url_for('admin.run_query', id=q.id) }}">Run</a>
    <a href="{{ url_for('admin.edit_query', id=q.id) }}">Edit</a>
    <form method="POST" action="{{ url_for('admin.delete_query', id=q.id) }}" style="display:inline" onsubmit="return confirm('Delete query &quot;{{ q.name }}&quot;?')">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <button type="submit" style="background:none;border:none;color:#c00;cursor:pointer;text-decoration:underline;padding:0;font:inherit">Delete</button>
    </form>
  </td>
</tr>
{% endfor %}
</tbody></table>
</div>
{% else %}
<p style="color:#888;">No queries defined yet.</p>
{% endif %}''', queries=queries, modules=modules,
                    selected_module_id=selected_module_id,
                    sort_col=sort_col, sort_order=sort_order)


@queries_bp.route('/queries/new', methods=['GET', 'POST'])
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
        flash(f'Query "{q.name}" created')
        return redirect(url_for('admin.edit_query', id=q.id))
    q = QueryReport(module_id=modules[0].id if modules else 0, name='', description='', sql='SELECT * FROM modules LIMIT 10', chart_type='none',
                    label_column='', data_columns='', chart_title='',
                    schedule_cron='', email_to='', email_subject='')
    return render_admin('New Query', QUERY_FORM_TEMPLATE, q=q, modules=modules, action=url_for('admin.new_query'))


@queries_bp.route('/queries/<int:id>', methods=['GET', 'POST'])
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
        flash('Query updated')
        return redirect(url_for('admin.edit_query', id=q.id))
    return render_admin('Edit: ' + q.name, QUERY_FORM_TEMPLATE, q=q, modules=modules, action=url_for('admin.edit_query', id=q.id))


@queries_bp.route('/queries/<int:id>/delete', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def delete_query(id):
    q = QueryReport.query.get_or_404(id)
    db.session.delete(q)
    db.session.commit()
    flash('Query deleted')
    return redirect(url_for('admin.list_queries'))


@queries_bp.route('/queries/<int:id>/run')
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
    html = render_template_string(QUERY_RESULT_TEMPLATE,
        columns=columns, rows=rows, duration=duration, error=error,
        chart_type=q.chart_type if q.chart_type != 'none' else None,
        chart_labels=chart_labels, chart_datasets=chart_datasets,
        chart_title=q.chart_title, q=q)
    return render_admin('Results: ' + q.name, html)


QUERY_FORM_TEMPLATE = '''<script src="/static/chart.umd.min.js"></script>
<div id="queryApp">
<form method="POST" action="{{ action }}">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem;">
  <div>
    <label style="display:block;font-weight:600;margin-bottom:4px;">Name</label>
    <input name="name" value="{{ q.name }}" required style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;">
  </div>
  <div>
    <label style="display:block;font-weight:600;margin-bottom:4px;">Module</label>
    <select name="module_id" required style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;">
      {% for m in modules %}
      <option value="{{ m.id }}" {% if q.module_id == m.id %}selected{% endif %}>{{ m.name }}</option>
      {% endfor %}
    </select>
  </div>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem;">
  <div>
    <label style="display:block;font-weight:600;margin-bottom:4px;">Chart Type</label>
    <select name="chart_type" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;">
      <option value="none" {% if q.chart_type == 'none' %}selected{% endif %}>Table only (no chart)</option>
      <option value="bar" {% if q.chart_type == 'bar' %}selected{% endif %}>Bar</option>
      <option value="line" {% if q.chart_type == 'line' %}selected{% endif %}>Line</option>
      <option value="pie" {% if q.chart_type == 'pie' %}selected{% endif %}>Pie</option>
      <option value="doughnut" {% if q.chart_type == 'doughnut' %}selected{% endif %}>Doughnut</option>
      <option value="polarArea" {% if q.chart_type == 'polarArea' %}selected{% endif %}>Polar Area</option>
      <option value="radar" {% if q.chart_type == 'radar' %}selected{% endif %}>Radar</option>
    </select>
  </div>
  <div>
    <label style="display:block;font-weight:600;margin-bottom:4px;">Description</label>
    <input name="description" value="{{ q.description }}" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;">
  </div>
</div>

<div style="margin-bottom:1rem;">
  <label style="display:block;font-weight:600;margin-bottom:4px;">SQL Query</label>
  <textarea name="sql" rows="8" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;font-family:monospace;font-size:0.9em;" required>{{ q.sql }}</textarea>
  <div style="font-size:0.85em;color:#888;margin-top:4px;">Use <code>-- limit N</code> in your query to control row count for charts.</div>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem;margin-bottom:1rem;">
  <div>
    <label style="display:block;font-weight:600;margin-bottom:4px;">Label Column (X axis)</label>
    <input name="label_column" value="{{ q.label_column }}" placeholder="e.g. name, date" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;">
  </div>
  <div>
    <label style="display:block;font-weight:600;margin-bottom:4px;">Data Column(s) (Y axis)</label>
    <input name="data_columns" value="{{ q.data_columns }}" placeholder="e.g. count, total" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;">
  </div>
  <div>
    <label style="display:block;font-weight:600;margin-bottom:4px;">Chart Title</label>
    <input name="chart_title" value="{{ q.chart_title }}" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;">
  </div>
</div>

<details style="margin-bottom:1rem;border:1px solid #ddd;border-radius:4px;padding:0.75rem;">
  <summary style="cursor:pointer;font-weight:600;color:#555;">Schedule &amp; Email</summary>
  <div style="margin-top:0.75rem;display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem;">
    <div>
      <label style="display:block;font-weight:600;margin-bottom:4px;">Cron Schedule</label>
      <input name="schedule_cron" value="{{ q.schedule_cron }}" placeholder="e.g. 0 8 * * 1" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;">
      <div style="font-size:0.85em;color:#888;margin-top:2px;">Leave blank for manual only.</div>
    </div>
    <div>
      <label style="display:block;font-weight:600;margin-bottom:4px;">Email To</label>
      <input name="email_to" value="{{ q.email_to }}" placeholder="user@example.com" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;">
    </div>
    <div>
      <label style="display:block;font-weight:600;margin-bottom:4px;">Email Subject</label>
      <input name="email_subject" value="{{ q.email_subject }}" placeholder="Report: {{ q.name }}" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;">
    </div>
  </div>
</details>

<div style="display:flex;gap:0.75rem;">
  <button type="submit" style="padding:10px 24px;background:#2563eb;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:1em;">Save</button>
  {% if q.id %}
  <button type="button" onclick="runQuery({{ q.id }})" style="padding:10px 24px;background:#28a745;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:1em;">Save &amp; Run</button>
  {% endif %}
  <a href="{{ url_for('admin.list_queries') }}" style="padding:10px 24px;background:#6c757d;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:1em;text-decoration:none;">Cancel</a>
</div>
</form>

<div id="queryResults" style="margin-top:1.5rem;display:none;">
  <h3>Results</h3>
  <div id="chartContainer" style="max-width:600px;margin:1rem 0;display:none;"><canvas id="resultChart"></canvas></div>
  <div id="resultTable"></div>
  <div id="resultError" style="color:#c00;"></div>
</div>
</div>

<script>
function runQuery(id) {
  var form = document.getElementById('queryApp').querySelector('form');
  var formData = new FormData(form);
  var btn = event.target;
  btn.disabled = true;
  btn.textContent = 'Running...';
  fetch('/__api/queries/' + id + '/run', { method: 'POST', body: formData })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      btn.disabled = false;
      btn.textContent = 'Save & Run';
      var results = document.getElementById('queryResults');
      results.style.display = 'block';
      var chartContainer = document.getElementById('chartContainer');
      var errorDiv = document.getElementById('resultError');
      errorDiv.innerHTML = '';
      if (data.error) {
        errorDiv.textContent = data.error;
        return;
      }
      var tableHtml = '<div class="table-wrap"><table><thead><tr>';
      data.columns.forEach(function(c) { tableHtml += '<th>' + c + '</th>'; });
      tableHtml += '</tr></thead><tbody>';
      data.rows.forEach(function(r) {
        tableHtml += '<tr>';
        r.forEach(function(v) { tableHtml += '<td>' + (v != null ? v : '') + '</td>'; });
        tableHtml += '</tr>';
      });
      tableHtml += '</tbody></table></div><p style="font-size:0.85em;color:#888;">' + data.rows.length + ' row(s) in ' + data.duration_ms + 'ms</p>';
      document.getElementById('resultTable').innerHTML = tableHtml;
      var chartType = form.querySelector('[name=chart_type]').value;
      if (chartType !== 'none' && data.chart_labels && data.chart_datasets) {
        chartContainer.style.display = 'block';
        var ctx = document.getElementById('resultChart').getContext('2d');
        if (window._resultChart) window._resultChart.destroy();
        window._resultChart = new Chart(ctx, {
          type: chartType,
          data: { labels: data.chart_labels, datasets: data.chart_datasets },
          options: { responsive: true, plugins: { title: { display: !!(data.chart_title), text: data.chart_title || '' } } }
        });
      } else {
        chartContainer.style.display = 'none';
      }
    })
    .catch(function(err) {
      btn.disabled = false;
      btn.textContent = 'Save & Run';
      document.getElementById('resultError').textContent = 'Request failed: ' + err.message;
    });
}
</script>'''


QUERY_RESULT_TEMPLATE = '''<script src="/static/chart.umd.min.js"></script>
<h2>{{ q.name }}</h2>
<p style="color:#888;">{{ q.description }}</p>
{% if error %}
<div style="color:#c00;background:#fee;padding:1rem;border-radius:4px;border:1px solid #fcc;">
  <strong>Error:</strong> {{ error }}
</div>
{% else %}
{% if chart_type %}
<div style="max-width:600px;margin:1rem 0;">
  <canvas id="reportChart"></canvas>
</div>
<script>
new Chart(document.getElementById('reportChart'), {
  type: '{{ chart_type }}',
  data: { labels: {{ chart_labels|tojson|safe }}, datasets: {{ chart_datasets|tojson|safe }} },
  options: { responsive: true, plugins: { title: { display: true, text: '{{ chart_title }}' } } }
});
</script>
{% endif %}
<div class="table-wrap">
<table>
<thead><tr>{% for c in columns %}<th>{{ c }}</th>{% endfor %}</tr></thead>
<tbody>{% for r in rows %}<tr>{% for v in r %}<td>{{ v }}</td>{% endfor %}</tr>{% endfor %}</tbody>
</table>
</div>
<p style="font-size:0.85em;color:#888;">{{ rows|length }} row(s) in {{ duration }}ms</p>
<a href="{{ url_for('admin.edit_query', id=q.id) }}">&larr; Edit Query</a>
{% endif %}'''

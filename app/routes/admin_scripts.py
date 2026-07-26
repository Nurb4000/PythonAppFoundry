"""Admin routes for script management."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import developer_or_admin_required, list_view, render_admin
from app import db
from app.models import Script, Module

scripts_bp = Blueprint('scripts', __name__)


@scripts_bp.route('/scripts')
@developer_or_admin_required
def list_scripts():
    return list_view(Script, 'scripts',
        ['id', 'name', 'language'],
        'admin.edit_script', 'admin.new_script', has_module=True)


@scripts_bp.route('/scripts/new', methods=['GET', 'POST'])
@developer_or_admin_required
@csrf_protect
def new_script():
    modules = db.session.query(Module).all()
    if request.method == 'POST':
        source = request.form.get('source_code', '')
        language = request.form.get('language', 'python')
        if language == 'python' and source.strip():
            try:
                compile(source, f'<{request.form["name"]}>', 'exec')
            except SyntaxError as e:
                flash(f'Syntax error in script "{request.form["name"]}": {e.msg} (line {e.lineno})', 'error')
                return redirect(url_for('admin.new_script'))
        s = Script(
            module_id=int(request.form['module_id']),
            name=request.form['name'],
            language=language,
            source_code=source,
            description=request.form.get('description', ''),
        )
        db.session.add(s)
        db.session.commit()
        return redirect(url_for('admin.list_scripts'))
    return render_admin('New Script', '''
<form method="POST">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>Name <input name="name" required></label>
<label>Language <input name="language" value="python"></label>
<label>Module <select name="module_id">{% for m in modules %}<option value="{{ m.id }}">{{ m.name }}</option>{% endfor %}</select></label>
<label>Description <textarea name="description"></textarea></label>
<label>Source Code <textarea name="source_code" rows="15" style="width:100%;font-family:monospace"></textarea></label>
<button>Save</button>
</form>''', modules=modules)


@scripts_bp.route('/scripts/edit/<int:id>', methods=['GET', 'POST'])
@developer_or_admin_required
@csrf_protect
def edit_script(id):
    s = Script.query.get_or_404(id)
    modules = db.session.query(Module).all()
    if request.method == 'POST':
        source = request.form.get('source_code', '')
        language = request.form.get('language', 'python')
        if language == 'python' and source.strip():
            try:
                compile(source, f'<{request.form["name"]}>', 'exec')
            except SyntaxError as e:
                flash(f'Syntax error in script "{request.form["name"]}": {e.msg} (line {e.lineno})', 'error')
                return redirect(url_for('admin.edit_script', id=s.id))
        s.module_id = int(request.form['module_id'])
        s.name = request.form['name']
        s.language = language
        s.source_code = source
        s.description = request.form.get('description', '')
        db.session.commit()
        return redirect(url_for('admin.list_scripts'))
    return render_admin('Edit Script', '''
<form method="POST">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <div style="display:flex;gap:12px;flex-wrap:wrap;">
    <label style="flex:2;min-width:140px;">Name <input name="name" value="{{ s.name }}" required style="width:100%;"></label>
    <label style="flex:1;min-width:100px;">Language <input name="language" value="{{ s.language }}" style="width:100%;"></label>
    <label style="flex:2;min-width:140px;">Module <select name="module_id" style="width:100%;">{% for m in modules %}<option value="{{ m.id }}" {% if m.id == s.module_id %}selected{% endif %}>{{ m.name }}</option>{% endfor %}</select></label>
  </div>
  <label style="display:block;margin-top:12px;">Description
    <textarea name="description" style="width:100%;min-height:80px;resize:vertical;">{{ s.description }}</textarea>
  </label>
  <label style="display:block;margin-top:12px;">Source Code
    <textarea name="source_code" id="source_code" rows="15" style="width:100%;font-family:monospace;z-index:1;background:rgba(255,255,255,0.9);">{{ s.source_code }}</textarea>
  </label>
  <button style="margin-top:12px;padding:6px 16px;">Save</button>
  <button type="button" onclick="testScript({{ s.id }})" style="margin-left:0.5rem;padding:6px 16px;background:#28a745;color:#fff;border:none;border-radius:4px;cursor:pointer;">Test Script</button>
  <a href="{{ url_for('admin.debug_script', id=s.id) }}" style="margin-left:0.5rem;padding:6px 16px;background:#f0f0f0;color:#333;text-decoration:none;border:1px solid #ccc;border-radius:4px;display:inline-block;">Run Debug</a>
</form>

<!-- Test Script Modal -->
<div id="testModal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:10000;">
  <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:#fff;border-radius:8px;padding:1.5rem;max-width:700px;width:90%;max-height:80vh;overflow-y:auto;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;">
      <h3 style="margin:0;">Test Script: {{ s.name }}</h3>
      <button onclick="document.getElementById('testModal').style.display='none'" style="background:none;border:none;font-size:1.5rem;cursor:pointer;">&times;</button>
    </div>
    <div id="testResult"></div>
  </div>
</div>

<script src="/static/python-highlight.js"></script>
<script>
function testScript(scriptId) {
  var modal = document.getElementById('testModal');
  var result = document.getElementById('testResult');
  modal.style.display = 'block';
  result.innerHTML = '<p style="color:#888;">Running script...</p>';
  
  fetch('/__admin/scripts/test/' + scriptId, {
    method: 'POST',
    headers: {'X-CSRFToken': document.querySelector('[name=csrf_token]').value},
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    if (data.error) {
      result.innerHTML = '<div style="background:#fee;border:1px solid #fcc;padding:1rem;border-radius:4px;"><strong style="color:#c00;">Error:</strong><pre style="margin:0.5rem 0;font-size:0.85em;overflow:auto;">' + data.error + '</pre></div>' +
        (data.output ? '<div style="background:#f4f4f4;border:1px solid #ddd;padding:1rem;border-radius:4px;margin-top:0.5rem;"><strong>Output:</strong><pre style="margin:0.5rem 0;font-size:0.85em;overflow:auto;">' + data.output + '</pre></div>' : '');
    } else {
      result.innerHTML = '<div style="background:#efe;border:1px solid #cfc;padding:1rem;border-radius:4px;"><strong style="color:#080;">Success</strong> (' + data.duration_ms + 'ms)</div>' +
        (data.result ? '<div style="background:#f4f4f4;border:1px solid #ddd;padding:1rem;border-radius:4px;margin-top:0.5rem;"><strong>Result:</strong><pre style="margin:0.5rem 0;font-size:0.85em;overflow:auto;">' + data.result + '</pre></div>' : '') +
        (data.output ? '<div style="background:#f4f4f4;border:1px solid #ddd;padding:1rem;border-radius:4px;margin-top:0.5rem;"><strong>Output:</strong><pre style="margin:0.5rem 0;font-size:0.85em;overflow:auto;">' + data.output + '</pre></div>' : '');
    }
  })
  .catch(function(err) {
    result.innerHTML = '<div style="background:#fee;border:1px solid #fcc;padding:1rem;border-radius:4px;"><strong style="color:#c00;">Request failed:</strong> ' + err.message + '</div>';
  });
}
</script>''', s=s, modules=modules)


@scripts_bp.route('/scripts/debug/<int:id>')
@developer_or_admin_required
def debug_script(id):
    s = Script.query.get_or_404(id)
    import time
    t0 = time.time()
    from io import StringIO
    import sys
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    error = None
    output = None
    try:
        result = execute_script(s)
        output = sys.stdout.getvalue()
        duration = int((time.time() - t0) * 1000)
    except Exception as e:
        import traceback
        error = traceback.format_exc()
        duration = int((time.time() - t0) * 1000)
    finally:
        sys.stdout = old_stdout
    source_lines = s.source_code.split('\n')
    numbered_lines = [{'line_num': i + 1, 'line': line} for i, line in enumerate(source_lines)]
    return render_admin('Debug: ' + s.name, '''
<h2>Debug: {{ s.name }}</h2>
<p style="color:#888;">Duration: {{ duration }}ms | Module: {{ s.module.name }}</p>
<h3>Source Code</h3>
<pre style="background:#f4f4f4;padding:0.5rem;overflow:auto;font-size:0.85rem;border:1px solid #ddd;border-radius:4px;">
{% for item in source_lines %}
<span style="color:#999;">{{ '%3d' % item.line_num }}</span>  {{ item.line }}
{% endfor %}
</pre>
{% if error %}
<h3 style="color:#c00;">Error</h3>
<pre style="background:#fff5f5;padding:0.5rem;overflow:auto;font-size:0.85rem;border:1px solid #fcc;border-radius:4px;">{{ error }}</pre>
{% elif output %}
<h3>Output</h3>
<pre style="background:#f4f4f4;padding:0.5rem;overflow:auto;font-size:0.85rem;border:1px solid #ddd;border-radius:4px;">{{ output }}</pre>
{% else %}
<p>Script completed with no output.</p>
{% endif %}
<a href="{{ url_for('admin.edit_script', id=s.id) }}">&larr; Back to Script</a>
''', s=s, duration=duration, source_lines=numbered_lines, error=error, output=output)

"""Admin routes for form management."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import developer_or_admin_required, list_view
from app import db
from app.models import Form, Module

forms_bp = Blueprint('forms', __name__)


@forms_bp.route('/forms')
@developer_or_admin_required
def list_forms():
    return list_view(Form, 'forms', ['id', 'name'],
        'admin.edit_form', 'admin.new_form', has_module=True)


@forms_bp.route('/forms/new', methods=['GET', 'POST'])
@developer_or_admin_required
@csrf_protect
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
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>Name <input name="name" required></label>
<label>Module <select name="module_id">{% for m in modules %}<option value="{{ m.id }}">{{ m.name }}</option>{% endfor %}</select></label>
<label>Schema (JSON) <textarea name="schema_json" rows="10" style="width:100%;font-family:monospace">[{"name":"field1","type":"text","label":"Field 1","required":true}]</textarea></label>
<button>Save</button>
</form>''', modules=modules)


@forms_bp.route('/forms/edit/<int:id>', methods=['GET', 'POST'])
@developer_or_admin_required
@csrf_protect
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
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
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
</div>
</form>
<script>
(function() {
  var editor = document.getElementById('schemaEditor');
  var preview = document.getElementById('previewContent');
  var debounceTimer;
  
  function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }
  
  function renderPreview() {
    var json = editor.value.trim();
    if (!json || json === '[]') {
      preview.innerHTML = '<p style="color:#888;">No fields defined</p>';
      return;
    }
    try {
      var fields = JSON.parse(json);
      if (!Array.isArray(fields)) throw new Error('Expected array');
      var html = '<form onsubmit="event.preventDefault(); alert(' + JSON.stringify('Form submitted (preview only)') + ');">';
      for (var i = 0; i < fields.length; i++) {
        var field = fields[i];
        var name = escapeHtml(field.name || '');
        var label = escapeHtml(field.label || name);
        var type = escapeHtml(field.type || 'text');
        var required = field.required ? 'required' : '';
        var placeholder = escapeHtml(field.placeholder || '');
        html += '<div style="margin-bottom:12px;">';
        html += '<label for="' + name + '" style="display:block;font-weight:600;margin-bottom:4px;">' + label + '</label>';
        if (type === 'textarea') {
          html += '<textarea id="' + name + '" name="' + name + '" ' + required + ' placeholder="' + placeholder + '" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;min-height:80px;"></textarea>';
        } else if (type === 'select') {
          var opts = (field.options || '').split(',').map(function(o) { return escapeHtml(o.trim()); }).filter(Boolean);
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
    } catch (e) {
      preview.innerHTML = '<div class="preview-error">Invalid JSON: ' + escapeHtml(e.message) + '</div>';
    }
  }
  editor.addEventListener('input', function() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(renderPreview, 300);
  });
  renderPreview();
})();
</script>''', f=f, modules=modules)

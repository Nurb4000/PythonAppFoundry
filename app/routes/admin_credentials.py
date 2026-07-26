"""Admin routes for credential management."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required
from app import db
from app.models import Credential, Module

credentials_bp = Blueprint('credentials', __name__)


@credentials_bp.route('/credentials')
@admin_required
def list_credentials():
    module_id = request.args.get('module_id', type=int)
    q = db.session.query(Credential)
    if module_id:
        q = q.filter(Credential.module_id == module_id)
    q = q.order_by(Credential.module_id, Credential.name)
    creds = q.all()
    modules = db.session.query(Module).order_by(Module.name).all()
    return render_admin('Credentials', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.new_credential') }}">+ New Credential</a>
  <form method="GET" style="display:inline;">
    <select name="module_id" onchange="this.form.submit()" style="padding:4px 8px;">
      <option value="">All Modules</option>
      {% for m in modules %}
      <option value="{{ m.id }}" {% if module_id == m.id %}selected{% endif %}>{{ m.name }}</option>
      {% endfor %}
    </select>
  </form>
</div>
<div class="table-wrap">
<table>
<thead><tr>
  <th>ID</th><th>Module</th><th>Name</th><th>Type</th><th>Description</th><th>Updated</th><th>Actions</th>
</tr></thead>
<tbody>
{% for c in creds %}
<tr>
  <td>{{ c.id }}</td>
  <td>{% if c.module %}<a href="{{ url_for('admin.edit_module', id=c.module.id) }}">{{ c.module.name }}</a>{% else %}<span style="color:#999;">—</span>{% endif %}</td>
  <td><strong>{{ c.name }}</strong></td>
  <td><code>{{ c.credential_type }}</code></td>
  <td>{{ c.description[:60] if c.description else '—' }}</td>
  <td>{{ c.updated_at|localtime }}</td>
  <td>
    <a href="{{ url_for('admin.edit_credential', id=c.id) }}">Edit</a>
    <form method="POST" action="{{ url_for('admin.delete_credential', id=c.id) }}" style="display:inline" onsubmit="return confirm('Delete credential &quot;{{ c.name }}&quot;?')">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <button type="submit" style="background:none;border:none;color:#c00;cursor:pointer;text-decoration:underline;padding:0;font:inherit">Delete</button>
    </form>
  </td>
</tr>
{% endfor %}
</tbody></table>
</div>
{% if not creds %}<p style="color:#888;">No credentials defined. Add API keys, tokens, and secrets for your integration scripts.</p>{% endif %}''', creds=creds, modules=modules, module_id=module_id)


@credentials_bp.route('/credentials/new', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def new_credential():
    modules = db.session.query(Module).order_by(Module.name).all()
    if request.method == 'POST':
        from app.services.credential_store import encrypt_value
        c = Credential(
            module_id=int(request.form['module_id']),
            name=request.form['name'],
            credential_type=request.form.get('credential_type', 'api_key'),
            value_encrypted=encrypt_value(request.form['value']),
            description=request.form.get('description', ''),
        )
        db.session.add(c)
        db.session.commit()
        flash(f'Credential "{c.name}" saved')
        return redirect(url_for('admin.list_credentials'))
    return render_admin('New Credential', '''
<form method="POST">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem;">
    <label>Name <input name="name" required style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;" placeholder="e.g. github_api_key"></label>
    <label>Module <select name="module_id" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;">{% for m in modules %}<option value="{{ m.id }}">{{ m.name }}</option>{% endfor %}</select></label>
  </div>
  <label>Type
    <select name="credential_type" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;margin-bottom:1rem;">
      <option value="api_key">API Key</option>
      <option value="oauth_token">OAuth Token</option>
      <option value="basic_auth">Basic Auth (user:pass)</option>
      <option value="custom">Custom / Raw</option>
    </select>
  </label>
  <label style="display:block;margin-bottom:1rem;">
    Value <textarea name="value" rows="4" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;font-family:monospace;" required></textarea>
    <span style="color:#888;font-size:0.85em;">Stored encrypted at rest. Only accessible to scripts in the same module via <code>get_credential('name')</code>.</span>
  </label>
  <label style="display:block;margin-bottom:1rem;">
    Description <input name="description" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;">
  </label>
  <button style="padding:10px 24px;background:#2563eb;color:#fff;border:none;border-radius:4px;cursor:pointer;">Save</button>
  <a href="{{ url_for('admin.list_credentials') }}" style="margin-left:0.5rem;">Cancel</a>
</form>''', modules=modules)


@credentials_bp.route('/credentials/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def edit_credential(id):
    c = Credential.query.get_or_404(id)
    modules = db.session.query(Module).order_by(Module.name).all()
    if request.method == 'POST':
        from app.services.credential_store import encrypt_value
        c.module_id = int(request.form['module_id'])
        c.name = request.form['name']
        c.credential_type = request.form.get('credential_type', 'api_key')
        c.description = request.form.get('description', '')
        if request.form.get('value'):
            c.value_encrypted = encrypt_value(request.form['value'])
        db.session.commit()
        flash(f'Credential "{c.name}" updated')
        return redirect(url_for('admin.list_credentials'))
    return render_admin('Edit Credential', '''
<form method="POST">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem;">
    <label>Name <input name="name" value="{{ c.name }}" required style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;"></label>
    <label>Module <select name="module_id" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;">{% for m in modules %}<option value="{{ m.id }}" {% if m.id == c.module_id %}selected{% endif %}>{{ m.name }}</option>{% endfor %}</select></label>
  </div>
  <label>Type
    <select name="credential_type" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;margin-bottom:1rem;">
      <option value="api_key" {% if c.credential_type == 'api_key' %}selected{% endif %}>API Key</option>
      <option value="oauth_token" {% if c.credential_type == 'oauth_token' %}selected{% endif %}>OAuth Token</option>
      <option value="basic_auth" {% if c.credential_type == 'basic_auth' %}selected{% endif %}>Basic Auth (user:pass)</option>
      <option value="custom" {% if c.credential_type == 'custom' %}selected{% endif %}>Custom / Raw</option>
    </select>
  </label>
  <label style="display:block;margin-bottom:1rem;">
    Value <textarea name="value" rows="4" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;font-family:monospace;" placeholder="Leave blank to keep current value"></textarea>
    <span style="color:#888;font-size:0.85em;">Stored encrypted at rest. Leave blank to keep the existing value unchanged.</span>
  </label>
  <label style="display:block;margin-bottom:1rem;">
    Description <input name="description" value="{{ c.description }}" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;">
  </label>
  <button style="padding:10px 24px;background:#2563eb;color:#fff;border:none;border-radius:4px;cursor:pointer;">Update</button>
  <a href="{{ url_for('admin.list_credentials') }}" style="margin-left:0.5rem;">Cancel</a>
</form>''', c=c, modules=modules)


@credentials_bp.route('/credentials/<int:id>/delete', methods=['POST'])
@admin_required
@csrf_protect
def delete_credential(id):
    c = Credential.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    flash(f'Credential "{c.name}" deleted')
    return redirect(url_for('admin.list_credentials'))

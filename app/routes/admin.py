from flask import Blueprint, request, redirect, url_for, render_template_string, abort, jsonify, flash, Response
from app.services.scheduler import refresh_tasks
from app.services.csrf import csrf_protect, csrf_token
from app.services.validation import validate_slug, validate_route_slug, validate_cron_expression
from app.services.admin_utils import (
    admin_required as _admin_required,
    developer_or_admin_required as _dev_admin_required,
    create_auto_version as _create_auto_version,
    AttrProxy as _AttrProxy,
    render_admin as _render_admin,
    list_view as _list_view,
    _export_csv as _export_csv_util,
    ADMIN_TEMPLATE,
    LIST_TEMPLATE,
)
from flask_login import login_required, current_user
from sqlalchemy import func, inspect as sa_inspect
from sqlalchemy import Table, MetaData
import csv, io, os, subprocess
from datetime import datetime as _datetime, timezone as _tz

from app import db
from app.models import User, Module, Route, Script, Form, ScheduledTask, Trigger, ChatSession, ChatMessage, Upload, Setting, Group, ExecutionLog, ModuleVersion, QueryReport, IncomingEmail, Credential
from app.services.script_runner import execute_script

admin_bp = Blueprint('admin', __name__)

# Re-export utilities for use in this file
admin_required = _admin_required
developer_or_admin_required = _dev_admin_required
create_auto_version = _create_auto_version
AttrProxy = _AttrProxy
render_admin = _render_admin
list_view = _list_view
export_csv = _export_csv_util

# ── Triggers ──

@admin_bp.route('/triggers')
@admin_required
def list_triggers():
    return list_view(Trigger, 'triggers',
        ['id', 'name', 'event_type', 'target_table', 'enabled'],
        'admin.edit_trigger', 'admin.new_trigger', has_module=True)

@admin_bp.route('/triggers/new', methods=['GET', 'POST'])
@admin_required
@csrf_protect
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
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>Name <input name="name" required></label>
<label>Module <select name="module_id">{% for m in modules %}<option value="{{ m.id }}">{{ m.name }}</option>{% endfor %}</select></label>
<label>Event Type <select name="event_type"><option>on_insert</option><option>on_update</option><option>on_delete</option><option>after_route</option><option>webhook</option></select></label>
<label>Target Table <input name="target_table" placeholder="table_name or webhook-slug"></label>
<label>Script <select name="script_id">{% for s in scripts %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}</select></label>
<label>Auth Token (optional, for webhook triggers) <input name="auth_token" placeholder="Leave blank for public"></label>
<button>Save</button>
</form>''', modules=modules, scripts=scripts)

@admin_bp.route('/triggers/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
@csrf_protect
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
        tg.auth_token = request.form.get('auth_token', '').strip()
        db.session.commit()
        return redirect(url_for('admin.list_triggers'))
    return render_admin('Edit Trigger', '''
<form method="POST">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>Name <input name="name" value="{{ tg.name }}" required></label>
<label>Module <select name="module_id">{% for m in modules %}<option value="{{ m.id }}" {% if m.id == tg.module_id %}selected{% endif %}>{{ m.name }}</option>{% endfor %}</select></label>
<label>Event Type <select name="event_type"><option {% if tg.event_type=='on_insert' %}selected{% endif %}>on_insert</option><option {% if tg.event_type=='on_update' %}selected{% endif %}>on_update</option><option {% if tg.event_type=='on_delete' %}selected{% endif %}>on_delete</option><option {% if tg.event_type=='after_route' %}selected{% endif %}>after_route</option><option {% if tg.event_type=='webhook' %}selected{% endif %}>webhook</option></select></label>
<label>Target Table <input name="target_table" value="{{ tg.target_table }}"></label>
<label>Script <select name="script_id">{% for s in scripts %}<option value="{{ s.id }}" {% if s.id == tg.script_id %}selected{% endif %}>{{ s.name }}</option>{% endfor %}</select></label>
<label><input name="enabled" type="checkbox" {% if tg.enabled %}checked{% endif %}> Enabled</label>
<label>Auth Token (optional) <input name="auth_token" value="{{ tg.auth_token }}" placeholder="Leave blank for public"></label>
<button>Save</button>
</form>''', tg=tg, modules=modules, scripts=scripts)
# ── Settings ──

@admin_bp.route('/packages', methods=['GET', 'POST'])
@admin_required
def admin_packages():
    pip_bin = 'pip'
    output_lines = []
    install_error = ''
    selected = request.form.get('selected', '')
    protected_pkgs = {
        'flask', 'flask-sqlalchemy', 'flask-login', 'flask-migrate',
        'sqlalchemy', 'werkzeug', 'jinja2', 'markupsafe',
        'itsdangerous', 'click', 'greenlet', 'blinker',
        'bcrypt', 'apscheduler', 'python-slugify', 'python-dotenv',
        'cryptography', 'pip', 'setuptools', 'wheel',
    }

    if request.method == 'POST':
        if 'install' in request.form:
            pkg = request.form.get('package', '').strip()
            if pkg:
                cmd = [pip_bin, 'install'] + pkg.split()
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    output_lines = (r.stdout or '').splitlines() + (r.stderr or '').splitlines()
                    if r.returncode != 0:
                        install_error = f'Exit code {r.returncode}'
                except subprocess.TimeoutExpired:
                    install_error = 'Install timed out after 120s'
                except FileNotFoundError:
                    install_error = f'pip not found at "{pip_bin}"'
        elif 'uninstall' in request.form:
            pkg = request.form.get('package', '').strip()
            if pkg:
                pkg_name = pkg.split('==')[0].split('>=')[0].split('<=')[0].split('~=')[0].split('!=')[0].strip()
                if pkg_name.lower() in protected_pkgs:
                    install_error = f'"{pkg_name}" is a protected platform package and cannot be uninstalled.'
                else:
                    cmd = [pip_bin, 'uninstall', '-y', pkg]
                    try:
                        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                        output_lines = (r.stdout or '').splitlines() + (r.stderr or '').splitlines()
                        if r.returncode != 0:
                            install_error = f'Exit code {r.returncode}'
                    except subprocess.TimeoutExpired:
                        install_error = 'Uninstall timed out after 60s'
                    except FileNotFoundError:
                        install_error = f'pip not found at "{pip_bin}"'

    # Get installed packages list
    import json as _json
    packages = []
    try:
        r = subprocess.run([pip_bin, 'list', '--format=json'], capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            packages = _json.loads(r.stdout)
        else:
            install_error = f'Error listing packages:\n{r.stderr}'
    except FileNotFoundError:
        install_error = f'pip not found at "{pip_bin}"'

    output_text = '\n'.join(output_lines)
    return render_admin('Python Packages', '''
<script>
function fillUninstall(name) { document.getElementById('uninstall-input').value = name; }
</script>
<h2>Python Packages</h2>

<div style="display:flex;gap:24px;flex-wrap:wrap;">
<div style="flex:1;min-width:300px;">
<h3>Installed Packages</h3>
<div style="max-height:500px;overflow-y:auto;border:1px solid #ddd;border-radius:4px;">
<table style="width:100%;border-collapse:collapse;">
<thead><tr style="background:#f4f4f4;"><th style="padding:6px 10px;text-align:left;border-bottom:1px solid #ddd;">Package</th><th style="padding:6px 10px;text-align:left;border-bottom:1px solid #ddd;">Version</th><th style="padding:6px 10px;text-align:left;border-bottom:1px solid #ddd;">Actions</th></tr></thead>
<tbody>
{% for pkg in packages %}
{% set pkg_lower = pkg.name.lower() %}
<tr style="border-bottom:1px solid #eee;">
  <td style="padding:6px 10px;font-size:0.85em;">{{ pkg.name }}{% if pkg_lower in protected_pkgs %} <span style="color:#999;font-size:0.8em;" title="Platform package \u2014 protected">&#128274;</span>{% endif %}</td>
  <td style="padding:6px 10px;font-size:0.85em;color:#666;">{{ pkg.version }}</td>
  <td style="padding:6px 10px;font-size:0.85em;">
    {% if pkg_lower in protected_pkgs %}<span style="color:#999;">Protected</span>{% else %}<a href="#" onclick="fillUninstall('{{ pkg.name }}');return false;" style="color:#dc3545;">Uninstall</a>{% endif %}
  </td>
</tr>
{% endfor %}
</tbody></table>
</div>
</div>

<div style="flex:1;min-width:300px;">
<h3>Install Package</h3>
<form method="POST" style="margin-bottom:24px;">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label style="display:block;margin-bottom:8px;">
  <strong>Package name</strong><br>
  <input name="package" type="text" value="{{ selected }}" placeholder="requests requests==2.31.0" style="padding:6px 10px;width:100%;max-width:400px;"><br>
  <span style="color:#888;font-size:0.85em;">Name with optional <code>==version</code>. Multiple space-separated names are allowed.</span>
</label>
<button name="install" type="submit" style="padding:8px 20px;background:#2563eb;color:#fff;border:none;border-radius:4px;cursor:pointer;">Install</button>
</form>

<h3>Uninstall Package</h3>
<form method="POST" onsubmit="return confirm('Uninstall ' + document.getElementById('uninstall-input').value + '?')">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label style="display:block;margin-bottom:8px;">
  <strong>Package name</strong><br>
  <input id="uninstall-input" name="package" type="text" value="{{ selected }}" placeholder="requests" style="padding:6px 10px;width:100%;max-width:400px;"><br>
</label>
<button name="uninstall" type="submit" style="padding:8px 20px;background:#dc3545;color:#fff;border:none;border-radius:4px;cursor:pointer;">Uninstall</button>
</form>

{% if output_text %}
<h3>Command Output</h3>
<div style="max-height:400px;overflow-y:auto;border:1px solid {% if install_error %}#fcc{% else %} #ddd{% endif %};border-radius:4px;background:#f4f4f4;padding:8px;">
<pre style="margin:0;font-size:0.85em;white-space:pre-wrap;">{{ output_text }}</pre>
</div>
{% endif %}
</div>
</div>
''', packages=packages, protected_pkgs=protected_pkgs, output_text=output_text, install_error=install_error, selected=selected)


@admin_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
@csrf_protect
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
        Setting.set('script_timeout', request.form.get('script_timeout', '30'))
        Setting.set('smtp_host', request.form.get('smtp_host', 'localhost'))
        Setting.set('smtp_port', request.form.get('smtp_port', '587'))
        Setting.set('smtp_user', request.form.get('smtp_user', ''))
        Setting.set('smtp_password', request.form.get('smtp_password', ''))
        Setting.set('smtp_from', request.form.get('smtp_from', 'noreply@example.com'))
        Setting.set('smtp_tls', 'true' if 'smtp_tls' in request.form else 'false')
        Setting.set('log_retention_days', request.form.get('log_retention_days', '0'))
        Setting.set('imap_host', request.form.get('imap_host', ''))
        Setting.set('imap_port', request.form.get('imap_port', '993'))
        Setting.set('imap_user', request.form.get('imap_user', ''))
        Setting.set('imap_password', request.form.get('imap_password', ''))
        Setting.set('imap_use_ssl', 'true' if 'imap_use_ssl' in request.form else 'false')
        Setting.set('imap_folder', request.form.get('imap_folder', 'INBOX'))
        Setting.set('imap_poll_interval', request.form.get('imap_poll_interval', '5'))
        Setting.set('imap_enabled', 'true' if 'imap_enabled' in request.form else 'false')
        Setting.set('imap_mark_seen', 'true' if 'imap_mark_seen' in request.form else 'false')
        Setting.set('imap_retention_days', request.form.get('imap_retention_days', '0'))
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
    script_timeout = Setting.get('script_timeout', '30')
    smtp_host = Setting.get('smtp_host', 'localhost')
    smtp_port = Setting.get('smtp_port', '587')
    smtp_user = Setting.get('smtp_user', '')
    smtp_password = Setting.get('smtp_password', '')
    smtp_from = Setting.get('smtp_from', 'noreply@example.com')
    smtp_tls = Setting.get('smtp_tls', 'true') == 'true'
    log_retention_days = Setting.get('log_retention_days', '0')
    imap_host = Setting.get('imap_host', '')
    imap_port = Setting.get('imap_port', '993')
    imap_user = Setting.get('imap_user', '')
    imap_password = Setting.get('imap_password', '')
    imap_use_ssl = Setting.get('imap_use_ssl', 'true') == 'true'
    imap_folder = Setting.get('imap_folder', 'INBOX')
    imap_poll_interval = Setting.get('imap_poll_interval', '5')
    imap_enabled = Setting.get('imap_enabled', 'false') == 'true'
    imap_mark_seen = Setting.get('imap_mark_seen', 'false') == 'true'
    imap_retention_days = Setting.get('imap_retention_days', '0')
    return render_admin('Settings', '''
<form method="POST">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
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
<label style="display:block;margin-bottom:12px;">
  <strong>Script Timeout (seconds)</strong><br>
  <input name="script_timeout" type="number" min="1" step="1" value="{{ script_timeout }}" style="padding:6px 10px;width:120px;"><br>
  <span style="color:#888;font-size:0.85em;">Max execution time for scripts before they are killed. Protects against runaway scripts.</span>
</label>
<label style="display:block;margin-bottom:12px;">
  <strong>Log Retention (days)</strong><br>
  <input name="log_retention_days" type="number" min="0" step="1" value="{{ log_retention_days }}" style="padding:6px 10px;width:120px;"><br>
  <span style="color:#888;font-size:0.85em;">Auto-delete execution logs older than this. 0 = keep forever.</span>
</label>

<h3>Incoming Mail (IMAP)</h3>
<label style="display:block;margin-bottom:12px;">
  <input name="imap_enabled" type="checkbox" {% if imap_enabled %}checked{% endif %}>
  <strong>Enable IMAP polling</strong><br>
  <span style="color:#888;font-size:0.85em;">When enabled, the scheduler will check for new emails on the configured IMAP mailbox.</span>
</label>
<label style="display:block;margin-bottom:12px;">
  <strong>IMAP Host</strong><br>
  <input name="imap_host" type="text" value="{{ imap_host }}" placeholder="imap.example.com" style="padding:6px 10px;width:100%;max-width:400px;">
</label>
<label style="display:block;margin-bottom:12px;">
  <strong>Port</strong><br>
  <input name="imap_port" type="number" value="{{ imap_port }}" style="padding:6px 10px;width:120px;">
</label>
<label style="display:block;margin-bottom:12px;">
  <strong>Username</strong><br>
  <input name="imap_user" type="text" value="{{ imap_user }}" style="padding:6px 10px;width:100%;max-width:400px;">
</label>
<label style="display:block;margin-bottom:12px;">
  <strong>Password</strong><br>
  <input name="imap_password" type="password" value="{{ imap_password }}" style="padding:6px 10px;width:100%;max-width:400px;">
</label>
<label style="display:block;margin-bottom:12px;">
  <input name="imap_use_ssl" type="checkbox" {% if imap_use_ssl %}checked{% endif %}>
  <strong>Use SSL</strong>
</label>
<label style="display:block;margin-bottom:12px;">
  <strong>Folder</strong><br>
  <input name="imap_folder" type="text" value="{{ imap_folder }}" style="padding:6px 10px;width:200px;">
</label>
<label style="display:block;margin-bottom:12px;">
  <strong>Poll Interval (minutes)</strong><br>
  <input name="imap_poll_interval" type="number" min="1" value="{{ imap_poll_interval }}" style="padding:6px 10px;width:120px;">
</label>
<label style="display:block;margin-bottom:12px;">
  <input name="imap_mark_seen" type="checkbox" {% if imap_mark_seen %}checked{% endif %}>
  <strong>Mark messages as seen after fetching</strong><br>
  <span style="color:#888;font-size:0.85em;">If unchecked, the system will fetch unseen messages but leave them unseen on the server.</span>
</label>
<label style="display:block;margin-bottom:12px;">
  <strong>Email Retention (days)</strong><br>
  <input name="imap_retention_days" type="number" min="0" step="1" value="{{ imap_retention_days }}" style="padding:6px 10px;width:120px;"><br>
  <span style="color:#888;font-size:0.85em;">Auto-delete processed incoming emails older than this. 0 = keep forever.</span>
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
<hr style="margin:20px 0;">
<h4>Send Test Email</h4>
<div style="background:#fafafa;border:1px solid #eee;padding:16px;border-radius:4px;margin-bottom:12px;">
  <label style="display:block;margin-bottom:10px;">
    <strong>To</strong><br>
    <input name="test_to" type="email" placeholder="you@example.com" style="padding:6px 10px;width:100%;max-width:400px;">
  </label>
  <label style="display:block;margin-bottom:10px;">
    <strong>Subject</strong><br>
    <input name="test_subject" type="text" value="Test email from PythonAppFoundry" style="padding:6px 10px;width:100%;max-width:400px;">
  </label>
  <label style="display:block;margin-bottom:10px;">
    <strong>Body (HTML)</strong><br>
    <textarea name="test_body" rows="4" style="padding:6px 10px;width:100%;max-width:400px;">&lt;h1&gt;Test&lt;/h1&gt;&lt;p&gt;If you can read this, your SMTP configuration is working.&lt;/p&gt;</textarea>
  </label>
  <button type="submit" formaction="{{ url_for('admin.test_email') }}" formmethod="POST" style="padding:6px 16px;background:#f0f0f0;color:#333;border:1px solid #ccc;border-radius:4px;cursor:pointer;">Send Test Email</button>
</div>
<div style="margin-top:16px;">
  <button style="padding:8px 20px;">Save All Settings</button>
</div>
</form>''',
        disabled=disabled, require_approval=require_approval,
        site_name=site_name,
        llm_provider=llm_provider, llm_endpoint=llm_endpoint,
        llm_api_key=llm_api_key, llm_model=llm_model,
        llm_temperature=llm_temperature, llm_max_tokens=llm_max_tokens,
        llm_timeout=llm_timeout, script_timeout=script_timeout,
        smtp_host=smtp_host, smtp_port=smtp_port,
        smtp_user=smtp_user, smtp_password=smtp_password,
        smtp_from=smtp_from, smtp_tls=smtp_tls,
        log_retention_days=log_retention_days,
        imap_host=imap_host, imap_port=imap_port, imap_user=imap_user,
        imap_password=imap_password, imap_use_ssl=imap_use_ssl,
        imap_folder=imap_folder, imap_poll_interval=imap_poll_interval,
        imap_enabled=imap_enabled, imap_mark_seen=imap_mark_seen,
        imap_retention_days=imap_retention_days)


@admin_bp.route('/settings/test-email', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def test_email():
    if request.method == 'GET':
        return redirect(url_for('admin.edit_settings'))
    to = request.form.get('test_to', '')
    subject = request.form.get('test_subject', 'Test email from PythonAppFoundry')
    body = request.form.get('test_body', '<h1>Test</h1><p>If you can read this, your SMTP configuration is working.</p>')
    if not to:
        flash('Please provide a recipient (To) address.', 'error')
        return redirect(url_for('admin.edit_settings'))
    try:
        from app.services.script_runner import _send_email
        _send_email(to=to, subject=subject, body=body, html=True)
        flash(f'Test email sent to {to}')
    except Exception as e:
        flash(f'Test email failed: {e}', 'error')
    return redirect(url_for('admin.edit_settings'))


# ── Query Reports ──

QUERY_LIST_TEMPLATE = '''<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;flex-wrap:wrap;">
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
{% endif %}'''

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

@admin_bp.route('/queries')
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
    return render_admin('Query Reports', QUERY_LIST_TEMPLATE,
                        queries=queries, modules=modules,
                        selected_module_id=selected_module_id,
                        sort_col=sort_col, sort_order=sort_order)


@admin_bp.route('/queries/new', methods=['GET', 'POST'])
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


@admin_bp.route('/queries/<int:id>', methods=['GET', 'POST'])
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


@admin_bp.route('/queries/<int:id>/delete', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def delete_query(id):
    q = QueryReport.query.get_or_404(id)
    db.session.delete(q)
    db.session.commit()
    flash('Query deleted')
    return redirect(url_for('admin.list_queries'))


@admin_bp.route('/queries/<int:id>/run')
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


# ── Dashboard ──

_dashboard_start_time = None

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    import platform as _platform
    import sqlite3 as _sqlite3
    import sys as _sys
    import flask as _flask
    import time as _time
    from datetime import timedelta

    global _dashboard_start_time
    if _dashboard_start_time is None:
        _dashboard_start_time = _time.time()
    uptime_seconds = _time.time() - _dashboard_start_time

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

    # Clean up old execution logs
    retention_days = int(Setting.get('log_retention_days', '0'))
    if retention_days > 0:
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        deleted = db.session.query(ExecutionLog).filter(ExecutionLog.created_at < cutoff).delete()
        if deleted:
            db.session.commit()

    # Clean up old incoming emails
    imap_retention_days = int(Setting.get('imap_retention_days', '0'))
    if imap_retention_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=imap_retention_days)
        deleted = db.session.query(IncomingEmail).filter(
            IncomingEmail.processed == True,
            IncomingEmail.created_at < cutoff,
        ).delete()
        if deleted:
            db.session.commit()

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
                       'execution_logs', 'module_dependencies', 'module_versions',
                       'query_reports', 'incoming_emails', 'credentials'}
    table_stats = []
    bind = db.session.get_bind()
    inspector = _sa_inspect(bind)
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
        flask_version=_flask.__version__,
        sqlite_version=_sqlite3.sqlite_version,
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


@admin_bp.route('/incoming-emails')
@admin_required
def list_incoming_emails():
    sort_col = request.args.get('sort', 'created_at')
    sort_order = request.args.get('order', 'desc')
    search = request.args.get('search', '')
    q = db.session.query(IncomingEmail)
    if search:
        q = q.filter(
            db.or_(
                IncomingEmail.subject.ilike(f'%{search}%'),
                IncomingEmail.from_address.ilike(f'%{search}%'),
            )
        )
    sort_attr = getattr(IncomingEmail, sort_col, None)
    if sort_attr is not None:
        q = q.order_by(sort_attr.desc() if sort_order == 'desc' else sort_attr.asc())
    else:
        q = q.order_by(IncomingEmail.created_at.desc())
    emails = q.all()

    if request.args.get('format') == 'csv':
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['id', 'message_id', 'subject', 'from_address', 'to_address', 'processed', 'created_at'])
        for e in emails:
            w.writerow([e.id, e.message_id, e.subject, e.from_address, e.to_address, e.processed, e.created_at])
        return Response(buf.getvalue(), mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=incoming_emails.csv'})

    return render_admin('Incoming Emails', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;flex-wrap:wrap;">
  <form method="GET" style="display:flex;gap:8px;align-items:center;flex:1;">
    <input name="search" type="text" placeholder="Search subject or sender..." value="{{ search }}" style="padding:6px 12px;border:1px solid #ddd;border-radius:4px;flex:1;max-width:300px;">
    <button type="submit" style="padding:6px 12px;">Search</button>
    {% if search %}<a href="{{ url_for('admin.list_incoming_emails') }}" style="color:#007bff;text-decoration:none;">Clear</a>{% endif %}
  </form>
  <a href="?format=csv{% if search %}&search={{ search }}{% endif %}" style="margin-left:auto;">Export CSV</a>
</div>
<div class="table-wrap">
<table>
<thead><tr>
  <th><a href="?sort=id&order={% if sort_col == 'id' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">ID{% if sort_col == 'id' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th>Subject</th>
  <th><a href="?sort=from_address&order={% if sort_col == 'from_address' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">From{% if sort_col == 'from_address' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th>To</th>
  <th><a href="?sort=processed&order={% if sort_col == 'processed' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">Status{% if sort_col == 'processed' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th><a href="?sort=module_slug&order={% if sort_col == 'module_slug' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">Module{% if sort_col == 'module_slug' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th><a href="?sort=created_at&order={% if sort_col == 'created_at' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">Received{% if sort_col == 'created_at' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th>Actions</th>
</tr></thead>
<tbody>
{% for e in emails %}
<tr>
  <td>{{ e.id }}</td>
  <td><strong>{{ e.subject[:80] if e.subject else '(no subject)' }}</strong></td>
  <td>{{ e.from_address[:60] }}</td>
  <td>{{ e.to_address[:60] if e.to_address else '—' }}</td>
  <td>{% if e.processed %}<span style="color:#080;">Processed</span>{% else %}<span style="color:#856404;">Pending</span>{% endif %}</td>
  <td>{{ e.module_slug or '—' }}</td>
  <td style="white-space:nowrap;">{{ e.created_at|localtime }}</td>
  <td>
    <a href="{{ url_for('admin.view_incoming_email', id=e.id) }}">View</a>
    {% if not e.processed %}
    <form method="POST" action="{{ url_for('admin.mark_incoming_processed', id=e.id) }}" style="display:inline">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <button type="submit" style="background:none;border:none;color:#080;cursor:pointer;text-decoration:underline;padding:0;font:inherit;font-size:0.9em;">Mark Done</button>
    </form>
    {% endif %}
    <form method="POST" action="{{ url_for('admin.delete_incoming_email', id=e.id) }}" style="display:inline" onsubmit="return confirm('Delete email #{{ e.id }}?')">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <button type="submit" style="background:none;border:none;color:#c00;cursor:pointer;text-decoration:underline;padding:0;font:inherit;font-size:0.9em;">Delete</button>
    </form>
  </td>
</tr>
{% endfor %}
</tbody></table>
</div>
{% if not emails %}
<p style="color:#888;">No incoming emails yet. Configure IMAP settings and enable polling to start receiving emails.</p>
{% endif %}''', emails=emails, sort_col=sort_col, sort_order=sort_order, search=search)


@admin_bp.route('/incoming-emails/<int:id>')
@admin_required
def view_incoming_email(id):
    e = IncomingEmail.query.get_or_404(id)
    return render_admin(f'Email: {e.subject or "(no subject)"}', '''
<h2>{{ e.subject or '(no subject)' }}</h2>
<table>
<tr><th>ID</th><td>{{ e.id }}</td></tr>
<tr><th>From</th><td>{{ e.from_address }}</td></tr>
<tr><th>To</th><td>{{ e.to_address }}</td></tr>
<tr><th>Message-ID</th><td><code>{{ e.message_id }}</code></td></tr>
<tr><th>Received</th><td>{{ e.created_at|localtime }}</td></tr>
<tr><th>Status</th><td>{% if e.processed %}Processed{% else %}Pending{% endif %}</td></tr>
{% if e.module_slug %}<tr><th>Claimed By</th><td>{{ e.module_slug }}</td></tr>{% endif %}
{% if e.attachments %}<tr><th>Attachments</th><td>{{ e.attachments }}</td></tr>{% endif %}
</table>
{% if e.body_html %}
<h3>HTML Body</h3>
<div style="border:1px solid #ddd;border-radius:4px;padding:1rem;margin-bottom:1rem;max-height:500px;overflow-y:auto;background:#fff;">
  {{ e.body_html|safe }}
</div>
{% endif %}
{% if e.body_text %}
<h3>Plain Text Body</h3>
<pre style="background:#f4f4f4;padding:1rem;border-radius:4px;overflow:auto;white-space:pre-wrap;word-wrap:break-word;">{{ e.body_text }}</pre>
{% endif %}
<div style="margin-top:1rem;">
  <a href="{{ url_for('admin.list_incoming_emails') }}">&larr; Back</a>
  {% if not e.processed %}
  <form method="POST" action="{{ url_for('admin.mark_incoming_processed', id=e.id) }}" style="display:inline;margin-left:0.5rem;">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <button type="submit" style="background:#080;color:#fff;border:none;padding:6px 16px;border-radius:4px;cursor:pointer;">Mark as Processed</button>
  </form>
  {% endif %}
</div>''', e=e)


@admin_bp.route('/incoming-emails/<int:id>/processed', methods=['POST'])
@admin_required
@csrf_protect
def mark_incoming_processed(id):
    e = IncomingEmail.query.get_or_404(id)
    from datetime import datetime, timezone
    e.processed = True
    e.processed_at = datetime.now(timezone.utc)
    db.session.commit()
    flash(f'Email #{id} marked as processed')
    return redirect(url_for('admin.view_incoming_email', id=id))


@admin_bp.route('/incoming-emails/<int:id>/delete', methods=['POST'])
@admin_required
@csrf_protect
def delete_incoming_email(id):
    e = IncomingEmail.query.get_or_404(id)
    db.session.delete(e)
    db.session.commit()
    flash(f'Email #{id} deleted')
    return redirect(url_for('admin.list_incoming_emails'))


@admin_bp.route('/credentials')
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


@admin_bp.route('/credentials/new', methods=['GET', 'POST'])
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


@admin_bp.route('/credentials/edit/<int:id>', methods=['GET', 'POST'])
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


@admin_bp.route('/credentials/<int:id>/delete', methods=['POST'])
@admin_required
@csrf_protect
def delete_credential(id):
    c = Credential.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    flash(f'Credential "{c.name}" deleted')
    return redirect(url_for('admin.list_credentials'))


@admin_bp.route('/integration-health')
@admin_required
def integration_health():
    # Recent script execution logs — filter by script source_type
    limit = request.args.get('limit', 100, type=int)
    module_id = request.args.get('module_id', type=int)

    logs_q = db.session.query(ExecutionLog).filter(
        ExecutionLog.source_type.in_(['script', 'task'])
    )

    if module_id:
        # Find scripts in this module, then filter logs by their names
        script_names = [
            s.name for s in db.session.query(Script.name).filter(Script.module_id == module_id)
        ]
        if script_names:
            logs_q = logs_q.filter(ExecutionLog.source_name.in_(script_names))

    logs_q = logs_q.order_by(ExecutionLog.created_at.desc()).limit(limit)
    logs = logs_q.all()

    # Aggregated stats
    total_runs = len(logs)
    errors = [l for l in logs if l.status == 'error']
    error_rate = round(len(errors) / total_runs * 100, 1) if total_runs else 0
    avg_duration = sum(l.duration_ms for l in logs) / total_runs if total_runs else 0

    modules = db.session.query(Module).order_by(Module.name).all()

    return render_admin('Integration Health', '''
<div style="display:flex;gap:1rem;margin-bottom:1rem;flex-wrap:wrap;">
  <div class="dash-card" style="flex:1;min-width:120px;"><h3>Recent Runs</h3><div class="value">{{ total_runs }}</div></div>
  <div class="dash-card" style="flex:1;min-width:120px;"><h3>Errors</h3><div class="value" style="color:{% if errors %} #c00{% else %}#080{% endif %};">{{ errors|length }}</div><div class="sub">{{ error_rate }}% error rate</div></div>
  <div class="dash-card" style="flex:1;min-width:120px;"><h3>Avg Duration</h3><div class="value">{{ '%d'|format(avg_duration) }}ms</div></div>
</div>
<form method="GET" style="margin-bottom:1rem;display:flex;gap:8px;align-items:center;">
  <select name="module_id" onchange="this.form.submit()" style="padding:4px 8px;">
    <option value="">All Modules</option>
    {% for m in modules %}
    <option value="{{ m.id }}" {% if module_id == m.id %}selected{% endif %}>{{ m.name }}</option>
    {% endfor %}
  </select>
  <input name="limit" type="hidden" value="{{ limit }}">
  <noscript><button type="submit">Filter</button></noscript>
  {% if module_id %}<a href="{{ url_for('admin.integration_health') }}" style="color:#007bff;">Clear</a>{% endif %}
</form>
<div class="table-wrap">
<table>
<thead><tr>
  <th>Time</th><th>Script / Task</th><th>Status</th><th>Duration</th><th>Detail</th>
</tr></thead>
<tbody>
{% for log in logs %}
<tr>
  <td style="white-space:nowrap;font-size:0.85em;">{{ log.created_at|localtime }}</td>
  <td><strong>{{ log.source_name }}</strong><br><span style="font-size:0.8em;color:#888;">{{ log.source_type }}</span></td>
  <td><span class="{% if log.status == 'success' %}status-ok{% else %}status-err{% endif %}">{{ log.status|upper }}</span></td>
  <td>{{ log.duration_ms }}ms</td>
  <td>
    {% if log.error_message %}
    <button onclick="showLogDetail({{ log.id }}, this.nextElementSibling)" style="font-size:0.8em;padding:2px 8px;cursor:pointer;background:#fee;border:1px solid #c00;color:#c00;border-radius:3px;">View Error</button>
    <span style="display:none;">{{ log.error_message[:2000] }}</span>
    {% elif log.stdout %}
    <span style="color:#888;font-size:0.85em;">{{ log.stdout[:200] }}</span>
    {% else %}<span style="color:#999;font-size:0.85em;">—</span>{% endif %}
  </td>
</tr>
{% endfor %}
</tbody></table>
</div>
{% if not logs %}<p style="color:#888;">No script or task execution logs yet. Run a script to see results here.</p>{% endif %}
''', logs=logs, total_runs=total_runs, errors=errors, error_rate=error_rate,
        avg_duration=avg_duration, modules=modules, module_id=module_id, limit=limit)


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
function showLogDetail(id, msgEl) {
  var modal = document.getElementById('logModal');
  var content = document.getElementById('logContent');
  var message = msgEl ? msgEl.textContent || msgEl.innerText : 'No details available.';
  content.innerHTML = '<h3>Execution Log #' + id + '</h3>';
  var pre = document.createElement('pre');
  pre.textContent = message;
  content.appendChild(pre);
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
        <button onclick="showLogDetail({{ log.id }}, this.nextElementSibling)" style="font-size:0.8em;padding:2px 8px;cursor:pointer;background:#fee;border:1px solid #c00;color:#c00;border-radius:3px;">View Error</button>
        <span style="display:none;">{{ log.error_message[:2000] }}</span>
        {% elif log.stdout %}
        <button onclick="showLogDetail({{ log.id }}, this.nextElementSibling)" style="font-size:0.8em;padding:2px 8px;cursor:pointer;background:#efe;border:1px solid #080;color:#080;border-radius:3px;">View Output</button>
        <span style="display:none;">{{ log.stdout[:2000] }}</span>
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


# ── Backup & Restore ──

@admin_bp.route('/backup')
@admin_required
def backup_database():
    """Create a database backup."""
    from app.services.backup import create_backup
    try:
        backup_path = create_backup()
        flash(f'Backup created: {os.path.basename(backup_path)}')
        return redirect(url_for('admin.list_backups'))
    except Exception as e:
        flash(f'Backup failed: {e}', 'error')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/backups')
@admin_required
def list_backups():
    """List available backups."""
    from app.services.backup import list_backups as _list_backups
    backups = _list_backups()
    return render_admin('Backups', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.backup_database') }}">Create New Backup</a>
  <a href="?format=csv" style="margin-left:auto;">Export CSV</a>
</div>
{% if backups %}
<div class="table-wrap">
<table>
<thead><tr>
  <th>Filename</th>
  <th>Size</th>
  <th>Created</th>
  <th>Actions</th>
</tr></thead>
<tbody>
{% for b in backups %}
<tr>
  <td><code>{{ b.filename }}</code></td>
  <td>{{ '%0.1f MB'|format(b.size / 1048576) }}</td>
  <td>{{ b.created_at.strftime('%Y-%m-%d %H:%M UTC') }}</td>
  <td>
    <a href="{{ url_for('admin.download_backup', path=b.filename) }}">Download</a>
    <form method="POST" action="{{ url_for('admin.delete_backup', path=b.filename) }}" style="display:inline" onsubmit="return confirm('Delete backup {{ b.filename }}?')">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <button type="submit" style="background:none;border:none;color:#c00;cursor:pointer;text-decoration:underline;padding:0;font:inherit">Delete</button>
    </form>
  </td>
</tr>
{% endfor %}
</tbody></table>
</div>
{% else %}
<p style="color:#888;">No backups found. Create one to get started.</p>
{% endif %}''', backups=backups)


@admin_bp.route('/backups/<path:path>/download')
@admin_required
def download_backup(path):
    """Download a backup file."""
    from app.services.backup import list_backups, download_backup as _download
    backups = list_backups()
    for b in backups:
        if b['filename'] == path:
            return _download(b['path'])
    flash('Backup not found', 'error')
    return redirect(url_for('admin.list_backups'))


@admin_bp.route('/backups/<path:path>/delete', methods=['POST'])
@admin_required
@csrf_protect
def delete_backup(path):
    """Delete a backup file."""
    from app.services.backup import list_backups, delete_backup as _delete
    backups = list_backups()
    for b in backups:
        if b['filename'] == path:
            _delete(b['path'])
            flash(f'Backup {path} deleted')
            return redirect(url_for('admin.list_backups'))
    flash('Backup not found', 'error')
    return redirect(url_for('admin.list_backups'))


@admin_bp.route('/backups/restore/<path:path>', methods=['POST'])
@admin_required
@csrf_protect
def restore_backup(path):
    """Restore database from a backup."""
    from app.services.backup import list_backups, restore_backup as _restore
    backups = list_backups()
    for b in backups:
        if b['filename'] == path:
            try:
                _restore(b['path'])
                flash(f'Database restored from {path}. Restart the application to apply changes.')
                return redirect(url_for('admin.list_backups'))
            except Exception as e:
                flash(f'Restore failed: {e}', 'error')
                return redirect(url_for('admin.list_backups'))
    flash('Backup not found', 'error')
    return redirect(url_for('admin.list_backups'))


# ── Execution History per Module ──

@admin_bp.route('/modules/<int:module_id>/executions')
@developer_or_admin_required
def module_executions(module_id):
    """Show recent execution logs for a specific module."""
    from app.models import Script, ExecutionLog
    module = db.session.get(Module, module_id)
    if not module:
        flash('Module not found', 'error')
        return redirect(url_for('admin.list_modules'))
    
    # Get scripts in this module
    scripts = db.session.query(Script).filter_by(module_id=module_id).all()
    script_names = [s.name for s in scripts]
    
    # Get recent executions for these scripts
    limit = request.args.get('limit', 50, type=int)
    logs = db.session.query(ExecutionLog).filter(
        ExecutionLog.source_name.in_(script_names),
        ExecutionLog.source_type == 'script'
    ).order_by(ExecutionLog.created_at.desc()).limit(limit).all()
    
    return render_admin(f'Executions: {module.name}', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.edit_module', id=m.id) }}">Back to Module</a>
  <form method="GET" style="display:inline;">
    <input type="hidden" name="limit" value="{{ limit }}">
    <select name="status" onchange="this.form.submit()" style="padding:4px 8px;">
      <option value="">All Statuses</option>
      <option value="success" {% if status_filter == 'success' %}selected{% endif %}>Success</option>
      <option value="error" {% if status_filter == 'error' %}selected{% endif %}>Error</option>
    </select>
  </form>
</div>
{% if logs %}
<div class="table-wrap">
<table>
<thead><tr>
  <th>Time</th>
  <th>Script</th>
  <th>Status</th>
  <th>Duration</th>
  <th>Details</th>
</tr></thead>
<tbody>
{% for log in logs %}
<tr>
  <td style="white-space:nowrap;font-size:0.85em;">{{ log.created_at.strftime('%Y-%m-%d %H:%M:%S') }}</td>
  <td><strong>{{ log.source_name }}</strong></td>
  <td><span class="{% if log.status == 'success' %}status-ok{% else %}status-err{% endif %}">{{ log.status|upper }}</span></td>
  <td>{{ log.duration_ms }}ms</td>
  <td>
    {% if log.error_message %}
      <span style="color:#c00;font-size:0.85em;">{{ log.error_message[:100] }}...</span>
    {% elif log.stdout %}
      <span style="color:#888;font-size:0.85em;">{{ log.stdout[:100] }}...</span>
    {% else %}
      <span style="color:#999;font-size:0.85em;">—</span>
    {% endif %}
  </td>
</tr>
{% endfor %}
</tbody></table>
</div>
{% else %}
<p style="color:#888;">No executions found for this module.</p>
{% endif %}''', m=module, logs=logs, limit=limit, status_filter='')


# ── Test Script (AJAX endpoint) ──

@admin_bp.route('/scripts/test/<int:id>', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def test_script(id):
    """Test a script by executing it and returning the result as JSON."""
    from app.services.script_runner import execute_script
    s = Script.query.get_or_404(id)
    
    import time
    t0 = time.time()
    import sys
    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    
    error = None
    output = None
    result = None
    try:
        result = execute_script(s)
        output = sys.stdout.getvalue()
        duration = int((time.time() - t0) * 1000)
    except Exception as e:
        import traceback
        error = traceback.format_exc()
        output = sys.stdout.getvalue()
        duration = int((time.time() - t0) * 1000)
    finally:
        sys.stdout = old_stdout
    
    return jsonify({
        'success': error is None,
        'result': str(result)[:2000] if result else None,
        'output': output[:2000] if output else '',
        'error': error[:2000] if error else None,
        'duration_ms': duration,
    })


# ── Import Preview ──

@admin_bp.route('/import-preview', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def import_preview():
    """Preview what will be imported from an XML file without actually importing."""
    if 'import_xml' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    xml_file = request.files['import_xml']
    if not xml_file.filename:
        return jsonify({'error': 'Empty filename'}), 400
    
    try:
        from app.services.bundle import import_module
        xml_str = xml_file.read().decode('utf-8')
        
        # Parse XML to extract preview info without importing
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_str)
        
        if root.tag != 'module':
            return jsonify({'error': 'Root element must be <module>'}), 400
        
        name = root.get('name', 'Untitled')
        slug = root.get('slug', '')
        
        # Count items that would be imported
        scripts = root.find('scripts')
        script_count = len(scripts.findall('script')) if scripts is not None else 0
        
        routes = root.find('routes')
        route_count = len(routes.findall('route')) if routes is not None else 0
        
        forms = root.find('forms')
        form_count = len(forms.findall('form')) if forms is not None else 0
        
        tasks = root.find('scheduled_tasks')
        task_count = len(tasks.findall('task')) if tasks is not None else 0
        
        triggers = root.find('triggers')
        trigger_count = len(triggers.findall('trigger')) if triggers is not None else 0
        
        # Check for existing module with same slug
        existing = db.session.query(Module).filter_by(slug=slug).first()
        
        return jsonify({
            'success': True,
            'preview': {
                'name': name,
                'slug': slug,
                'existing': existing is not None,
                'existing_id': existing.id if existing else None,
                'counts': {
                    'scripts': script_count,
                    'routes': route_count,
                    'forms': form_count,
                    'tasks': task_count,
                    'triggers': trigger_count,
                }
            }
        })
    except ET.ParseError as e:
        return jsonify({'error': f'Invalid XML: {e}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400


# ── Module Marketplace ──

@admin_bp.route('/marketplace')
@developer_or_admin_required
def module_marketplace():
    """Browse and install modules from the marketplace."""
    from app.services.marketplace import list_available_modules
    available = list_available_modules()
    
    # Check which are already installed
    installed_slugs = {m.slug for m in db.session.query(Module.slug).all()}
    
    return render_admin('Module Marketplace', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.list_modules') }}">Back to Modules</a>
</div>
{% if available %}
<div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(300px, 1fr));gap:1rem;">
{% for mod in available %}
<div style="border:1px solid #ddd;border-radius:8px;padding:1rem;">
  <h3 style="margin-top:0;">{{ mod.name }}</h3>
  <p style="color:#666;font-size:0.9em;">{{ mod.description[:200] }}...</p>
  <div style="font-size:0.85em;color:#888;margin-bottom:0.5rem;">
    Version: {{ mod.version }} | Author: {{ mod.author }}
    {% if mod.tags %} | Tags: {{ mod.tags|join(', ') }}{% endif %}
  </div>
  {% if mod.slug in installed_slugs %}
    <span style="color:#080;font-weight:bold;">Installed</span>
  {% else %}
    <form method="POST" action="{{ url_for('admin.install_marketplace_module', slug=mod.slug) }}" style="display:inline;">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <button type="submit" style="padding:6px 16px;background:#2563eb;color:#fff;border:none;border-radius:4px;cursor:pointer;">Install</button>
    </form>
  {% endif %}
</div>
{% endfor %}
</div>
{% else %}
<p style="color:#888;">No modules available in the marketplace yet.</p>
{% endif %}''', available=available, installed_slugs=installed_slugs)


@admin_bp.route('/marketplace/<slug>/install', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def install_marketplace_module(slug):
    """Install a module from the marketplace."""
    from app.services.marketplace import get_module_info
    from app.services.bundle import import_module
    
    info = get_module_info(slug)
    if not info:
        flash(f'Module "{slug}" not found in marketplace', 'error')
        return redirect(url_for('admin.module_marketplace'))
    
    xml_path = info.get('xml_source')
    if not xml_path or not os.path.exists(xml_path):
        flash(f'Module XML not found for "{slug}"', 'error')
        return redirect(url_for('admin.module_marketplace'))
    
    try:
        with open(xml_path) as f:
            xml_str = f.read()
        module = import_module(xml_str)
        flash(f'Module "{module.name}" installed from marketplace')
    except Exception as e:
        flash(f'Installation failed: {e}', 'error')
    
    return redirect(url_for('admin.module_marketplace'))


# ── Blueprint Registration ──
# Import and register all admin blueprints
from app.routes.admin_blueprints import register_admin_blueprints

# Register all blueprints with the admin blueprint
register_admin_blueprints(admin_bp)

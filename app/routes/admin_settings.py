"""Admin routes for settings management."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required
from app import db
from app.models import Setting

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def edit_settings():
    if request.method == 'POST':
        # Check if this is a test email submission
        if 'test_to' in request.form:
            return _handle_test_email()
        
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


@settings_bp.route('/settings/test-email', methods=['GET', 'POST'])
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


def _handle_test_email():
    """Handle test email submission."""
    from flask import request, redirect, url_for, flash
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

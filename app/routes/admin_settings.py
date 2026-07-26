from flask import Blueprint, request, redirect, url_for, render_template_string, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required, render_admin
from app import db
from app.models import Setting

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/settings', methods=['GET', 'POST'])
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
        return redirect(url_for('admin.settings.edit_settings'))
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
    return render_admin('Settings', 'admin/settings/edit.html',
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
        return redirect(url_for('admin.settings.edit_settings'))
    to = request.form.get('test_to', '')
    subject = request.form.get('test_subject', 'Test email from PythonAppFoundry')
    body = request.form.get('test_body', '<h1>Test</h1><p>If you can read this, your SMTP configuration is working.</p>')
    if not to:
        flash('Please provide a recipient (To) address.', 'error')
        return redirect(url_for('admin.settings.edit_settings'))
    try:
        from app.services.script_runner import _send_email
        _send_email(to=to, subject=subject, body=body, html=True)
        flash(f'Test email sent to {to}')
    except Exception as e:
        flash(f'Test email failed: {e}', 'error')
    return redirect(url_for('admin.settings.edit_settings'))

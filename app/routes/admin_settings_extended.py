"""Admin routes for extended settings."""
from flask import Blueprint, request, redirect, url_for, flash

settings_extended_bp = Blueprint('settings_extended', __name__)


@settings_extended_bp.route('/settings/advanced', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def advanced_settings():
    """Advanced settings configuration."""
    from app.models import Setting
    
    if request.method == 'POST':
        # Save advanced settings
        Setting.set('max_upload_size', request.form.get('max_upload_size', '10485760'))
        Setting.set('session_timeout', request.form.get('session_timeout', '3600'))
        Setting.set('password_min_length', request.form.get('password_min_length', '4'))
        Setting.set('enable_registration', 'true' if 'enable_registration' in request.form else 'false')
        flash('Advanced settings saved')
        return redirect(url_for('admin.advanced_settings'))
    
    max_upload_size = Setting.get('max_upload_size', '10485760')
    session_timeout = Setting.get('session_timeout', '3600')
    password_min_length = Setting.get('password_min_length', '4')
    enable_registration = Setting.get('enable_registration', 'true') == 'true'
    
    return render_admin('Advanced Settings', '''
<form method="POST">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<h3>Upload Settings</h3>
<label>Max Upload Size (bytes) <input name="max_upload_size" value="{{ max_upload_size }}"></label>

<h3>Session Settings</h3>
<label>Session Timeout (seconds) <input name="session_timeout" value="{{ session_timeout }}"></label>

<h3>Password Policy</h3>
<label>Minimum Password Length <input name="password_min_length" type="number" value="{{ password_min_length }}"></label>

<h3>Registration</h3>
<label><input name="enable_registration" type="checkbox" {% if enable_registration %}checked{% endif %}> Enable User Registration</label>

<button type="submit" style="margin-top:1rem;padding:8px 20px;background:#2563eb;color:#fff;border:none;border-radius:4px;cursor:pointer;">Save Advanced Settings</button>
</form>
''', max_upload_size=max_upload_size, session_timeout=session_timeout, password_min_length=password_min_length, enable_registration=enable_registration)

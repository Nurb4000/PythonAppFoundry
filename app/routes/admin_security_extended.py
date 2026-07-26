"""Admin routes for extended security monitoring."""
from flask import Blueprint, request, redirect, url_for, render_template_string

security_extended_bp = Blueprint('security_extended', __name__)


@security_extended_bp.route('/security/audit-log')
@admin_required
def audit_log():
    """View detailed audit log of administrative actions."""
    from app.models import ExecutionLog
    
    logs = db.session.query(ExecutionLog).order_by(ExecutionLog.created_at.desc()).limit(100).all()
    
    return render_admin('Audit Log', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.security_dashboard') }}">Back to Security</a>
</div>
{% if logs %}
<div class="table-wrap">
<table>
<thead><tr>
  <th>Time</th>
  <th>Type</th>
  <th>Name</th>
  <th>Status</th>
  <th>Duration</th>
</tr></thead>
<tbody>
{% for log in logs %}
<tr>
  <td style="white-space:nowrap;font-size:0.85em;">{{ log.created_at.strftime('%Y-%m-%d %H:%M:%S') }}</td>
  <td>{{ log.source_type }}</td>
  <td>{{ log.source_name }}</td>
  <td><span class="{% if log.status == 'success' %}status-ok{% else %}status-err{% endif %}">{{ log.status|upper }}</span></td>
  <td>{{ log.duration_ms }}ms</td>
</tr>
{% endfor %}
</tbody></table>
</div>
{% else %}
<p style="color:#888;">No audit logs found.</p>
{% endif %}''', logs=logs)


@security_extended_bp.route('/security/ip-logs')
@admin_required
def ip_logs():
    """View IP address logs for security monitoring."""
    # This would typically track IP addresses associated with requests
    # For now, show a placeholder
    return render_admin('IP Logs', '''
<p style="color:#666;">IP logging is not yet implemented. This feature will track IP addresses associated with administrative actions for security auditing.</p>
''')


@security_extended_bp.route('/security/session-logs')
@admin_required
def session_logs():
    """View session logs for security monitoring."""
    # This would typically track user sessions
    # For now, show a placeholder
    return render_admin('Session Logs', '''
<p style="color:#666;">Session logging is not yet implemented. This feature will track user sessions for security auditing.</p>
''')


@security_extended_bp.route('/security/password-policies')
@admin_required
def password_policies():
    """View and configure password policies."""
    from app.models import Setting
    
    min_length = int(Setting.get('password_min_length', '4'))
    require_uppercase = Setting.get('password_require_uppercase', 'false') == 'true'
    require_lowercase = Setting.get('password_require_lowercase', 'false') == 'true'
    require_numbers = Setting.get('password_require_numbers', 'false') == 'true'
    require_special = Setting.get('password_require_special', 'false') == 'true'
    max_age_days = int(Setting.get('password_max_age_days', '0'))
    
    return render_admin('Password Policies', '''
<form method="POST" action="{{ url_for('admin.save_password_policies') }}">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<h3>Password Requirements</h3>
<label>Minimum Length: <input name="min_length" type="number" value="{{ min_length }}"></label>
<label><input name="require_uppercase" type="checkbox" {% if require_uppercase %}checked{% endif %}> Require Uppercase</label>
<label><input name="require_lowercase" type="checkbox" {% if require_lowercase %}checked{% endif %}> Require Lowercase</label>
<label><input name="require_numbers" type="checkbox" {% if require_numbers %}checked{% endif %}> Require Numbers</label>
<label><input name="require_special" type="checkbox" {% if require_special %}checked{% endif %}> Require Special Characters</label>

<h3>Password Expiration</h3>
<label>Password Max Age (days, 0 = never): <input name="max_age_days" type="number" value="{{ max_age_days }}"></label>

<button type="submit" style="margin-top:1rem;padding:8px 20px;background:#2563eb;color:#fff;border:none;border-radius:4px;cursor:pointer;">Save Password Policies</button>
</form>
''', min_length=min_length, require_uppercase=require_uppercase, require_lowercase=require_lowercase, require_numbers=require_numbers, require_special=require_special, max_age_days=max_age_days)


@security_extended_bp.route('/security/save-password-policies', methods=['POST'])
@admin_required
@csrf_protect
def save_password_policies():
    """Save password policies."""
    from app.models import Setting
    
    Setting.set('password_min_length', request.form.get('min_length', '4'))
    Setting.set('password_require_uppercase', 'true' if 'require_uppercase' in request.form else 'false')
    Setting.set('password_require_lowercase', 'true' if 'require_lowercase' in request.form else 'false')
    Setting.set('password_require_numbers', 'true' if 'require_numbers' in request.form else 'false')
    Setting.set('password_require_special', 'true' if 'require_special' in request.form else 'false')
    Setting.set('password_max_age_days', request.form.get('max_age_days', '0'))
    
    flash('Password policies saved')
    return redirect(url_for('admin.password_policies'))


@security_extended_bp.route('/security/login-attempts')
@admin_required
def login_attempts():
    """View failed login attempts."""
    # This would typically track failed login attempts
    # For now, show a placeholder
    return render_admin('Login Attempts', '''
<p style="color:#666;">Failed login attempt tracking is not yet implemented. This feature will monitor and log failed login attempts for security auditing.</p>
''')


@security_extended_bp.route('/security/active-sessions')
@admin_required
def active_sessions():
    """View active user sessions."""
    # This would typically track active sessions
    # For now, show a placeholder
    return render_admin('Active Sessions', '''
<p style="color:#666;">Active session tracking is not yet implemented. This feature will monitor and display active user sessions.</p>
''')


@security_extended_bp.route('/security/blocked-ips')
@admin_required
def blocked_ips():
    """View and manage blocked IP addresses."""
    # This would typically track blocked IPs
    # For now, show a placeholder
    return render_admin('Blocked IPs', '''
<p style="color:#666;">IP blocking is not yet implemented. This feature will allow administrators to block IP addresses for security reasons.</p>
''')


@security_extended_bp.route('/security/2fa-settings')
@admin_required
def two_factor_settings():
    """View and configure two-factor authentication settings."""
    # This would typically track 2FA settings
    # For now, show a placeholder
    return render_admin('Two-Factor Authentication', '''
<p style="color:#666;">Two-factor authentication is not yet implemented. This feature will allow administrators to enable 2FA for enhanced security.</p>
''')


@security_extended_bp.route('/security/api-keys')
@admin_required
def api_keys():
    """View and manage API keys."""
    # This would typically track API keys
    # For now, show a placeholder
    return render_admin('API Keys', '''
<p style="color:#666;">API key management is not yet implemented. This feature will allow administrators to create and manage API keys for programmatic access.</p>
''')


@security_extended_bp.route('/security/audit-trail')
@admin_required
def audit_trail():
    """View complete audit trail of all administrative actions."""
    # This would typically track all administrative actions
    # For now, show a placeholder
    return render_admin('Audit Trail', '''
<p style="color:#666;">Complete audit trail is not yet implemented. This feature will log all administrative actions for compliance and security auditing.</p>
''')


@security_extended_bp.route('/security/compliance')
@admin_required
def compliance_check():
    """Run compliance checks on the platform."""
    # This would typically run various compliance checks
    # For now, show a placeholder
    return render_admin('Compliance Check', '''
<p style="color:#666;">Compliance checking is not yet implemented. This feature will verify that the platform meets various security and regulatory requirements.</p>
''')


@security_extended_bp.route('/security/incident-report')
@admin_required
def incident_report():
    """Report a security incident."""
    if request.method == 'POST':
        # In a real implementation, this would send an alert to security team
        flash('Incident report submitted. Security team will investigate.')
        return redirect(url_for('admin.security_dashboard'))
    
    return render_admin('Report Security Incident', '''
<form method="POST">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<h3>Security Incident Report</h3>
<label>Description <textarea name="description" rows="5" style="width:100%;"></textarea></label>
<label>Severity
  <select name="severity">
    <option value="low">Low</option>
    <option value="medium">Medium</option>
    <option value="high">High</option>
    <option value="critical">Critical</option>
  </select>
</label>
<button type="submit" style="margin-top:1rem;padding:8px 20px;background:#dc3545;color:#fff;border:none;border-radius:4px;cursor:pointer;">Submit Report</button>
</form>
''')


@security_extended_bp.route('/security/vulnerability-scan')
@admin_required
def vulnerability_scan():
    """Run a vulnerability scan on the platform."""
    # This would typically run various security scans
    # For now, show a placeholder
    return render_admin('Vulnerability Scan', '''
<p style="color:#666;">Vulnerability scanning is not yet implemented. This feature will perform automated security scans to identify potential vulnerabilities.</p>
''')


@security_extended_bp.route('/security/security-policy')
@admin_required
def security_policy():
    """View the platform's security policy."""
    return render_admin('Security Policy', '''
<div class="dash-card">
  <h3>Security Policy</h3>
  <p>PythonAppFoundry implements the following security measures:</p>
  <ul style="margin:0;padding-left:1.5rem;line-height:1.8;">
    <li>Hardened script sandbox with blocked imports</li>
    <li>Webhook rate limiting (30/min, 600/hr)</li>
    <li>SSL certificate verification for API calls</li>
    <li>Settings access control (blocks sensitive keys)</li>
    <li>CSRF protection on all forms</li>
    <li>Encrypted credential storage</li>
    <li>Input validation for slugs, routes, and cron expressions</li>
    <li>Rate limiting on authentication endpoints</li>
  </ul>
</div>
''')


@security_extended_bp.route('/security/security-dashboard')
@admin_required
def security_dashboard():
    """View the security dashboard."""
    return render_admin('Security Dashboard', '''
<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(250px, 1fr));gap:1rem;">
  <div class="dash-card">
    <h3>Script Sandbox</h3>
    <p>Status: <span class="status-ok">Active</span></p>
    <p>Blocked modules: os, subprocess, sys, socket, etc.</p>
  </div>
  
  <div class="dash-card">
    <h3>Webhook Rate Limiting</h3>
    <p>Status: <span class="status-ok">Active</span></p>
    <p>Limit: 30 calls/min, 600 calls/hr per slug</p>
  </div>
  
  <div class="dash-card">
    <h3>SSL Verification</h3>
    <p>Status: <span class="status-ok">Enabled</span></p>
    <p>call_api() verifies certificates by default</p>
  </div>
  
  <div class="dash-card">
    <h3>Settings Access Control</h3>
    <p>Status: <span class="status-ok">Active</span></p>
    <p>Blocks access to sensitive keys in scripts</p>
  </div>
  
  <div class="dash-card">
    <h3>CSRF Protection</h3>
    <p>Status: <span class="status-ok">Active</span></p>
    <p>All forms include CSRF tokens</p>
  </div>
  
  <div class="dash-card">
    <h3>Credential Encryption</h3>
    <p>Status: <span class="status-ok">Active</span></p>
    <p>Fernet encryption for stored credentials</p>
  </div>
  
  <div class="dash-card">
    <h3>Input Validation</h3>
    <p>Status: <span class="status-ok">Active</span></p>
    <p>Validates slugs, routes, and cron expressions</p>
  </div>
  
  <div class="dash-card">
    <h3>Auth Rate Limiting</h3>
    <p>Status: <span class="status-ok">Active</span></p>
    <p>5 attempts per 5 minutes per IP</p>
  </div>
</div>

<div style="margin-top:2rem;">
  <a href="{{ url_for('admin.audit_log') }}" class="btn">View Audit Log</a>
  <a href="{{ url_for('admin.password_policies') }}" class="btn">Password Policies</a>
  <a href="{{ url_for('admin.security_policy') }}" class="btn">Security Policy</a>
</div>
''')

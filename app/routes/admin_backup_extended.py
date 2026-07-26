"""Admin routes for extended backup functionality."""
from flask import Blueprint, request, redirect, url_for, flash

backup_extended_bp = Blueprint('backup_extended', __name__)


@backup_extended_bp.route('/backup/schedule', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def backup_schedule():
    """Configure automated backup schedule."""
    from app.models import Setting
    
    if request.method == 'POST':
        Setting.set('backup_enabled', 'true' if 'backup_enabled' in request.form else 'false')
        Setting.set('backup_frequency', request.form.get('backup_frequency', 'daily'))
        Setting.set('backup_retention', request.form.get('backup_retention', '7'))
        flash('Backup schedule saved')
        return redirect(url_for('admin.backup_schedule'))
    
    backup_enabled = Setting.get('backup_enabled', 'false') == 'true'
    backup_frequency = Setting.get('backup_frequency', 'daily')
    backup_retention = Setting.get('backup_retention', '7')
    
    return render_admin('Backup Schedule', '''
<form method="POST">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<h3>Automated Backups</h3>
<label><input name="backup_enabled" type="checkbox" {% if backup_enabled %}checked{% endif %}> Enable Automated Backups</label>

<label>Frequency
  <select name="backup_frequency">
    <option value="hourly" {% if backup_frequency == 'hourly' %}selected{% endif %}>Hourly</option>
    <option value="daily" {% if backup_frequency == 'daily' %}selected{% endif %}>Daily</option>
    <option value="weekly" {% if backup_frequency == 'weekly' %}selected{% endif %}>Weekly</option>
  </select>
</label>

<label>Retention (days) <input name="backup_retention" type="number" value="{{ backup_retention }}"></label>

<button type="submit" style="margin-top:1rem;padding:8px 20px;background:#2563eb;color:#fff;border:none;border-radius:4px;cursor:pointer;">Save Backup Schedule</button>
</form>
''', backup_enabled=backup_enabled, backup_frequency=backup_frequency, backup_retention=backup_retention)

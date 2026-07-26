"""Admin routes for database backup and restore."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash, send_file
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required
import os

backup_bp = Blueprint('backup', __name__)


@backup_bp.route('/backup')
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


@backup_bp.route('/backups')
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


@backup_bp.route('/backups/<path:path>/download')
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


@backup_bp.route('/backups/<path:path>/delete', methods=['POST'])
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


@backup_bp.route('/backups/restore/<path:path>', methods=['POST'])
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

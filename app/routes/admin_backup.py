from flask import Blueprint, request, redirect, url_for, flash
import os
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required, render_admin

backup_bp = Blueprint('backup', __name__)


@backup_bp.route('/')
@admin_required
def backup_database():
    """Create a database backup."""
    from app.services.backup import create_backup
    try:
        backup_path = create_backup()
        flash(f'Backup created: {os.path.basename(backup_path)}')
        return redirect(url_for('admin.backup.list_backups'))
    except Exception as e:
        flash(f'Backup failed: {e}', 'error')
        return redirect(url_for('admin.dashboard.dashboard'))


@backup_bp.route('/backups')
@admin_required
def list_backups():
    """List available backups."""
    from app.services.backup import list_backups as _list_backups
    backups = _list_backups()
    return render_admin('Backups', 'admin/backup/list.html', backups=backups)


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
    return redirect(url_for('admin.backup.list_backups'))


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
            return redirect(url_for('admin.backup.list_backups'))
    flash('Backup not found', 'error')
    return redirect(url_for('admin.backup.list_backups'))


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
                return redirect(url_for('admin.backup.list_backups'))
            except Exception as e:
                flash(f'Restore failed: {e}', 'error')
                return redirect(url_for('admin.backup.list_backups'))
    flash('Backup not found', 'error')
    return redirect(url_for('admin.backup.list_backups'))


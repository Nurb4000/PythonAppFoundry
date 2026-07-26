"""Database backup and restore utilities."""
import os
import shutil
import sqlite3
import logging
from datetime import datetime, timezone
from flask import current_app, send_file, Response
from io import BytesIO

logger = logging.getLogger(__name__)


def create_backup(backup_dir=None):
    """Create a backup of the current database.
    
    Returns path to the backup file.
    """
    if backup_dir is None:
        backup_dir = os.path.join(current_app.instance_path, 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    # Get database path
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if db_uri.startswith('sqlite:///'):
        db_path = db_uri[10:]  # Remove 'sqlite:///'
    elif db_uri.startswith('sqlite://'):
        db_path = db_uri[9:]  # Remove 'sqlite://'
    else:
        raise ValueError(f'Unsupported database URI: {db_uri}')
    
    if not os.path.isabs(db_path):
        db_path = os.path.join(current_app.root_path, '..', db_path)
        db_path = os.path.normpath(db_path)
    
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'database_{timestamp}.db')
    
    # Copy the database file
    shutil.copy2(db_path, backup_path)
    os.chmod(backup_path, 0o600)
    
    logger.info(f'Created database backup: {backup_path}')
    return backup_path


def list_backups(backup_dir=None):
    """List available backups with metadata."""
    if backup_dir is None:
        backup_dir = os.path.join(current_app.instance_path, 'backups')
    
    if not os.path.exists(backup_dir):
        return []
    
    backups = []
    for filename in sorted(os.listdir(backup_dir)):
        if filename.startswith('database_') and filename.endswith('.db'):
            filepath = os.path.join(backup_dir, filename)
            stat = os.stat(filepath)
            backups.append({
                'filename': filename,
                'path': filepath,
                'size': stat.st_size,
                'created_at': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            })
    
    return backups


def restore_backup(backup_path):
    """Restore database from a backup file.
    
    WARNING: This will replace the current database!
    """
    if not os.path.exists(backup_path):
        raise FileNotFoundError(f'Backup file not found: {backup_path}')
    
    # Get database path
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if db_uri.startswith('sqlite:///'):
        db_path = db_uri[10:]
    elif db_uri.startswith('sqlite://'):
        db_path = db_uri[9:]
    else:
        raise ValueError(f'Unsupported database URI: {db_uri}')
    
    if not os.path.isabs(db_path):
        db_path = os.path.join(current_app.root_path, '..', db_path)
        db_path = os.path.normpath(db_path)
    
    # Backup current database before restoring
    if os.path.exists(db_path):
        emergency_backup = db_path + '.emergency_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        shutil.copy2(db_path, emergency_backup)
        logger.info(f'Created emergency backup: {emergency_backup}')
    
    # Restore from backup
    shutil.copy2(backup_path, db_path)
    logger.info(f'Restored database from: {backup_path}')


def download_backup(backup_path):
    """Send a backup file for download."""
    return send_file(
        backup_path,
        as_attachment=True,
        download_name=os.path.basename(backup_path),
        mimetype='application/octet-stream'
    )


def delete_backup(backup_path):
    """Delete a backup file."""
    if os.path.exists(backup_path):
        os.remove(backup_path)
        logger.info(f'Deleted backup: {backup_path}')

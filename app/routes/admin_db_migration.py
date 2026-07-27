from flask import Blueprint, request, redirect, url_for, flash, session
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required, render_admin
from app.services.audit import log_audit
from app.services.backup import create_backup
import os
import time

db_migration_bp = Blueprint('db_migration', __name__)


@db_migration_bp.route('/')
@admin_required
def migration_page():
    """Show database migration page."""
    from app import db
    current_db_url = db.engine.url.__str__()
    
    # Get current database info
    db_info = {
        'url': current_db_url,
        'type': 'SQLite' if current_db_url.startswith('sqlite') else 'PostgreSQL',
    }
    
    # Check if migration is pending
    pending_target = session.get('migration_target')
    
    return render_admin('Database Migration', 'admin/db_migration/index.html', 
                       db_info=db_info, pending_target=pending_target)


@db_migration_bp.route('/start', methods=['POST'])
@admin_required
@csrf_protect
def start_migration():
    """Start the database migration process."""
    new_db_url = request.form.get('new_db_url', '').strip()
    
    if not new_db_url:
        flash('Please provide a database URL.', 'error')
        return redirect(url_for('admin.db_migration.migration_page'))
    
    # Validate the database URL format
    if not _validate_db_url(new_db_url):
        flash('Invalid database URL format. Expected: postgresql://user:pass@host:port/dbname', 'error')
        return redirect(url_for('admin.db_migration.migration_page'))
    
    # Check if source and target are the same
    from app import db
    current_db_url = db.engine.url.__str__()
    if current_db_url == new_db_url:
        flash('Source and target databases cannot be the same.', 'error')
        return redirect(url_for('admin.db_migration.migration_page'))
    
    # Store migration params in session for the execute step
    session['migration_target'] = new_db_url
    session['migration_started_at'] = time.time()
    
    flash('Migration parameters saved. Click "Execute Migration" to begin.', 'info')
    return redirect(url_for('admin.db_migration.migration_page'))


@db_migration_bp.route('/execute', methods=['POST'])
@admin_required
@csrf_protect
def execute_migration():
    """Execute the database migration."""
    from app import db
    
    # Get migration params from session
    target_db_url = session.get('migration_target')
    
    if not target_db_url:
        flash('No migration target configured. Please start a new migration first.', 'error')
        return redirect(url_for('admin.db_migration.migration_page'))
    
    # Check if database driver is available
    if target_db_url.startswith('postgresql://'):
        try:
            import psycopg2
        except ImportError:
            flash(
                'PostgreSQL driver not found. Install it with: pip install psycopg2-binary',
                'error'
            )
            return redirect(url_for('admin.db_migration.migration_page'))
    
    # Create backup before migration
    try:
        backup_path = create_backup()
        log_audit('backup_before_migration', 'database', details=f'Backup created: {os.path.basename(backup_path)}')
        flash(f'Pre-migration backup created: {os.path.basename(backup_path)}', 'info')
    except Exception as e:
        flash(f'Failed to create backup: {e}', 'error')
        return redirect(url_for('admin.db_migration.migration_page'))
    
    # Execute migration
    try:
        from app.services.db_migration import export_database, import_to_new_database, verify_migration
        
        # Step 1: Export current database
        flash('Step 1/4: Exporting data from current database...', 'info')
        exported_data = export_database(db.session)
        
        # Step 2: Import to new database
        flash('Step 2/4: Importing data into new database...', 'info')
        import_results = import_to_new_database(exported_data, target_db_url)
        
        if import_results['tables_failed'] > 0:
            flash(f'Warning: {import_results["tables_failed"]} table(s) failed to import. Check logs for details.', 'warning')
        
        # Step 3: Verify migration
        from sqlalchemy import create_engine
        new_engine = create_engine(target_db_url)
        flash('Step 3/4: Verifying migration...', 'info')
        verification = verify_migration(exported_data, new_engine)
        
        # Step 4: Report results
        if verification['tables_mismatched'] == 0:
            log_audit('database_migrated', 'database', details=f'Migrated to: {target_db_url}')
            flash(f'Success! Migrated {import_results["total_rows"]} rows across {import_results["tables_imported"]} tables. Verification passed.', 'success')
        else:
            error_details = []
            for detail in verification['details']:
                if detail.get('status') == 'mismatch':
                    error_details.append(f'{detail["table"]}: expected {detail["original_count"]}, got {detail["new_count"]}')
            
            flash(f'Migration completed with issues. {verification["tables_mismatched"]} table(s) have row count mismatches: {"; ".join(error_details)}', 'warning')
        
        # Clean up session data
        session.pop('migration_target', None)
        session.pop('migration_started_at', None)
        
    except Exception as e:
        flash(f'Migration failed: {e}', 'error')
        import traceback
        traceback.print_exc()
    
    return redirect(url_for('admin.db_migration.migration_page'))


@db_migration_bp.route('/cancel', methods=['POST'])
@admin_required
@csrf_protect
def cancel_migration():
    """Cancel pending migration."""
    session.pop('migration_target', None)
    session.pop('migration_started_at', None)
    flash('Migration cancelled.', 'info')
    return redirect(url_for('admin.db_migration.migration_page'))


def _validate_db_url(url):
    """Validate database URL format."""
    if url.startswith('postgresql://'):
        # Basic validation for PostgreSQL URLs
        return True
    elif url.startswith('sqlite:///'):
        # SQLite file paths
        return True
    else:
        return False

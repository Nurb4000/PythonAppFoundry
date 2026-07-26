"""Admin routes for database migrations."""
from flask import Blueprint, request, redirect, url_for, flash

migration_bp = Blueprint('migration', __name__)


@migration_bp.route('/migrate')
@admin_required
def migrate():
    """Run database migrations and schema updates."""
    from app import db
    from sqlalchemy import inspect as sa_inspect, text
    
    bind = db.session.get_bind()
    inspector = sa_inspect(bind)
    
    # Check for missing columns and add them
    migrations_run = []
    
    # Routes table
    routes_cols = {c['name'] for c in inspector.get_columns('routes')}
    if 'allowed_groups' not in routes_cols:
        db.session.execute(text('ALTER TABLE routes ADD COLUMN allowed_groups TEXT DEFAULT \'\''))
        db.session.commit()
        migrations_run.append('Added allowed_groups to routes')
    
    # Modules table
    mod_cols = {c['name'] for c in inspector.get_columns('modules')}
    if 'is_system' not in mod_cols:
        db.session.execute(text("ALTER TABLE modules ADD COLUMN is_system BOOLEAN DEFAULT 0"))
        db.session.commit()
        migrations_run.append('Added is_system to modules')
    
    # Query reports table
    if 'query_reports' in inspector.get_table_names():
        qr_cols = {c['name'] for c in inspector.get_columns('query_reports')}
        if 'module_id' not in qr_cols:
            db.session.execute(text('ALTER TABLE query_reports ADD COLUMN module_id INTEGER REFERENCES modules(id)'))
            db.session.commit()
            migrations_run.append('Added module_id to query_reports')
    
    if migrations_run:
        flash(f' ran {len(migrations_run)} migration(s): ' + ', '.join(migrations_run))
    else:
        flash('No migrations needed. Database is up to date.')
    
    return redirect(url_for('admin.dashboard'))

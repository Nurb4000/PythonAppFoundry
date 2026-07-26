"""Admin routes for database optimization."""
from flask import Blueprint, request, redirect, url_for, flash

optimize_bp = Blueprint('optimize', __name__)


@optimize_bp.route('/optimize')
@admin_required
def optimize_database():
    """Optimize database performance."""
    from app import db
    
    # Run VACUUM for SQLite
    try:
        db.session.execute(db.text('VACUUM'))
        db.session.commit()
        flash('Database optimized (VACUUM completed)')
    except Exception as e:
        flash(f'Optimization failed: {e}', 'error')
    
    # Reindex tables
    try:
        from sqlalchemy import inspect as sa_inspect
        bind = db.session.get_bind()
        inspector = sa_inspect(bind)
        for table_name in inspector.get_table_names():
            if not table_name.startswith('sqlite_') and table_name != 'alembic_version':
                db.session.execute(db.text(f'REINDEX TABLE {table_name}'))
        db.session.commit()
        flash('Database reindexed')
    except Exception as e:
        flash(f'Reindex failed: {e}', 'error')
    
    return redirect(url_for('admin.dashboard'))

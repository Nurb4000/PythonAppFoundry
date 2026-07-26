"""Admin routes for database cleanup."""
from flask import Blueprint, request, redirect, url_for, flash

cleanup_bp = Blueprint('cleanup', __name__)


@cleanup_bp.route('/cleanup')
@admin_required
def cleanup_database():
    """Clean up orphaned data and optimize database."""
    from app.models import DynamicTableRegistry, Module
    
    # Find orphaned dynamic table registrations
    orphaned = db.session.query(DynamicTableRegistry).filter(
        ~DynamicTableRegistry.module_id.in_(db.session.query(Module.id))
    ).all()
    
    removed = 0
    for reg in orphaned:
        db.session.delete(reg)
        removed += 1
    
    if removed > 0:
        db.session.commit()
        flash(f'Removed {removed} orphaned dynamic table registration(s)')
    else:
        flash('No orphaned registrations found.')
    
    # Clean up empty modules (optional)
    empty_modules = db.session.query(Module).filter(
        Module.routes.count() == 0,
        Module.scripts.count() == 0,
        Module.forms.count() == 0,
    ).all()
    
    if empty_modules:
        flash(f'Found {len(empty_modules)} empty module(s). Consider removing them.')
    
    return redirect(url_for('admin.dashboard'))

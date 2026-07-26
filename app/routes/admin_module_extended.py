"""Admin routes for extended module management."""
from flask import Blueprint, request, redirect, url_for, render_template_string

module_extended_bp = Blueprint('module_extended', __name__)


@module_extended_bp.route('/modules/<int:id>/enable')
@admin_required
def enable_module(id):
    """Enable a module."""
    from app.models import Module
    
    module = db.session.get(Module, id)
    if not module:
        flash('Module not found', 'error')
        return redirect(url_for('admin.list_modules'))
    
    module.enabled = True
    db.session.commit()
    flash(f'Module "{module.name}" enabled')
    return redirect(url_for('admin.list_modules'))


@module_extended_bp.route('/modules/<int:id>/disable')
@admin_required
def disable_module(id):
    """Disable a module."""
    from app.models import Module
    
    module = db.session.get(Module, id)
    if not module:
        flash('Module not found', 'error')
        return redirect(url_for('admin.list_modules'))
    
    module.enabled = False
    db.session.commit()
    flash(f'Module "{module.name}" disabled')
    return redirect(url_for('admin.list_modules'))


@module_extended_bp.route('/modules/bulk-enable', methods=['POST'])
@admin_required
@csrf_protect
def bulk_enable_modules():
    """Enable multiple modules at once."""
    from app.models import Module
    
    module_ids = request.form.getlist('module_ids')
    enabled = 0
    for mid in module_ids:
        module = db.session.get(Module, int(mid))
        if module:
            module.enabled = True
            enabled += 1
    
    db.session.commit()
    flash(f'Enabled {enabled} module(s)')
    return redirect(url_for('admin.list_modules'))


@module_extended_bp.route('/modules/bulk-disable', methods=['POST'])
@admin_required
@csrf_protect
def bulk_disable_modules():
    """Disable multiple modules at once."""
    from app.models import Module
    
    module_ids = request.form.getlist('module_ids')
    disabled = 0
    for mid in module_ids:
        module = db.session.get(Module, int(mid))
        if module and not module.is_system:
            module.enabled = False
            disabled += 1
    
    db.session.commit()
    flash(f'Disabled {disabled} module(s)')
    return redirect(url_for('admin.list_modules'))

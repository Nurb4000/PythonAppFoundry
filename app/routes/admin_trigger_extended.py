"""Admin routes for extended trigger management."""
from flask import Blueprint, request, redirect, url_for, render_template_string

trigger_extended_bp = Blueprint('trigger_extended', __name__)


@trigger_extended_bp.route('/triggers/<int:id>/enable')
@admin_required
def enable_trigger(id):
    """Enable a trigger."""
    from app.models import Trigger
    
    trigger = db.session.get(Trigger, id)
    if not trigger:
        flash('Trigger not found', 'error')
        return redirect(url_for('admin.list_triggers'))
    
    trigger.enabled = True
    db.session.commit()
    flash(f'Trigger "{trigger.name}" enabled')
    return redirect(url_for('admin.list_triggers'))


@trigger_extended_bp.route('/triggers/<int:id>/disable')
@admin_required
def disable_trigger(id):
    """Disable a trigger."""
    from app.models import Trigger
    
    trigger = db.session.get(Trigger, id)
    if not trigger:
        flash('Trigger not found', 'error')
        return redirect(url_for('admin.list_triggers'))
    
    trigger.enabled = False
    db.session.commit()
    flash(f'Trigger "{trigger.name}" disabled')
    return redirect(url_for('admin.list_triggers'))


@trigger_extended_bp.route('/triggers/bulk-enable', methods=['POST'])
@admin_required
@csrf_protect
def bulk_enable_triggers():
    """Enable multiple triggers at once."""
    from app.models import Trigger
    
    trigger_ids = request.form.getlist('trigger_ids')
    enabled = 0
    for tid in trigger_ids:
        trigger = db.session.get(Trigger, int(tid))
        if trigger:
            trigger.enabled = True
            enabled += 1
    
    db.session.commit()
    flash(f'Enabled {enabled} trigger(s)')
    return redirect(url_for('admin.list_triggers'))


@trigger_extended_bp.route('/triggers/bulk-disable', methods=['POST'])
@admin_required
@csrf_protect
def bulk_disable_triggers():
    """Disable multiple triggers at once."""
    from app.models import Trigger
    
    trigger_ids = request.form.getlist('trigger_ids')
    disabled = 0
    for tid in trigger_ids:
        trigger = db.session.get(Trigger, int(tid))
        if trigger:
            trigger.enabled = False
            disabled += 1
    
    db.session.commit()
    flash(f'Disabled {disabled} trigger(s)')
    return redirect(url_for('admin.list_triggers'))

"""Admin routes for extended task management."""
from flask import Blueprint, request, redirect, url_for, render_template_string

task_extended_bp = Blueprint('task_extended', __name__)


@task_extended_bp.route('/tasks/<int:id>/enable')
@admin_required
def enable_task(id):
    """Enable a scheduled task."""
    from app.models import ScheduledTask
    
    task = db.session.get(ScheduledTask, id)
    if not task:
        flash('Task not found', 'error')
        return redirect(url_for('admin.list_tasks'))
    
    task.enabled = True
    db.session.commit()
    flash(f'Task "{task.name}" enabled')
    return redirect(url_for('admin.list_tasks'))


@task_extended_bp.route('/tasks/<int:id>/disable')
@admin_required
def disable_task(id):
    """Disable a scheduled task."""
    from app.models import ScheduledTask
    
    task = db.session.get(ScheduledTask, id)
    if not task:
        flash('Task not found', 'error')
        return redirect(url_for('admin.list_tasks'))
    
    task.enabled = False
    db.session.commit()
    flash(f'Task "{task.name}" disabled')
    return redirect(url_for('admin.list_tasks'))


@task_extended_bp.route('/tasks/bulk-enable', methods=['POST'])
@admin_required
@csrf_protect
def bulk_enable_tasks():
    """Enable multiple tasks at once."""
    from app.models import ScheduledTask
    
    task_ids = request.form.getlist('task_ids')
    enabled = 0
    for tid in task_ids:
        task = db.session.get(ScheduledTask, int(tid))
        if task:
            task.enabled = True
            enabled += 1
    
    db.session.commit()
    flash(f'Enabled {enabled} task(s)')
    return redirect(url_for('admin.list_tasks'))


@task_extended_bp.route('/tasks/bulk-disable', methods=['POST'])
@admin_required
@csrf_protect
def bulk_disable_tasks():
    """Disable multiple tasks at once."""
    from app.models import ScheduledTask
    
    task_ids = request.form.getlist('task_ids')
    disabled = 0
    for tid in task_ids:
        task = db.session.get(ScheduledTask, int(tid))
        if task:
            task.enabled = False
            disabled += 1
    
    db.session.commit()
    flash(f'Disabled {disabled} task(s)')
    return redirect(url_for('admin.list_tasks'))

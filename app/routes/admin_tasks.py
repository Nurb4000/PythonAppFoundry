from flask import Blueprint, request, redirect, url_for, flash
from app.services.csrf import csrf_protect
from app.services.validation import validate_cron_expression
from app.services.admin_utils import admin_required, list_view, render_admin
from app.services.scheduler import refresh_tasks
from app import db
from app.models import Module, Script, ScheduledTask

tasks_bp = Blueprint('tasks', __name__)

def _validate_cron(expr):
    valid, err = validate_cron_expression(expr)
    if not valid:
        return err
    try:
        from apscheduler.triggers.cron import CronTrigger
        parts = expr.strip().split()
        CronTrigger(minute=parts[0], hour=parts[1], day=parts[2], month=parts[3], day_of_week=parts[4])
    except (ValueError, ImportError) as e:
        return str(e)
    return None

@tasks_bp.route('/tasks')
@admin_required
def list_tasks():
    return list_view(ScheduledTask, 'scheduled tasks',
        ['id', 'name', 'cron_expression', 'enabled', 'last_run', 'next_run'],
        'admin.tasks.edit_task', 'admin.tasks.new_task', has_module=True)

@tasks_bp.route('/tasks/new', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def new_task():
    modules = db.session.query(Module).all()
    scripts = db.session.query(Script).all()
    if request.method == 'POST':
        cron = request.form['cron_expression']
        err = _validate_cron(cron)
        if err:
            flash(f'Invalid cron expression: {err}', 'error')
            return redirect(url_for('admin.tasks.list_tasks'))
        t = ScheduledTask(
            module_id=int(request.form['module_id']),
            name=request.form['name'],
            script_id=int(request.form['script_id']),
            cron_expression=cron,
        )
        db.session.add(t)
        db.session.commit()
        refresh_tasks()
        return redirect(url_for('admin.tasks.list_tasks'))
    return render_admin('New Scheduled Task', 'admin/tasks/new.html', modules=modules, scripts=scripts)

@tasks_bp.route('/tasks/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def edit_task(id):
    t = ScheduledTask.query.get_or_404(id)
    modules = db.session.query(Module).all()
    scripts = db.session.query(Script).all()
    if request.method == 'POST':
        cron = request.form['cron_expression']
        err = _validate_cron(cron)
        if err:
            flash(f'Invalid cron expression: {err}', 'error')
            return redirect(url_for('admin.tasks.list_tasks'))
        t.module_id = int(request.form['module_id'])
        t.name = request.form['name']
        t.script_id = int(request.form['script_id'])
        t.cron_expression = cron
        t.enabled = 'enabled' in request.form
        db.session.commit()
        refresh_tasks()
        return redirect(url_for('admin.tasks.list_tasks'))
    return render_admin('Edit Scheduled Task', 'admin/tasks/edit.html', t=t, modules=modules, scripts=scripts)

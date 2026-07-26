"""Admin routes for scheduled task management."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required, list_view, render_admin, _validate_cron, refresh_tasks
from app import db
from app.models import ScheduledTask, Module, Script

tasks_bp = Blueprint('tasks', __name__)


@tasks_bp.route('/tasks')
@admin_required
def list_tasks():
    return list_view(ScheduledTask, 'scheduled tasks',
        ['id', 'name', 'cron_expression', 'enabled', 'last_run', 'next_run'],
        'admin.edit_task', 'admin.new_task', has_module=True)


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
            return redirect(url_for('admin.list_tasks'))
        t = ScheduledTask(
            module_id=int(request.form['module_id']),
            name=request.form['name'],
            script_id=int(request.form['script_id']),
            cron_expression=cron,
        )
        db.session.add(t)
        db.session.commit()
        refresh_tasks()
        return redirect(url_for('admin.list_tasks'))
    return render_admin('New Scheduled Task', '''
<form method="POST">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>Name <input name="name" required></label>
<label>Module <select name="module_id">{% for m in modules %}<option value="{{ m.id }}">{{ m.name }}</option>{% endfor %}</select></label>
<label>Script <select name="script_id">{% for s in scripts %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}</select></label>
<label>Cron Expression <input name="cron_expression" placeholder="*/5 * * * *" required></label>
<button>Save</button>
</form>''', modules=modules, scripts=scripts)


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
            return redirect(url_for('admin.list_tasks'))
        t.module_id = int(request.form['module_id'])
        t.name = request.form['name']
        t.script_id = int(request.form['script_id'])
        t.cron_expression = cron
        t.enabled = 'enabled' in request.form
        db.session.commit()
        refresh_tasks()
        return redirect(url_for('admin.list_tasks'))
    return render_admin('Edit Scheduled Task', '''
<form method="POST">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>Name <input name="name" value="{{ t.name }}" required></label>
<label>Module <select name="module_id">{% for m in modules %}<option value="{{ m.id }}" {% if m.id == t.module_id %}selected{% endif %}>{{ m.name }}</option>{% endfor %}</select></label>
<label>Script <select name="script_id">{% for s in scripts %}<option value="{{ s.id }}" {% if s.id == t.script_id %}selected{% endif %}>{{ s.name }}</option>{% endfor %}</select></label>
<label>Cron Expression <input name="cron_expression" value="{{ t.cron_expression }}" required></label>
<label><input name="enabled" type="checkbox" {% if t.enabled %}checked{% endif %}> Enabled</label>
<button>Save</button>
</form>''', t=t, modules=modules, scripts=scripts)

from flask import Blueprint, request, redirect, url_for, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required, list_view, render_admin
from app import db
from app.models import Module, Script, Trigger

triggers_bp = Blueprint('triggers', __name__)

@triggers_bp.route('/')
@admin_required
def list_triggers():
    return list_view(Trigger, 'triggers',
        ['id', 'name', 'event_type', 'target_table', 'enabled'],
        'admin.triggers.edit_trigger', 'admin.triggers.new_trigger', has_module=True)

@triggers_bp.route('/new', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def new_trigger():
    modules = db.session.query(Module).all()
    scripts = db.session.query(Script).all()
    if request.method == 'POST':
        tg = Trigger(
            module_id=int(request.form['module_id']),
            name=request.form['name'],
            event_type=request.form['event_type'],
            target_table=request.form['target_table'],
            script_id=int(request.form['script_id']),
        )
        db.session.add(tg)
        db.session.commit()
        return redirect(url_for('admin.triggers.list_triggers'))
    return render_admin('New Trigger', 'admin/triggers/new.html', modules=modules, scripts=scripts)

@triggers_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def edit_trigger(id):
    tg = Trigger.query.get_or_404(id)
    modules = db.session.query(Module).all()
    scripts = db.session.query(Script).all()
    if request.method == 'POST':
        tg.module_id = int(request.form['module_id'])
        tg.name = request.form['name']
        tg.event_type = request.form['event_type']
        tg.target_table = request.form['target_table']
        tg.script_id = int(request.form['script_id'])
        tg.enabled = 'enabled' in request.form
        tg.auth_token = request.form.get('auth_token', '').strip()
        db.session.commit()
        return redirect(url_for('admin.triggers.list_triggers'))
    return render_admin('Edit Trigger', 'admin/triggers/edit.html', tg=tg, modules=modules, scripts=scripts)

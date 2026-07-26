"""Admin routes for trigger management."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required, list_view
from app import db
from app.models import Trigger, Module, Script

triggers_bp = Blueprint('triggers', __name__)


@triggers_bp.route('/triggers')
@admin_required
def list_triggers():
    return list_view(Trigger, 'triggers',
        ['id', 'name', 'event_type', 'target_table', 'enabled'],
        'admin.edit_trigger', 'admin.new_trigger', has_module=True)


@triggers_bp.route('/triggers/new', methods=['GET', 'POST'])
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
        return redirect(url_for('admin.list_triggers'))
    return render_admin('New Trigger', '''
<form method="POST">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>Name <input name="name" required></label>
<label>Module <select name="module_id">{% for m in modules %}<option value="{{ m.id }}">{{ m.name }}</option>{% endfor %}</select></label>
<label>Event Type <select name="event_type"><option>on_insert</option><option>on_update</option><option>on_delete</option><option>after_route</option><option>webhook</option></select></label>
<label>Target Table <input name="target_table" placeholder="table_name or webhook-slug"></label>
<label>Script <select name="script_id">{% for s in scripts %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}</select></label>
<label>Auth Token (optional, for webhook triggers) <input name="auth_token" placeholder="Leave blank for public"></label>
<button>Save</button>
</form>''', modules=modules, scripts=scripts)


@triggers_bp.route('/triggers/edit/<int:id>', methods=['GET', 'POST'])
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
        return redirect(url_for('admin.list_triggers'))
    return render_admin('Edit Trigger', '''
<form method="POST">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>Name <input name="name" value="{{ tg.name }}" required></label>
<label>Module <select name="module_id">{% for m in modules %}<option value="{{ m.id }}" {% if m.id == tg.module_id %}selected{% endif %}>{{ m.name }}</option>{% endfor %}</select></label>
<label>Event Type <select name="event_type"><option {% if tg.event_type=='on_insert' %}selected{% endif %}>on_insert</option><option {% if tg.event_type=='on_update' %}selected{% endif %}>on_update</option><option {% if tg.event_type=='on_delete' %}selected{% endif %}>on_delete</option><option {% if tg.event_type=='after_route' %}selected{% endif %}>after_route</option><option {% if tg.event_type=='webhook' %}selected{% endif %}>webhook</option></select></label>
<label>Target Table <input name="target_table" value="{{ tg.target_table }}"></label>
<label>Script <select name="script_id">{% for s in scripts %}<option value="{{ s.id }}" {% if s.id == tg.script_id %}selected{% endif %}>{{ s.name }}</option>{% endfor %}</select></label>
<label><input name="enabled" type="checkbox" {% if tg.enabled %}checked{% endif %}> Enabled</label>
<label>Auth Token (optional) <input name="auth_token" value="{{ tg.auth_token }}" placeholder="Leave blank for public"></label>
<button>Save</button>
</form>''', tg=tg, modules=modules, scripts=scripts)

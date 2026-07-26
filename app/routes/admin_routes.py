"""Admin routes for route management."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import developer_or_admin_required, list_view, validate_route_slug, render_admin
from app import db
from app.models import Route, Module, Script, Form, Group

routes_bp = Blueprint('routes', __name__)


@routes_bp.route('/')
@developer_or_admin_required
def list_routes():
    return list_view(Route, 'routes', ['id', 'slug', 'methods', 'auth_required', 'title'], 'admin.edit_route', 'admin.new_route', show_view=True, has_module=True)


@routes_bp.route('/new', methods=['GET', 'POST'])
@developer_or_admin_required
@csrf_protect
def new_route():
    modules = db.session.query(Module).all()
    scripts = db.session.query(Script).all()
    forms = db.session.query(Form).all()
    groups = db.session.query(Group).order_by(Group.name).all()
    if request.method == 'POST':
        raw_slug = request.form['slug'].strip()
        valid, result = validate_route_slug(raw_slug)
        if not valid:
            flash(f'Route slug validation failed: {result}', 'error')
            return redirect(url_for('admin.list_routes'))
        slug = result
        existing = db.session.query(Route).filter_by(slug=slug).first()
        if existing:
            flash(f'Route slug "{slug}" already in use by module "{existing.module.name}"')
            return redirect(url_for('admin.list_routes'))
        allowed = ','.join(request.form.getlist('allowed_groups'))
        r = Route(module_id=int(request.form['module_id']), slug=slug, methods=request.form.get('methods', 'GET'), script_id=int(request.form['script_id']) if request.form.get('script_id') else None, form_id=int(request.form['form_id']) if request.form.get('form_id') else None, auth_required='auth_required' in request.form, allowed_groups=allowed, title=request.form.get('title', ''))
        db.session.add(r)
        db.session.commit()
        return redirect(url_for('admin.list_routes'))
    return render_admin('New Route', NEW_ROUTE_TEMPLATE, modules=modules, scripts=scripts, forms=forms, groups=groups)


NEW_ROUTE_TEMPLATE = '''<form method="POST">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>Slug <input name="slug" required></label>
<label>Methods <input name="methods" value="GET"></label>
<label>Module <select name="module_id">{% for m in modules %}<option value="{{ m.id }}">{{ m.name }}</option>{% endfor %}</select></label>
<label>Script <select name="script_id"><option value="">-- none --</option>{% for s in scripts %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}</select></label>
<label>Form <select name="form_id"><option value="">-- none --</option>{% for f in forms %}<option value="{{ f.id }}">{{ f.name }}</option>{% endfor %}</select></label>
<label><input name="auth_required" type="checkbox"> Auth Required</label>
<label>Title <input name="title"></label>
<details style="margin:0.5rem 0;"><summary>Group Access</summary>
<div style="margin:0.5rem 0 0 1rem;">{% for g in groups %}<label style="display:block;font-weight:normal;font-size:0.9em;"><input name="allowed_groups" type="checkbox" value="{{ g.id }}"> {{ g.name }}</label>{% endfor %}{% if not groups %}<span style="color:#888;font-size:0.85em;">No groups defined</span>{% endif %}</div>
</details>
<button>Save</button>
</form>'''


@routes_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@developer_or_admin_required
@csrf_protect
def edit_route(id):
    r = Route.query.get_or_404(id)
    modules = db.session.query(Module).all()
    scripts = db.session.query(Script).all()
    forms = db.session.query(Form).all()
    groups = db.session.query(Group).order_by(Group.name).all()
    if request.method == 'POST':
        r.module_id = int(request.form['module_id'])
        raw_slug = request.form['slug'].strip()
        valid, result = validate_route_slug(raw_slug)
        if not valid:
            flash(f'Route slug validation failed: {result}', 'error')
            return redirect(url_for('admin.list_routes'))
        slug = result
        existing = db.session.query(Route).filter(Route.slug == slug, Route.id != id).first()
        if existing:
            flash(f'Route slug "{slug}" already in use by module "{existing.module.name}"')
            return redirect(url_for('admin.list_routes'))
        r.slug = slug
        r.methods = request.form.get('methods', 'GET')
        r.script_id = int(request.form['script_id']) if request.form.get('script_id') else None
        r.form_id = int(request.form['form_id']) if request.form.get('form_id') else None
        r.auth_required = 'auth_required' in request.form
        r.allowed_groups = ','.join(request.form.getlist('allowed_groups'))
        r.title = request.form.get('title', '')
        db.session.commit()
        return redirect(url_for('admin.list_routes'))
    allowed_ids = set(r.allowed_groups.split(',') if r.allowed_groups else [])
    return render_admin('Edit Route', EDIT_ROUTE_TEMPLATE, r=r, modules=modules, scripts=scripts, forms=forms, groups=groups, allowed_ids=allowed_ids)


EDIT_ROUTE_TEMPLATE = '''<form method="POST">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>Slug <input name="slug" value="{{ r.slug }}" required></label>
<label>Methods <input name="methods" value="{{ r.methods }}"></label>
<label>Module <select name="module_id">{% for m in modules %}<option value="{{ m.id }}" {% if m.id == r.module_id %}selected{% endif %}>{{ m.name }}</option>{% endfor %}</select></label>
<label>Script <select name="script_id"><option value="">-- none --</option>{% for s in scripts %}<option value="{{ s.id }}" {% if s.id == r.script_id %}selected{% endif %}>{{ s.name }}</option>{% endfor %}</select></label>
<label>Form <select name="form_id"><option value="">-- none --</option>{% for f in forms %}<option value="{{ f.id }}" {% if f.id == r.form_id %}selected{% endif %}>{{ f.name }}</option>{% endfor %}</select></label>
<label><input name="auth_required" type="checkbox" {% if r.auth_required %}checked{% endif %}> Auth Required</label>
<label>Title <input name="title" value="{{ r.title }}"></label>
<details style="margin:0.5rem 0;"><summary>Group Access</summary>
<div style="margin:0.5rem 0 0 1rem;">{% for g in groups %}<label style="display:block;font-weight:normal;font-size:0.9em;"><input name="allowed_groups" type="checkbox" value="{{ g.id }}" {% if g.id|string in allowed_ids %}checked{% endif %}> {{ g.name }}</label>{% endfor %}{% if not groups %}<span style="color:#888;font-size:0.85em;">No groups defined</span>{% endif %}</div>
</details>
<button>Save</button>
</form>'''

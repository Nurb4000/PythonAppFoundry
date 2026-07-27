"""Admin routes for route management."""
from flask import Blueprint, request, redirect, url_for, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import developer_or_admin_required, list_view, render_admin
from app.services.validation import validate_route_slug
from app import db
from app.models import Route, Module, Script, Form, Group
from app.services.audit import log_audit

routes_bp = Blueprint('routes', __name__)


@routes_bp.route('/')
@developer_or_admin_required
def list_routes():
    return list_view(Route, 'routes', ['id', 'slug', 'methods', 'auth_required', 'title'], 'admin.routes.edit_route', 'admin.routes.new_route', show_view=True, has_module=True)


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
            return redirect(url_for('admin.routes.list_routes'))
        slug = result
        existing = db.session.query(Route).filter_by(slug=slug).first()
        if existing:
            flash(f'Route slug "{slug}" already in use by module "{existing.module.name}"')
            return redirect(url_for('admin.routes.list_routes'))
        allowed = ','.join(request.form.getlist('allowed_groups'))
        r = Route(module_id=int(request.form['module_id']), slug=slug, methods=request.form.get('methods', 'GET'), script_id=int(request.form['script_id']) if request.form.get('script_id') else None, form_id=int(request.form['form_id']) if request.form.get('form_id') else None, auth_required='auth_required' in request.form, allowed_groups=allowed, title=request.form.get('title', ''))
        db.session.add(r)
        db.session.commit()
        log_audit('create', 'route', r.id, r.slug)
        return redirect(url_for('admin.routes.list_routes'))
    return render_admin('New Route', 'admin/routes/new.html', modules=modules, scripts=scripts, forms=forms, groups=groups)


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
            return redirect(url_for('admin.routes.list_routes'))
        slug = result
        existing = db.session.query(Route).filter(Route.slug == slug, Route.id != id).first()
        if existing:
            flash(f'Route slug "{slug}" already in use by module "{existing.module.name}"')
            return redirect(url_for('admin.routes.list_routes'))
        r.slug = slug
        r.methods = request.form.get('methods', 'GET')
        r.script_id = int(request.form['script_id']) if request.form.get('script_id') else None
        r.form_id = int(request.form['form_id']) if request.form.get('form_id') else None
        r.auth_required = 'auth_required' in request.form
        r.allowed_groups = ','.join(request.form.getlist('allowed_groups'))
        r.title = request.form.get('title', '')
        db.session.commit()
        log_audit('edit', 'route', r.id, r.slug)
        return redirect(url_for('admin.routes.list_routes'))
    allowed_ids = set(r.allowed_groups.split(',') if r.allowed_groups else [])
    return render_admin('Edit Route', 'admin/routes/edit.html', r=r, modules=modules, scripts=scripts, forms=forms, groups=groups, allowed_ids=allowed_ids)

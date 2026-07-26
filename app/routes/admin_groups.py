"""Admin routes for group management."""
from flask import Blueprint, request, redirect, url_for, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required, render_admin
from app import db
from app.models import Group, User

groups_bp = Blueprint('groups', __name__)

@groups_bp.route('/')
@admin_required
def list_groups():
    groups = db.session.query(Group).order_by(Group.name).all()
    return render_admin('Groups', 'admin/groups/list.html', groups=groups)

@groups_bp.route('/new', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def new_group():
    if request.method == 'POST':
        g = Group(name=request.form['name'], description=request.form.get('description', ''))
        db.session.add(g)
        db.session.commit()
        return redirect(url_for('admin.groups.list_groups'))
    return render_admin('New Group', 'admin/groups/new.html')

@groups_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def edit_group(id):
    g = Group.query.get_or_404(id)
    users = db.session.query(User).order_by(User.username).all()
    if request.method == 'POST':
        g.name = request.form['name']
        g.description = request.form.get('description', '')
        selected_ids = [int(x) for x in request.form.getlist('user_ids')]
        g.users = [u for u in users if u.id in selected_ids]
        db.session.commit()
        return redirect(url_for('admin.groups.list_groups'))
    selected_ids = {u.id for u in g.users}
    return render_admin('Edit Group', 'admin/groups/edit.html', g=g, users=users, selected_ids=selected_ids)

@groups_bp.route('/<int:id>/delete', methods=['POST'])
@admin_required
@csrf_protect
def delete_group(id):
    g = Group.query.get_or_404(id)
    db.session.delete(g)
    db.session.commit()
    return redirect(url_for('admin.groups.list_groups'))

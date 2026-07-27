from flask import Blueprint, request, redirect, url_for, Response, flash
import csv, io
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required, render_admin
from app import db
from app.models import User
from app.services.audit import log_audit

users_bp = Blueprint('users', __name__)


@users_bp.route('/')
@admin_required
def list_users():
    sort_col = request.args.get('sort', 'created_at')
    sort_order = request.args.get('order', 'desc')
    q = db.session.query(User)
    sort_attr = getattr(User, sort_col, None)
    if sort_attr is not None:
        q = q.order_by(sort_attr.desc() if sort_order == 'desc' else sort_attr.asc())
    else:
        q = q.order_by(User.created_at.desc())
    users = q.all()
    pending = db.session.query(User).filter_by(is_approved=False).count()

    if request.args.get('format') == 'csv':
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['id', 'username', 'role', 'is_active', 'is_approved', 'created_at'])
        for u in users:
            w.writerow([u.id, u.username, u.role, u.is_active, u.is_approved, u.created_at])
        return Response(buf.getvalue(), mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=users.csv'})

    return render_admin('Users', 'admin/users/list.html', users=users, pending=pending, sort_col=sort_col, sort_order=sort_order)

@users_bp.route('/<int:id>/approve', methods=['POST'])
@admin_required
@csrf_protect
def approve_user(id):
    u = db.session.get(User, id)
    if u:
        u.is_approved = True
        u.is_active = True
        db.session.commit()
    return redirect(url_for('admin.users.list_users'))

@users_bp.route('/<int:id>/disable', methods=['POST'])
@admin_required
@csrf_protect
def disable_user(id):
    u = db.session.get(User, id)
    if u:
        u.is_active = False
        db.session.commit()
    return redirect(url_for('admin.users.list_users'))

@users_bp.route('/<int:id>/enable', methods=['POST'])
@admin_required
@csrf_protect
def enable_user(id):
    u = db.session.get(User, id)
    if u:
        u.is_active = True
        db.session.commit()
    return redirect(url_for('admin.users.list_users'))

@users_bp.route('/new', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def new_user():
    import bcrypt
    if request.method == 'POST':
        pw = bcrypt.hashpw(request.form['password'].encode(), bcrypt.gensalt()).decode()
        u = User(
            username=request.form['username'],
            password_hash=pw,
            role=request.form.get('role', 'user'),
            is_approved='is_approved' in request.form,
            is_active='is_active' in request.form,
        )
        db.session.add(u)
        db.session.commit()
        log_audit('create', 'user', u.id, u.username)
        return redirect(url_for('admin.users.list_users'))
    return render_admin('New User', 'admin/users/new.html')

@users_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def edit_user(id):
    u = User.query.get_or_404(id)
    import bcrypt
    if request.method == 'POST':
        u.username = request.form['username']
        u.role = request.form.get('role', 'user')
        u.is_approved = 'is_approved' in request.form
        u.is_active = 'is_active' in request.form
        if request.form.get('password'):
            u.password_hash = bcrypt.hashpw(request.form['password'].encode(), bcrypt.gensalt()).decode()
        db.session.commit()
        log_audit('edit', 'user', u.id, u.username)
        return redirect(url_for('admin.users.list_users'))
    return render_admin('Edit User', 'admin/users/edit.html', u=u)

"""Admin routes for user management."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash
import bcrypt
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required
from app import db
from app.models import User, Group

users_bp = Blueprint('users', __name__)


@users_bp.route('/users')
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
        from app.services.admin_utils import _export_csv
        import csv, io
        from flask import Response
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['id', 'username', 'role', 'is_active', 'is_approved', 'created_at'])
        for u in users:
            w.writerow([u.id, u.username, u.role, u.is_active, u.is_approved, u.created_at])
        return Response(buf.getvalue(), mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=users.csv'})

    return render_admin('Users', '''
{% if pending %}
<div style="background:#fff3cd;padding:0.5rem;margin-bottom:1rem;">
  <strong>{{ pending }} pending approval</strong>
</div>
{% endif %}
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.new_user') }}">+ New User</a>
  <a href="?format=csv{% if sort_col %}&sort={{ sort_col }}&order={{ sort_order }}{% endif %}" style="margin-left:auto;">Export CSV</a>
</div>
<div class="table-wrap">
<table>
<thead><tr>
  <th><a href="?sort=id&order={% if sort_col == 'id' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">ID{% if sort_col == 'id' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th><a href="?sort=username&order={% if sort_col == 'username' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">Username{% if sort_col == 'username' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th><a href="?sort=role&order={% if sort_col == 'role' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">Role{% if sort_col == 'role' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th>Status</th>
  <th><a href="?sort=created_at&order={% if sort_col == 'created_at' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">Created{% if sort_col == 'created_at' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th></th>
</tr></thead>
<tbody>
{% for u in users %}
<tr>
  <td>{{ u.id }}</td>
  <td>{{ u.username }}</td>
  <td>{{ u.role }}</td>
  <td>
    {% if not u.is_approved %}<span style="color:#856404;">Pending</span>
    {% elif not u.is_active %}<span style="color:#c00;">Disabled</span>
    {% else %}<span style="color:#080;">Active</span>{% endif %}
  </td>
  <td>{{ u.created_at|localtime }}</td>
  <td>
    <a href="{{ url_for('admin.edit_user', id=u.id) }}">Edit</a>
    {% if not u.is_approved %}
      <form method="POST" action="{{ url_for('admin.approve_user', id=u.id) }}" style="display:inline">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <button style="background:none;border:none;color:#080;cursor:pointer;text-decoration:underline;padding:0;font:inherit;font-size:0.9em;">Approve</button>
      </form>
    {% endif %}
    {% if u.is_active and u.is_approved %}
      <form method="POST" action="{{ url_for('admin.disable_user', id=u.id) }}" style="display:inline">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <button style="background:none;border:none;color:#c00;cursor:pointer;text-decoration:underline;padding:0;font:inherit;font-size:0.9em;">Disable</button>
      </form>
    {% elif not u.is_active %}
      <form method="POST" action="{{ url_for('admin.enable_user', id=u.id) }}" style="display:inline">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <button style="background:none;border:none;color:#080;cursor:pointer;text-decoration:underline;padding:0;font:inherit;font-size:0.9em;">Enable</button>
      </form>
    {% endif %}
  </td>
</tr>
{% endfor %}
</tbody></table>
</div>''', users=users, pending=pending, sort_col=sort_col, sort_order=sort_order)


@users_bp.route('/users/<int:id>/approve', methods=['POST'])
@admin_required
@csrf_protect
def approve_user(id):
    u = db.session.get(User, id)
    if u:
        u.is_approved = True
        u.is_active = True
        db.session.commit()
    return redirect(url_for('admin.list_users'))


@users_bp.route('/users/<int:id>/disable', methods=['POST'])
@admin_required
@csrf_protect
def disable_user(id):
    u = db.session.get(User, id)
    if u:
        u.is_active = False
        db.session.commit()
    return redirect(url_for('admin.list_users'))


@users_bp.route('/users/<int:id>/enable', methods=['POST'])
@admin_required
@csrf_protect
def enable_user(id):
    u = db.session.get(User, id)
    if u:
        u.is_active = True
        db.session.commit()
    return redirect(url_for('admin.list_users'))


@users_bp.route('/users/new', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def new_user():
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
        return redirect(url_for('admin.list_users'))
    return render_admin('New User', '''
<form method="POST">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>Username <input name="username" required></label>
<label>Password <input name="password" type="password" required></label>
<label>Role <select name="role"><option>admin</option><option>developer</option><option>user</option></select></label>
<label><input name="is_approved" type="checkbox" checked> Approved</label>
<label><input name="is_active" type="checkbox" checked> Active</label>
<button>Save</button>
</form>''')


@users_bp.route('/users/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def edit_user(id):
    u = User.query.get_or_404(id)
    if request.method == 'POST':
        u.username = request.form['username']
        u.role = request.form.get('role', 'user')
        u.is_approved = 'is_approved' in request.form
        u.is_active = 'is_active' in request.form
        if request.form.get('password'):
            pw = bcrypt.hashpw(request.form['password'].encode(), bcrypt.gensalt()).decode()
            u.password_hash = pw
        db.session.commit()
        return redirect(url_for('admin.list_users'))
    return render_admin('Edit User', '''
<form method="POST">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>Username <input name="username" value="{{ u.username }}" required></label>
<label>Password <input name="password" type="password" placeholder="Leave blank to keep"></label>
<label>Role <select name="role"><option {% if u.role=='admin' %}selected{% endif %}>admin</option><option {% if u.role=='developer' %}selected{% endif %}>developer</option><option {% if u.role=='user' %}selected{% endif %}>user</option></select></label>
<label><input name="is_approved" type="checkbox" {% if u.is_approved %}checked{% endif %}> Approved</label>
<label><input name="is_active" type="checkbox" {% if u.is_active %}checked{% endif %}> Active</label>
<button>Save</button>
</form>''', u=u)

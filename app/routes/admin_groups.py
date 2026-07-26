"""Admin routes for group management."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required
from app import db
from app.models import Group, User

groups_bp = Blueprint('groups', __name__)


@groups_bp.route('/groups')
@admin_required
def list_groups():
    groups = db.session.query(Group).order_by(Group.name).all()
    return render_admin('Groups', '''
<a href="{{ url_for('admin.new_group') }}">+ New Group</a>
<table>
<thead><tr><th>ID</th><th>Name</th><th>Description</th><th>Members</th><th></th></tr></thead>
<tbody>
{% for g in groups %}
<tr>
  <td>{{ g.id }}</td>
  <td>{{ g.name }}</td>
  <td>{{ g.description[:60] if g.description else '' }}</td>
  <td>{{ g.users|length }}</td>
  <td>
    <a href="{{ url_for('admin.edit_group', id=g.id) }}">Edit</a>
    <form method="POST" action="{{ url_for('admin.delete_group', id=g.id) }}" style="display:inline" onsubmit="return confirm('Delete group {{ g.name }}?')">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <button style="background:none;border:none;color:#c00;cursor:pointer;text-decoration:underline;padding:0;font:inherit;font-size:0.9em;">Delete</button>
    </form>
  </td>
</tr>
{% endfor %}
</tbody></table>''', groups=groups)


@groups_bp.route('/groups/new', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def new_group():
    if request.method == 'POST':
        g = Group(name=request.form['name'], description=request.form.get('description', ''))
        db.session.add(g)
        db.session.commit()
        return redirect(url_for('admin.list_groups'))
    return render_admin('New Group', '''
<form method="POST">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>Name <input name="name" required></label>
<label>Description <textarea name="description" rows="3" style="width:100%;max-width:400px;"></textarea></label>
<button>Save</button>
</form>''')


@groups_bp.route('/groups/edit/<int:id>', methods=['GET', 'POST'])
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
        return redirect(url_for('admin.list_groups'))
    selected_ids = {u.id for u in g.users}
    return render_admin('Edit Group', '''
<form method="POST">
<label>Name <input name="name" value="{{ g.name }}" required></label>
<label>Description <textarea name="description" rows="3" style="width:100%;max-width:400px;">{{ g.description }}</textarea></label>
<p><strong>Members</strong></p>
{% for u in users %}
<label style="display:block;font-weight:normal;">
  <input name="user_ids" type="checkbox" value="{{ u.id }}" {% if u.id in selected_ids %}checked{% endif %}>
  {{ u.username }} ({{ u.role }})
</label>
{% endfor %}
<button>Save</button>
</form>''', g=g, users=users, selected_ids=selected_ids)


@groups_bp.route('/groups/<int:id>/delete', methods=['POST'])
@admin_required
@csrf_protect
def delete_group(id):
    g = Group.query.get_or_404(id)
    db.session.delete(g)
    db.session.commit()
    return redirect(url_for('admin.list_groups'))

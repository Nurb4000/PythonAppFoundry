"""Admin routes for extended group management."""
from flask import Blueprint, request, redirect, url_for, render_template_string

group_extended_bp = Blueprint('group_extended', __name__)


@group_extended_bp.route('/groups/<int:id>/users')
@admin_required
def group_users(id):
    """View users in a group."""
    from app.models import Group, User
    
    group = db.session.get(Group, id)
    if not group:
        flash('Group not found', 'error')
        return redirect(url_for('admin.list_groups'))
    
    users = group.users.order_by(User.username).all()
    
    return render_admin(f'Users in {group.name}', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.list_groups') }}">Back to Groups</a>
</div>
{% if users %}
<div class="table-wrap">
<table>
<thead><tr>
  <th>Username</th>
  <th>Role</th>
  <th>Status</th>
</tr></thead>
<tbody>
{% for u in users %}
<tr>
  <td>{{ u.username }}</td>
  <td>{{ u.role }}</td>
  <td>{% if u.is_active and u.is_approved %}<span style="color:#080;">Active</span>{% elif not u.is_approved %}<span style="color:#856404;">Pending</span>{% else %}<span style="color:#c00;">Disabled</span>{% endif %}</td>
</tr>
{% endfor %}
</tbody></table>
</div>
{% else %}
<p style="color:#888;">No users in this group.</p>
{% endif %}''', group=group, users=users)


@group_extended_bp.route('/groups/<int:id>/add-user/<int:user_id>', methods=['POST'])
@admin_required
@csrf_protect
def add_user_to_group(id, user_id):
    """Add a user to a group."""
    from app.models import Group, User
    
    group = db.session.get(Group, id)
    user = db.session.get(User, user_id)
    
    if not group or not user:
        flash('Group or user not found', 'error')
        return redirect(url_for('admin.list_groups'))
    
    if user not in group.users:
        group.users.append(user)
        db.session.commit()
        flash(f'Added {user.username} to {group.name}')
    
    return redirect(url_for('admin.group_users', id=id))


@group_extended_bp.route('/groups/<int:id>/remove-user/<int:user_id>', methods=['POST'])
@admin_required
@csrf_protect
def remove_user_from_group(id, user_id):
    """Remove a user from a group."""
    from app.models import Group, User
    
    group = db.session.get(Group, id)
    user = db.session.get(User, user_id)
    
    if not group or not user:
        flash('Group or user not found', 'error')
        return redirect(url_for('admin.list_groups'))
    
    if user in group.users:
        group.users.remove(user)
        db.session.commit()
        flash(f'Removed {user.username} from {group.name}')
    
    return redirect(url_for('admin.group_users', id=id))

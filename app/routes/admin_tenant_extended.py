"""Admin routes for extended tenant management."""
from flask import Blueprint, request, redirect, url_for, render_template_string

tenant_extended_bp = Blueprint('tenant_extended', __name__)


@tenant_extended_bp.route('/tenants/<int:id>/modules')
@admin_required
def tenant_modules(id):
    """View modules for a specific tenant."""
    from app.services.tenant import _tenants
    from app.models import Module
    
    tenant = _tenants.get(id)
    if not tenant:
        flash('Tenant not found', 'error')
        return redirect(url_for('admin.list_tenants'))
    
    # In a real implementation, you'd filter modules by tenant
    # For now, show all modules with a note
    modules = db.session.query(Module).all()
    
    return render_admin(f'Modules for {tenant.name}', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.list_tenants') }}">Back to Tenants</a>
</div>
<p style="color:#666;margin-bottom:1rem;">Note: Module filtering by tenant is not yet implemented. All modules are shown.</p>
{% if modules %}
<div class="table-wrap">
<table>
<thead><tr>
  <th>Name</th>
  <th>Slug</th>
  <th>Status</th>
</tr></thead>
<tbody>
{% for m in modules %}
<tr>
  <td>{{ m.name }}</td>
  <td><code>{{ m.slug }}</code></td>
  <td>{% if m.enabled %}<span style="color:#080;">Enabled</span>{% else %}<span style="color:#c00;">Disabled</span>{% endif %}</td>
</tr>
{% endfor %}
</tbody></table>
</div>
{% else %}
<p style="color:#888;">No modules found.</p>
{% endif %}''', tenant=tenant, modules=modules)


@tenant_extended_bp.route('/tenants/<int:id>/users')
@admin_required
def tenant_users(id):
    """View users for a specific tenant."""
    from app.services.tenant import _tenants
    from app.models import User
    
    tenant = _tenants.get(id)
    if not tenant:
        flash('Tenant not found', 'error')
        return redirect(url_for('admin.list_tenants'))
    
    # In a real implementation, you'd filter users by tenant
    # For now, show all users with a note
    users = db.session.query(User).all()
    
    return render_admin(f'Users for {tenant.name}', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.list_tenants') }}">Back to Tenants</a>
</div>
<p style="color:#666;margin-bottom:1rem;">Note: User filtering by tenant is not yet implemented. All users are shown.</p>
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
<p style="color:#888;">No users found.</p>
{% endif %}''', tenant=tenant, users=users)


@tenant_extended_bp.route('/tenants/stats')
@admin_required
def tenant_stats():
    """View tenant statistics."""
    from app.services.tenant import _tenants
    
    tenants = list(_tenants.values())
    
    return render_admin('Tenant Statistics', '''
<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:1rem;">
  {% for tenant in tenants %}
  <div class="dash-card">
    <h3>{{ tenant.name }}</h3>
    <ul style="margin:0;padding-left:1.5rem;line-height:1.8;">
      <li><strong>Slug:</strong> {{ tenant.slug }}</li>
      <li><strong>Subdomain:</strong> {{ tenant.config.get('subdomain', '—') or '—' }}</li>
      <li><strong>Path Prefix:</strong> {{ tenant.config.get('path_prefix', '—') or '—' }}</li>
    </ul>
  </div>
  {% endfor %}
</div>
''', tenants=tenants)

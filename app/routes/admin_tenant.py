"""Admin routes for tenant management."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash

tenant_bp = Blueprint('tenant', __name__)


@tenant_bp.route('/tenants')
@admin_required
def list_tenants():
    """List all configured tenants."""
    from app.services.tenant import _tenants, _default_tenant
    tenants = list(_tenants.values())
    
    return render_admin('Tenants', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.list_modules') }}">Back to Modules</a>
</div>
{% if tenants %}
<div class="table-wrap">
<table>
<thead><tr>
  <th>ID</th>
  <th>Name</th>
  <th>Slug</th>
  <th>Subdomain</th>
  <th>Path Prefix</th>
</tr></thead>
<tbody>
{% for t in tenants %}
<tr>
  <td>{{ t.id }}</td>
  <td><strong>{{ t.name }}</strong></td>
  <td><code>{{ t.slug }}</code></td>
  <td>{{ t.config.get('subdomain', '') or '—' }}</td>
  <td>{{ t.config.get('path_prefix', '') or '—' }}</td>
</tr>
{% endfor %}
</tbody></table>
</div>
{% else %}
<p style="color:#888;">No tenants configured.</p>
{% endif %}''', tenants=tenants)


@tenant_bp.route('/tenants/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_tenant(id):
    """Edit a tenant configuration."""
    from app.services.tenant import _tenants
    tenant = _tenants.get(id)
    if not tenant:
        flash('Tenant not found', 'error')
        return redirect(url_for('admin.list_tenants'))
    
    if request.method == 'POST':
        tenant.name = request.form.get('name', tenant.name)
        tenant.slug = request.form.get('slug', tenant.slug)
        tenant.config['subdomain'] = request.form.get('subdomain', '')
        tenant.config['path_prefix'] = request.form.get('path_prefix', '')
        flash(f'Tenant "{tenant.name}" updated')
        return redirect(url_for('admin.list_tenants'))
    
    return render_admin(f'Edit Tenant: {tenant.name}', '''
<form method="POST">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>Name <input name="name" value="{{ tenant.name }}" required></label>
<label>Slug <input name="slug" value="{{ tenant.slug }}" required></label>
<label>Subdomain <input name="subdomain" value="{{ tenant.config.get('subdomain', '') }}"></label>
<label>Path Prefix <input name="path_prefix" value="{{ tenant.config.get('path_prefix', '') }}"></label>
<button>Save</button>
</form>''', tenant=tenant)


@tenant_bp.route('/tenants/new', methods=['GET', 'POST'])
@admin_required
def new_tenant():
    """Create a new tenant."""
    from app.services.tenant import _tenants, Tenant
    from app import db
    
    if request.method == 'POST':
        max_id = max([t.id for t in _tenants.values()], default=0)
        tenant = Tenant(
            id=max_id + 1,
            name=request.form['name'],
            slug=request.form['slug'],
            config={
                'subdomain': request.form.get('subdomain', ''),
                'path_prefix': request.form.get('path_prefix', ''),
            }
        )
        _tenants[tenant.slug] = tenant
        flash(f'Tenant "{tenant.name}" created')
        return redirect(url_for('admin.list_tenants'))
    
    return render_admin('New Tenant', '''
<form method="POST">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>Name <input name="name" required></label>
<label>Slug <input name="slug" required></label>
<label>Subdomain <input name="subdomain"></label>
<label>Path Prefix <input name="path_prefix"></label>
<button>Save</button>
</form>''')


@tenant_bp.route('/tenants/<int:id>/delete', methods=['POST'])
@admin_required
@csrf_protect
def delete_tenant(id):
    """Delete a tenant."""
    from app.services.tenant import _tenants
    tenant = _tenants.get(id)
    if not tenant:
        flash('Tenant not found', 'error')
        return redirect(url_for('admin.list_tenants'))
    
    del _tenants[tenant.slug]
    flash(f'Tenant "{tenant.name}" deleted')
    return redirect(url_for('admin.list_tenants'))

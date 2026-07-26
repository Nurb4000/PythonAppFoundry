"""Admin routes for module marketplace."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import developer_or_admin_required
import os

marketplace_bp = Blueprint('marketplace', __name__)


@marketplace_bp.route('/marketplace')
@developer_or_admin_required
def module_marketplace():
    """Browse and install modules from the marketplace."""
    from app.services.marketplace import list_available_modules
    available = list_available_modules()
    
    # Check which are already installed
    installed_slugs = {m.slug for m in db.session.query(Module.slug).all()}
    
    return render_admin('Module Marketplace', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.list_modules') }}">Back to Modules</a>
</div>
{% if available %}
<div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(300px, 1fr));gap:1rem;">
{% for mod in available %}
<div style="border:1px solid #ddd;border-radius:8px;padding:1rem;">
  <h3 style="margin-top:0;">{{ mod.name }}</h3>
  <p style="color:#666;font-size:0.9em;">{{ mod.description[:200] }}...</p>
  <div style="font-size:0.85em;color:#888;margin-bottom:0.5rem;">
    Version: {{ mod.version }} | Author: {{ mod.author }}
    {% if mod.tags %} | Tags: {{ mod.tags|join(', ') }}{% endif %}
  </div>
  {% if mod.slug in installed_slugs %}
    <span style="color:#080;font-weight:bold;">Installed</span>
  {% else %}
    <form method="POST" action="{{ url_for('admin.install_marketplace_module', slug=mod.slug) }}" style="display:inline;">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <button type="submit" style="padding:6px 16px;background:#2563eb;color:#fff;border:none;border-radius:4px;cursor:pointer;">Install</button>
    </form>
  {% endif %}
</div>
{% endfor %}
</div>
{% else %}
<p style="color:#888;">No modules available in the marketplace yet.</p>
{% endif %}''', available=available, installed_slugs=installed_slugs)


@marketplace_bp.route('/marketplace/<slug>/install', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def install_marketplace_module(slug):
    """Install a module from the marketplace."""
    from app.services.marketplace import get_module_info
    from app.services.bundle import import_module
    
    info = get_module_info(slug)
    if not info:
        flash(f'Module "{slug}" not found in marketplace', 'error')
        return redirect(url_for('admin.module_marketplace'))
    
    xml_path = info.get('xml_source')
    if not xml_path or not os.path.exists(xml_path):
        flash(f'Module XML not found for "{slug}"', 'error')
        return redirect(url_for('admin.module_marketplace'))
    
    try:
        with open(xml_path) as f:
            xml_str = f.read()
        module = import_module(xml_str)
        flash(f'Module "{module.name}" installed from marketplace')
    except Exception as e:
        flash(f'Installation failed: {e}', 'error')
    
    return redirect(url_for('admin.module_marketplace'))

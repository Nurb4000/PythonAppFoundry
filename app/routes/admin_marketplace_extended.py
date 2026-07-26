"""Admin routes for extended marketplace functionality."""
from flask import Blueprint, request, redirect, url_for, flash

marketplace_extended_bp = Blueprint('marketplace_extended', __name__)


@marketplace_extended_bp.route('/marketplace/<slug>/unpublish', methods=['POST'])
@admin_required
@csrf_protect
def unpublish_module(slug):
    """Unpublish a module from the marketplace."""
    from app.services.marketplace import remove_module
    
    if remove_module(slug):
        flash(f'Module "{slug}" unpublished from marketplace')
    else:
        flash('Failed to unpublish module', 'error')
    
    return redirect(url_for('admin.module_marketplace'))


@marketplace_extended_bp.route('/marketplace/publish', methods=['POST'])
@admin_required
@csrf_protect
def publish_module():
    """Publish a module to the marketplace."""
    from app.services.marketplace import publish_module as _publish
    from app.models import Module
    
    module_id = request.form.get('module_id')
    if not module_id:
        flash('Module ID required', 'error')
        return redirect(url_for('admin.module_marketplace'))
    
    module = db.session.get(Module, int(module_id))
    if not module:
        flash('Module not found', 'error')
        return redirect(url_for('admin.module_marketplace'))
    
    try:
        # Export module to XML and save to marketplace
        from app.services.bundle import export_module
        import os
        
        xml_str = export_module(module)
        xml_path = f'marketplace/{module.slug}.xml'
        
        os.makedirs('marketplace', exist_ok=True)
        with open(xml_path, 'w') as f:
            f.write(xml_str)
        
        _publish(
            slug=module.slug,
            name=module.name,
            description=module.description or '',
            version=module.version,
            author=module.author or 'System',
            xml_path=xml_path,
            tags=['platform-generated'],
        )
        flash(f'Module "{module.name}" published to marketplace')
    except Exception as e:
        flash(f'Failed to publish module: {e}', 'error')
    
    return redirect(url_for('admin.module_marketplace'))


@marketplace_extended_bp.route('/marketplace/<slug>/info')
@developer_or_admin_required
def marketplace_module_info(slug):
    """View detailed information about a marketplace module."""
    from app.services.marketplace import get_module_info
    
    info = get_module_info(slug)
    if not info:
        flash('Module not found in marketplace', 'error')
        return redirect(url_for('admin.module_marketplace'))
    
    return render_admin(f'Module Info: {info["name"]}', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.module_marketplace') }}">Back to Marketplace</a>
</div>
<div class="dash-card">
  <h3>{{ info.name }}</h3>
  <p><strong>Slug:</strong> {{ info.slug }}</p>
  <p><strong>Version:</strong> {{ info.version }}</p>
  <p><strong>Author:</strong> {{ info.author }}</p>
  <p><strong>Description:</strong> {{ info.description }}</p>
  {% if info.tags %}
  <p><strong>Tags:</strong> {{ info.tags|join(', ') }}</p>
  {% endif %}
  <p><strong>Published:</strong> {{ info.published_at }}</p>
</div>
''', info=info)

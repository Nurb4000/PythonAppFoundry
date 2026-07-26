"""Admin routes for extended dependency management."""
from flask import Blueprint, request, redirect, url_for, render_template_string

dependency_extended_bp = Blueprint('dependency_extended', __name__)


@dependency_extended_bp.route('/modules/<int:module_id>/dependencies/scan-all', methods=['POST'])
@admin_required
@csrf_protect
def scan_all_dependencies(module_id):
    """Scan all modules for dependencies."""
    from app.models import Module
    from app.services.dependencies import detect_dependencies
    
    modules = db.session.query(Module).all()
    total_deps = 0
    
    for module in modules:
        try:
            deps = detect_dependencies(module.id)
            total_deps += len(deps)
        except Exception:
            pass
    
    flash(f'Scanned {len(modules)} module(s). Found {total_deps} dependency reference(s).')
    return redirect(url_for('admin.list_modules'))


@dependency_extended_bp.route('/modules/<int:module_id>/dependencies/clear', methods=['POST'])
@admin_required
@csrf_protect
def clear_dependencies(module_id):
    """Clear all dependencies for a module."""
    from app.models import ModuleDependency, Module
    
    module = db.session.get(Module, module_id)
    if not module:
        flash('Module not found', 'error')
        return redirect(url_for('admin.list_modules'))
    
    # Delete all dependencies involving this module
    ModuleDependency.query.filter_by(source_module_id=module_id).delete()
    ModuleDependency.query.filter_by(target_module_id=module_id).delete()
    db.session.commit()
    
    flash(f'Cleared dependencies for {module.name}')
    return redirect(url_for('admin.list_modules'))


@dependency_extended_bp.route('/modules/<int:module_id>/dependencies/view-all')
@admin_required
def view_all_dependencies(module_id):
    """View all dependencies for a module (both incoming and outgoing)."""
    from app.models import ModuleDependency, Module
    
    module = db.session.get(Module, module_id)
    if not module:
        flash('Module not found', 'error')
        return redirect(url_for('admin.list_modules'))
    
    # Incoming dependencies (modules that depend on this one)
    incoming = ModuleDependency.query.filter_by(target_module_id=module_id).all()
    
    # Outgoing dependencies (modules that this one depends on)
    outgoing = ModuleDependency.query.filter_by(source_module_id=module_id).all()
    
    return render_admin(f'Dependencies: {module.name}', '''
<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
  <div>
    <h3>Incoming Dependencies ({{ incoming|length }})</h3>
    {% if incoming %}
    <div class="table-wrap">
    <table>
    <thead><tr><th>Module</th><th>Type</th><th>Reference</th></tr></thead>
    <tbody>
    {% for dep in incoming %}
    <tr>
      <td>{{ dep.source_module.name if dep.source_module else 'Unknown' }}</td>
      <td>{{ dep.dependency_type }}</td>
      <td><code>{{ dep.reference_value }}</code></td>
    </tr>
    {% endfor %}
    </tbody></table>
    </div>
    {% else %}
    <p style="color:#888;">No incoming dependencies.</p>
    {% endif %}
  </div>
  
  <div>
    <h3>Outgoing Dependencies ({{ outgoing|length }})</h3>
    {% if outgoing %}
    <div class="table-wrap">
    <table>
    <thead><tr><th>Module</th><th>Type</th><th>Reference</th></tr></thead>
    <tbody>
    {% for dep in outgoing %}
    <tr>
      <td>{{ dep.target_module.name if dep.target_module else 'Unknown' }}</td>
      <td>{{ dep.dependency_type }}</td>
      <td><code>{{ dep.reference_value }}</code></td>
    </tr>
    {% endfor %}
    </tbody></table>
    </div>
    {% else %}
    <p style="color:#888;">No outgoing dependencies.</p>
    {% endif %}
  </div>
</div>
''', module=module, incoming=incoming, outgoing=outgoing)


@dependency_extended_bp.route('/modules/<int:module_id>/dependencies/stats')
@admin_required
def dependency_stats(module_id):
    """View dependency statistics for a module."""
    from app.models import ModuleDependency, Module
    
    module = db.session.get(Module, module_id)
    if not module:
        flash('Module not found', 'error')
        return redirect(url_for('admin.list_modules'))
    
    # Count incoming and outgoing dependencies
    incoming_count = ModuleDependency.query.filter_by(target_module_id=module_id).count()
    outgoing_count = ModuleDependency.query.filter_by(source_module_id=module_id).count()
    
    # Count by type
    route_refs = ModuleDependency.query.filter_by(source_module_id=module_id, dependency_type='route_reference').count()
    script_refs = ModuleDependency.query.filter_by(source_module_id=module_id, dependency_type='script_reference').count()
    form_refs = ModuleDependency.query.filter_by(source_module_id=module_id, dependency_type='form_reference').count()
    
    return render_admin(f'Dependency Stats: {module.name}', '''
<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
  <div class="dash-card">
    <h3>Summary</h3>
    <ul style="margin:0;padding-left:1.5rem;line-height:1.8;">
      <li><strong>Incoming:</strong> {{ incoming_count }}</li>
      <li><strong>Outgoing:</strong> {{ outgoing_count }}</li>
    </ul>
  </div>
  
  <div class="dash-card">
    <h3>By Type (Outgoing)</h3>
    <ul style="margin:0;padding-left:1.5rem;line-height:1.8;">
      <li>Route References: {{ route_refs }}</li>
      <li>Script References: {{ script_refs }}</li>
      <li>Form References: {{ form_refs }}</li>
    </ul>
  </div>
</div>
''', module=module, incoming_count=incoming_count, outgoing_count=outgoing_count, route_refs=route_refs, script_refs=script_refs, form_refs=form_refs)

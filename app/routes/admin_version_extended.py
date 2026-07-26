"""Admin routes for extended version management."""
from flask import Blueprint, request, redirect, url_for, render_template_string

version_extended_bp = Blueprint('version_extended', __name__)


@version_extended_bp.route('/modules/<int:module_id>/versions/restore-all', methods=['POST'])
@admin_required
@csrf_protect
def restore_all_versions(module_id):
    """Restore all versions of a module (rollback to first version)."""
    from app.models import Module, ModuleVersion
    
    module = db.session.get(Module, module_id)
    if not module:
        flash('Module not found', 'error')
        return redirect(url_for('admin.list_modules'))
    
    versions = module.versions.order_by(ModuleVersion.created_at.asc()).all()
    if not versions:
        flash('No versions to restore', 'error')
        return redirect(url_for('admin.list_versions', module_id=module_id))
    
    # Restore to the first version
    first_version = versions[0]
    try:
        from app.services.versioning import restore_version as _restore_version
        _restore_version(first_version.id)
        flash(f'Restored module to version {first_version.version_number}')
    except Exception as e:
        flash(f'Failed to restore: {e}', 'error')
    
    return redirect(url_for('admin.list_versions', module_id=module_id))


@version_extended_bp.route('/modules/<int:module_id>/versions/delete-all', methods=['POST'])
@admin_required
@csrf_protect
def delete_all_versions(module_id):
    """Delete all versions of a module."""
    from app.models import Module, ModuleVersion
    
    module = db.session.get(Module, module_id)
    if not module:
        flash('Module not found', 'error')
        return redirect(url_for('admin.list_modules'))
    
    versions = module.versions.all()
    deleted = 0
    for version in versions:
        db.session.delete(version)
        deleted += 1
    
    db.session.commit()
    flash(f'Deleted {deleted} version(s)')
    return redirect(url_for('admin.list_versions', module_id=module_id))


@version_extended_bp.route('/modules/<int:module_id>/versions/export', methods=['GET'])
@admin_required
def export_versions(module_id):
    """Export all versions of a module as a ZIP file."""
    import zipfile
    import io
    from flask import Response
    from app.models import Module, ModuleVersion
    
    module = db.session.get(Module, module_id)
    if not module:
        flash('Module not found', 'error')
        return redirect(url_for('admin.list_modules'))
    
    versions = module.versions.order_by(ModuleVersion.created_at.desc()).all()
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for version in versions:
            zf.writestr(f'{version.version_number}.xml', version.snapshot_xml)
    
    zip_buffer.seek(0)
    return Response(
        zip_buffer.read(),
        mimetype='application/zip',
        headers={'Content-Disposition': f'attachment; filename="{module.slug}_versions.zip"'}
    )


@version_extended_bp.route('/modules/<int:module_id>/versions/stats')
@admin_required
def version_stats(module_id):
    """View version statistics for a module."""
    from app.models import Module, ModuleVersion
    
    module = db.session.get(Module, module_id)
    if not module:
        flash('Module not found', 'error')
        return redirect(url_for('admin.list_modules'))
    
    versions = module.versions.all()
    total_versions = len(versions)
    current_version = next((v for v in versions if v.is_current), None)
    
    return render_admin(f'Version Stats: {module.name}', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.list_versions', module_id=m.id) }}">Back to Versions</a>
</div>
<div class="dash-card">
  <h3>{{ m.name }}</h3>
  <ul style="margin:0;padding-left:1.5rem;line-height:1.8;">
    <li><strong>Total Versions:</strong> {{ total_versions }}</li>
    {% if current_version %}
    <li><strong>Current Version:</strong> {{ current_version.version_number }}</li>
    <li><strong>Last Updated:</strong> {{ current_version.created_at.strftime('%Y-%m-%d %H:%M') }}</li>
    {% else %}
    <li><strong>No versions created yet.</strong></li>
    {% endif %}
  </ul>
</div>
''', m=module, total_versions=total_versions, current_version=current_version)

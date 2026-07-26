from flask import Blueprint, request, redirect, url_for, flash
from flask_login import current_user
from app.services.csrf import csrf_protect
from app.services.admin_utils import developer_or_admin_required, render_admin
from app import db
from app.models import Module, ModuleVersion

versions_bp = Blueprint('versions', __name__)


@versions_bp.route('/')
@developer_or_admin_required
def list_versions(module_id):
    m = Module.query.get_or_404(module_id)
    versions = m.versions.order_by(ModuleVersion.created_at.desc()).all()
    return render_admin(f'Versions - {m.name}', 'admin/versions/list.html', m=m, versions=versions)


@versions_bp.route('/create', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def create_version(module_id):
    m = Module.query.get_or_404(module_id)
    comment = request.form.get('comment', '')
    try:
        from app.services.versioning import create_version as _create_version
        _create_version(module_id, comment=comment, user_id=current_user.id if current_user.is_authenticated else None)
        flash(f'Version created for "{m.name}"')
    except Exception as e:
        flash(f'Failed to create version: {e}', 'error')
    return redirect(url_for('admin.versions.list_versions', module_id=module_id))


@versions_bp.route('/<int:version_id>/restore', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def restore_version(module_id, version_id):
    v = ModuleVersion.query.get_or_404(version_id)
    try:
        from app.services.versioning import restore_version as _restore_version
        _restore_version(version_id)
        flash(f'Restored "{v.module.name}" to version {v.version_number}')
    except Exception as e:
        flash(f'Failed to restore version: {e}', 'error')
    return redirect(url_for('admin.versions.list_versions', module_id=module_id))


@versions_bp.route('/<int:version_id>/diff')
@developer_or_admin_required
def diff_version(module_id, version_id):
    v = ModuleVersion.query.get_or_404(version_id)
    versions = v.module.versions.order_by(ModuleVersion.created_at.desc()).all()
    
    v_index = next((i for i, ver in enumerate(versions) if ver.id == version_id), None)
    prev_version = None
    if v_index is not None and v_index + 1 < len(versions):
        prev_version = versions[v_index + 1]
    
    diff_text = ''
    if prev_version:
        try:
            from app.services.versioning import diff_versions as _diff_versions
            diff_text = _diff_versions(version_id, prev_version.id)
        except Exception as e:
            diff_text = f'Error generating diff: {e}'
    
    return render_admin(f'Diff - Version {v.version_number}', 'admin/versions/diff.html', m=v.module, v=v, prev_version=prev_version, diff_text=diff_text)

from flask import Blueprint, request, redirect, url_for, flash, jsonify
from flask_login import current_user
from app.services.csrf import csrf_protect
from app.services.admin_utils import developer_or_admin_required, render_admin
from app import db
from app.models import Module, ModuleVersion
from app.services.audit import log_audit

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
        log_audit('create', 'version', module_id, m.name)
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
        log_audit('restore', 'version', version_id, v.module.name)
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


@versions_bp.route('/compare')
@developer_or_admin_required
def compare_versions(module_id):
    v1_id = request.args.get('v1', type=int)
    v2_id = request.args.get('v2', type=int)

    if not v1_id or not v2_id:
        flash('Please select two versions to compare.', 'error')
        return redirect(url_for('admin.versions.list_versions', module_id=module_id))

    v1 = ModuleVersion.query.get(v1_id)
    v2 = ModuleVersion.query.get(v2_id)

    if not v1 or not v2:
        flash('One or both versions not found.', 'error')
        return redirect(url_for('admin.versions.list_versions', module_id=module_id))

    if v1.module_id != module_id or v2.module_id != module_id:
        flash('Versions must belong to the same module.', 'error')
        return redirect(url_for('admin.versions.list_versions', module_id=module_id))

    if v1.id == v2.id:
        flash('Please select two different versions to compare.', 'error')
        return redirect(url_for('admin.versions.list_versions', module_id=module_id))

    # Ensure v1 is the older version for display
    if v1.created_at > v2.created_at:
        v1, v2 = v2, v1

    try:
        from app.services.versioning import structured_diff_versions as _structured_diff
        diff_result = _structured_diff(v1.id, v2.id)
    except Exception as e:
        flash(f'Error generating structured diff: {e}', 'error')
        return redirect(url_for('admin.versions.list_versions', module_id=module_id))

    return render_admin(
        f'Compare: {v1.version_number} vs {v2.version_number}',
        'admin/versions/compare.html',
        m=v1.module,
        v1=v1,
        v2=v2,
        diff=diff_result,
    )


@versions_bp.route('/<int:version_id>/check-deps')
@developer_or_admin_required
def check_restore_deps(module_id, version_id):
    """JSON endpoint to check dependency safety before restoring a version."""
    v = ModuleVersion.query.get_or_404(version_id)
    if v.module_id != module_id:
        return jsonify({'error': 'Version does not belong to this module'}), 404

    try:
        from app.services.versioning import validate_restore_dependencies as _validate
        result = _validate(v.id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'safe': False, 'warnings': [], 'errors': [str(e)], 'referenced_slugs': []}), 500

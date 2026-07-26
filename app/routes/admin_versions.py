"""Admin routes for module version management."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import developer_or_admin_required, create_auto_version
from app import db
from app.models import Module, ModuleVersion

versions_bp = Blueprint('versions', __name__)


@versions_bp.route('/modules/<int:module_id>/versions')
@developer_or_admin_required
def list_versions(module_id):
    m = Module.query.get_or_404(module_id)
    versions = m.versions.order_by(ModuleVersion.created_at.desc()).all()
    return render_admin(f'Versions - {m.name}', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.edit_module', id=m.id) }}">Back to Module</a>
  <form method="POST" action="{{ url_for('admin.create_version', module_id=m.id) }}" style="display:inline;flex:1;max-width:400px;">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <input type="text" name="comment" placeholder="Version comment (e.g., 'Added contact form')" style="flex:1;padding:6px 12px;border:1px solid #ddd;border-radius:4px;">
    <button type="submit" style="padding:6px 16px;background:#2563eb;color:white;border:none;border-radius:4px;cursor:pointer;">Create Version</button>
  </form>
</div>
<div class="table-wrap">
<table>
<thead><tr>
  <th>Version</th>
  <th>Comment</th>
  <th>Author</th>
  <th>Date</th>
  <th>Status</th>
  <th>Actions</th>
</tr></thead>
<tbody>
{% for v in versions %}
<tr>
  <td><strong>{{ v.version_number }}</strong></td>
  <td>{{ v.comment or '-' }}</td>
  <td>{{ v.created_by.username if v.created_by else 'System' }}</td>
  <td style="white-space:nowrap;">{{ v.created_at|localtime }}</td>
  <td>{% if v.is_current %}<span style="color:#16a34a;font-weight:bold;">Current</span>{% else %}<span style="color:#888;">Past</span>{% endif %}</td>
  <td>
    {% if not v.is_current %}
    <form method="POST" action="{{ url_for('admin.restore_version', version_id=v.id) }}" style="display:inline" onsubmit="return confirm('Restore module to version {{ v.version_number }}? This will replace the current state.')">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <button type="submit" style="background:none;border:none;color:#2563eb;cursor:pointer;text-decoration:underline;padding:0;font:inherit;">Restore</button>
    </form>
    {% endif %}
    |
    {% if loop.length > 1 %}
    <a href="{{ url_for('admin.diff_version', version_id=v.id) }}">Diff</a>
    {% endif %}
  </td>
</tr>
{% endfor %}
</tbody></table>
</div>
{% if not versions %}
<p style="color:#888;">No versions created yet. Create a version to start tracking changes.</p>
{% endif %}
''', m=m, versions=versions)


@versions_bp.route('/modules/<int:module_id>/versions/create', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def create_version(module_id):
    m = Module.query.get_or_404(module_id)
    comment = request.form.get('comment', '')
    try:
        create_auto_version(module_id, comment=comment)
        flash(f'Version created for "{m.name}"')
    except Exception as e:
        flash(f'Failed to create version: {e}', 'error')
    return redirect(url_for('admin.list_versions', module_id=module_id))


@versions_bp.route('/modules/versions/<int:version_id>/restore', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def restore_version(version_id):
    v = ModuleVersion.query.get_or_404(version_id)
    try:
        from app.services.versioning import restore_version as _restore_version
        _restore_version(version_id)
        flash(f'Restored "{v.module.name}" to version {v.version_number}')
    except Exception as e:
        flash(f'Failed to restore version: {e}', 'error')
    return redirect(url_for('admin.list_versions', module_id=v.module_id))


@versions_bp.route('/modules/versions/<int:version_id>/diff')
@developer_or_admin_required
def diff_version(version_id):
    v = ModuleVersion.query.get_or_404(version_id)
    versions = v.module.versions.order_by(ModuleVersion.created_at.desc()).all()
    
    # Find the previous version for diffing
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
    
    return render_admin(f'Diff - Version {v.version_number}', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.list_versions', module_id=m.id) }}">Back to Versions</a>
</div>
<h2>Diff: Version {{ v.version_number }}</h2>
{% if prev_version %}
<p style="color:#888;margin-bottom:1rem;">Comparing against version {{ prev_version.version_number }} ({{ prev_version.created_at|localtime }})</p>
{% endif %}
<div class="table-wrap">
<pre style="background:#f4f4f4;padding:1rem;overflow:auto;font-size:0.85rem;max-height:600px;white-space:pre-wrap;word-wrap:break-word;">{{ diff_text or 'No changes to display.' }}</pre>
</div>
{% if not diff_text %}
<p style="color:#888;">This is the first version, or unable to generate diff.</p>
{% endif %}
''', m=v.module, v=v, prev_version=prev_version, diff_text=diff_text)

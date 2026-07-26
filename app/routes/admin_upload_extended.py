"""Admin routes for extended upload management."""
from flask import Blueprint, request, redirect, url_for, render_template_string

upload_extended_bp = Blueprint('upload_extended', __name__)


@upload_extended_bp.route('/uploads/<int:id>/preview')
@developer_or_admin_required
def preview_upload(id):
    """Preview an uploaded file."""
    from app.models import Upload
    
    upload = db.session.get(Upload, id)
    if not upload:
        flash('Upload not found', 'error')
        return redirect(url_for('admin.list_uploads'))
    
    # Check if it's an image
    if upload.mime_type.startswith('image/'):
        return render_admin(f'Preview: {upload.original_name}', f'''
<img src="/uploads/{upload.filename}" style="max-width:100%;max-height:500px;">
<p>Original: {upload.original_name}</p>
<p>Type: {upload.mime_type}</p>
<p>Size: {upload.size} bytes</p>
''')
    else:
        flash('Preview not available for this file type', 'error')
        return redirect(url_for('admin.list_uploads'))


@upload_extended_bp.route('/uploads/bulk-delete', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def bulk_delete_uploads():
    """Delete multiple uploads at once."""
    from app.models import Upload
    from app.services.file_upload import delete_upload_file
    
    upload_ids = request.form.getlist('upload_ids')
    deleted = 0
    for uid in upload_ids:
        upload = db.session.get(Upload, int(uid))
        if upload:
            try:
                delete_upload_file(upload)
                deleted += 1
            except Exception:
                pass
    
    flash(f'Deleted {deleted} upload(s)')
    return redirect(url_for('admin.list_uploads'))


@upload_extended_bp.route('/uploads/cleanup')
@admin_required
def cleanup_uploads():
    """Remove uploads not referenced by any module."""
    from app.models import Upload, Module, Route, Script
    
    # Get all uploaded filenames referenced in routes/scripts
    referenced = set()
    for route in db.session.query(Route).all():
        if route.script and route.script.source_code:
            # Simple check - look for /uploads/ references
            import re
            matches = re.findall(r'/uploads/([^"\')\s]+)', route.script.source_code)
            referenced.update(matches)
    
    # Find unreferenced uploads
    all_uploads = db.session.query(Upload).all()
    unreferenced = [u for u in all_uploads if u.filename not in referenced]
    
    deleted = 0
    for upload in unreferenced:
        try:
            from app.services.file_upload import delete_upload_file
            delete_upload_file(upload)
            deleted += 1
        except Exception:
            pass
    
    flash(f'Cleaned up {deleted} unreferenced upload(s)')
    return redirect(url_for('admin.list_uploads'))


@upload_extended_bp.route('/uploads/stats')
@admin_required
def upload_stats():
    """View upload statistics."""
    from app.models import Upload
    
    total_uploads = db.session.query(Upload).count()
    total_size = db.session.execute(db.select(db.func.sum(Upload.size))).scalar() or 0
    
    # Group by MIME type
    mime_stats = db.session.query(Upload.mime_type, db.func.count(Upload.id), db.func.sum(Upload.size)).group_by(Upload.mime_type).all()
    
    return render_admin('Upload Statistics', '''
<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
  <div class="dash-card">
    <h3>Overview</h3>
    <ul style="margin:0;padding-left:1.5rem;line-height:1.8;">
      <li><strong>Total Uploads:</strong> {{ total_uploads }}</li>
      <li><strong>Total Size:</strong> {{ '%.2f MB'|format(total_size / 1048576) }}</li>
    </ul>
  </div>
  
  <div class="dash-card">
    <h3>By Type</h3>
    {% if mime_stats %}
    <table style="width:100%;">
    <thead><tr><th>Type</th><th>Count</th><th>Size</th></tr></thead>
    <tbody>
    {% for mime, count, size in mime_stats %}
    <tr>
      <td>{{ mime }}</td>
      <td>{{ count }}</td>
      <td>{{ '%.2f KB'|format(size / 1024) }}</td>
    </tr>
    {% endfor %}
    </tbody></table>
    {% else %}
    <p style="color:#888;">No uploads yet.</p>
    {% endif %}
  </div>
</div>
''', total_uploads=total_uploads, total_size=total_size, mime_stats=mime_stats)

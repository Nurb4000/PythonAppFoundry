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

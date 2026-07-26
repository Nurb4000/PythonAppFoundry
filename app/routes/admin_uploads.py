"""Admin routes for file uploads management."""
from flask import Blueprint, request, redirect, url_for, flash, abort
import os as _os
from flask import current_app as _current_app
import secrets as _secrets
from app.services.csrf import csrf_protect
from app.services.admin_utils import developer_or_admin_required, render_admin
from app import db
from app.models import Upload

uploads_bp = Blueprint('uploads', __name__)

@uploads_bp.route('/')
@developer_or_admin_required
def list_uploads():
    # Get search/filter parameters
    search = request.args.get('search', '')
    file_type = request.args.get('type', '')

    query = db.session.query(Upload).order_by(Upload.created_at.desc())

    # Apply filters
    if search:
        query = query.filter(
            db.or_(
                Upload.original_name.ilike(f'%{search}%'),
                Upload.filename.ilike(f'%{search}%')
            )
        )

    if file_type:
        if file_type == 'image':
            query = query.filter(Upload.mime_type.like('image/%'))
        elif file_type == 'document':
            query = query.filter(Upload.mime_type.in_(['application/pdf', 'application/msword',
                                                      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                                                      'text/plain']))
        elif file_type == 'video':
            query = query.filter(Upload.mime_type.like('video/%'))
        elif file_type == 'audio':
            query = query.filter(Upload.mime_type.like('audio/%'))

    uploads = query.all()

    # Calculate total size
    total_size = sum(u.size for u in uploads)

    return render_admin('File Manager', 'admin/uploads/list.html', uploads=uploads, total_size=total_size, search=search, file_type=file_type)

@uploads_bp.route('/upload', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def upload_file():
    if 'file' not in request.files:
        flash('No file')
        return redirect(url_for('admin.uploads.list_uploads'))
    f = request.files['file']
    if not f.filename:
        flash('No file selected')
        return redirect(url_for('admin.uploads.list_uploads'))

    try:
        from app.services.file_upload import upload_file as upload_service
        upload = upload_service(f)
        flash(f'Uploaded {upload.original_name}')
    except Exception as e:
        flash(f'Upload failed: {str(e)}', 'error')

    return redirect(url_for('admin.uploads.list_uploads'))

@uploads_bp.route('/<int:id>/delete', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def delete_upload(id):
    upload = db.session.get(Upload, id)
    if not upload:
        abort(404)

    try:
        from app.services.file_upload import delete_upload_file
        delete_upload_file(upload)
        flash(f'Deleted {upload.original_name}')
    except Exception as e:
        flash(f'Delete failed: {str(e)}', 'error')

    return redirect(url_for('admin.uploads.list_uploads'))

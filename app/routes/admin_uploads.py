"""Admin routes for file upload management."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import developer_or_admin_required
from app import db
from app.models import Upload

uploads_bp = Blueprint('uploads', __name__)


@uploads_bp.route('/uploads')
@developer_or_admin_required
def list_uploads():
    search = request.args.get('search', '')
    file_type = request.args.get('type', '')

    query = db.session.query(Upload).order_by(Upload.created_at.desc())

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
    total_size = sum(u.size for u in uploads)

    return render_admin('File Manager', '''
<div style="margin-bottom:1rem;display:flex;gap:1rem;align-items:center;flex-wrap:wrap;">
  <form method="POST" action="{{ url_for('admin.upload_file') }}" enctype="multipart/form-data" style="display:flex;gap:8px;align-items:center;flex:1;min-width:300px;">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <input type="file" name="file" required style="flex:1;">
    <button type="submit" style="padding:6px 16px;background:#007bff;color:#fff;border:none;border-radius:4px;cursor:pointer;">Upload</button>
  </form>
  <form method="GET" style="display:flex;gap:8px;align-items:center;">
    <input type="text" name="search" placeholder="Search files..." value="{{ search }}" style="padding:6px 12px;border:1px solid #ddd;border-radius:4px;">
    <select name="type" style="padding:6px 12px;border:1px solid #ddd;border-radius:4px;">
      <option value="">All Types</option>
      <option value="image" {% if file_type == 'image' %}selected{% endif %}>Images</option>
      <option value="document" {% if file_type == 'document' %}selected{% endif %}>Documents</option>
      <option value="video" {% if file_type == 'video' %}selected{% endif %}>Videos</option>
      <option value="audio" {% if file_type == 'audio' %}selected{% endif %}>Audio</option>
    </select>
    <button type="submit" style="padding:6px 12px;background:#6c757d;color:#fff;border:none;border-radius:4px;cursor:pointer;">Filter</button>
    {% if search or file_type %}
      <a href="{{ url_for('admin.list_uploads') }}" style="padding:6px 12px;color:#007bff;text-decoration:none;">Clear</a>
    {% endif %}
  </form>
</div>

<div style="margin-bottom:1rem;padding:0.75rem;background:#f8f9fa;border-radius:4px;font-size:0.9rem;color:#666;">
  Showing {{ uploads|length }} file(s), total size: {{ '%0.2f MB'|format(total_size / 1048576) }}
</div>

<table>
<thead><tr>
  <th>Preview</th>
  <th>Original Name</th>
  <th>Type</th>
  <th>Size</th>
  <th>Uploaded</th>
  <th>Actions</th>
</tr></thead>
<tbody>
{% for u in uploads %}
<tr>
  <td>
    {% if 'image' in u.mime_type %}
      <img src="/uploads/{{ u.filename }}" style="width:50px;height:50px;object-fit:cover;border-radius:4px;" alt="{{ u.original_name }}">
    {% elif 'pdf' in u.mime_type %}
      <span style="font-size:1.5rem;">📄</span>
    {% elif 'video' in u.mime_type %}
      <span style="font-size:1.5rem;">🎥</span>
    {% elif 'audio' in u.mime_type %}
      <span style="font-size:1.5rem;">🎵</span>
    {% else %}
      <span style="font-size:1.5rem;">📎</span>
    {% endif %}
  </td>
  <td>
    <strong>{{ u.original_name }}</strong><br>
    <code style="font-size:0.8em;color:#666;">{{ u.filename }}</code>
  </td>
  <td>{{ u.mime_type }}</td>
  <td>{{ '%0.1f KB'|format(u.size / 1024) }}</td>
  <td>{{ u.created_at|localtime }}</td>
  <td>
    <a href="/uploads/{{ u.filename }}" target="_blank" style="margin-right:0.5rem;">View</a>
    <a href="/uploads/{{ u.filename }}" download style="margin-right:0.5rem;">Download</a>
    <form method="POST" action="{{ url_for('admin.delete_upload', id=u.id) }}" style="display:inline" onsubmit="return confirm('Delete {{ u.original_name }}?')">
      <button type="submit" style="background:none;border:none;color:#c00;cursor:pointer;text-decoration:underline;padding:0;font:inherit;font-size:0.9em;">Delete</button>
    </form>
  </td>
</tr>
{% endfor %}
</tbody></table>
{% if not uploads %}<p style="color:#888;">No files uploaded yet.</p>{% endif %}''', uploads=uploads, total_size=total_size, search=search, file_type=file_type)


@uploads_bp.route('/uploads/upload', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def upload_file():
    if 'file' not in request.files:
        flash('No file')
        return redirect(url_for('admin.list_uploads'))
    f = request.files['file']
    if not f.filename:
        flash('No file selected')
        return redirect(url_for('admin.list_uploads'))

    try:
        from app.services.file_upload import upload_file as upload_service
        upload = upload_service(f)
        flash(f'Uploaded {upload.original_name}')
    except Exception as e:
        flash(f'Upload failed: {str(e)}', 'error')

    return redirect(url_for('admin.list_uploads'))


@uploads_bp.route('/uploads/<int:id>/delete', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def delete_upload(id):
    upload = db.session.get(Upload, id)
    if not upload:
        from flask import abort
        abort(404)

    try:
        from app.services.file_upload import delete_upload_file
        delete_upload_file(upload)
        flash(f'Deleted {upload.original_name}')
    except Exception as e:
        flash(f'Delete failed: {str(e)}', 'error')

    return redirect(url_for('admin.list_uploads'))

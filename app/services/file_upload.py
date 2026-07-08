import os
import secrets
import logging
from datetime import datetime, timezone
from flask import current_app
from app import db
from app.models import Upload

logger = logging.getLogger(__name__)


def upload_file(file_obj, original_name=None):
    """
    Handle file upload and create Upload record.
    
    Args:
        file_obj: Flask file object from request.files
        original_name: Optional override for the original filename
    
    Returns:
        Upload: The created Upload record
    
    Raises:
        ValueError: If no file is provided or filename is empty
    """
    if not file_obj:
        raise ValueError('No file provided')
    
    filename = original_name or file_obj.filename
    if not filename:
        raise ValueError('No filename provided')
    
    # Generate secure random filename to prevent path traversal
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    save_name = secrets.token_hex(12) + ('.' + ext if ext else '')
    
    # Get upload directory from app config or use default
    upload_dir = os.path.join(current_app.instance_path, 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save file to disk
    file_obj.save(os.path.join(upload_dir, save_name))
    
    # Get file size
    file_size = os.path.getsize(os.path.join(upload_dir, save_name))
    
    # Create database record
    upload = Upload(
        filename=save_name,
        original_name=filename,
        mime_type=file_obj.content_type or 'application/octet-stream',
        size=file_size,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(upload)
    db.session.commit()
    
    logger.info(f'File uploaded: {save_name} (original: {filename}, size: {file_size})')
    return upload


def get_upload_file_path(upload):
    """Get the full filesystem path for an Upload record."""
    upload_dir = os.path.join(current_app.instance_path, 'uploads')
    return os.path.join(upload_dir, upload.filename)


def delete_upload_file(upload):
    """Delete both the file from disk and the database record."""
    file_path = get_upload_file_path(upload)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    db.session.delete(upload)
    db.session.commit()
    
    logger.info(f'File deleted: {upload.original_name}')


def get_upload_url(upload):
    """Get the public URL for an Upload record."""
    return f'/uploads/{upload.filename}'

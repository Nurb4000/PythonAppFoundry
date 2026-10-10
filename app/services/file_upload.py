import os
import secrets
import logging
from datetime import datetime, timezone
from flask import current_app
from app import db
from app.models import Upload

logger = logging.getLogger(__name__)

# Allowed MIME types for uploads. Extend via ALLOWED_MIME_TYPES env var (comma-separated).
_DEFAULT_ALLOWED_MIMES = {
    # Images
    'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/svg+xml',
    # Documents
    'application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain', 'text/csv', 'text/html', 'text/xml',
    # Archives
    'application/zip', 'application/gzip', 'application/x-tar',
    # Data
    'application/json', 'application/xml',
    # Code
    'text/javascript', 'text/css', 'text/x-python',
}

# Extension-to-MIME mapping for cross-validation.
_EXT_TO_MIME = {
    '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif',
    '.webp': 'image/webp', '.svg': 'image/svg+xml', '.pdf': 'application/pdf',
    '.doc': 'application/msword', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xls': 'application/vnd.ms-excel', '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.txt': 'text/plain', '.csv': 'text/csv', '.html': 'text/html', '.htm': 'text/html',
    '.xml': 'application/xml', '.json': 'application/json',
    '.zip': 'application/zip', '.gz': 'application/gzip', '.tar': 'application/x-tar',
    '.js': 'text/javascript', '.css': 'text/css', '.py': 'text/x-python',
}


def _get_allowed_mimes():
    """Get allowed MIME types, merging defaults with env var override."""
    import os
    env_mimes = os.environ.get('ALLOWED_MIME_TYPES', '')
    allowed = set(_DEFAULT_ALLOWED_MIMES)
    if env_mimes:
        allowed.update(m.strip().lower() for m in env_mimes.split(',') if m.strip())
    return allowed


def _validate_mime_type(file_obj, filename):
    """Validate file MIME type against allowlist and cross-check extension.

    Args:
        file_obj: Flask file object from request.files
        filename: Original filename

    Returns:
        str: The validated MIME type

    Raises:
        ValueError: If MIME type is not allowed or mismatched with extension
    """
    claimed_mime = (file_obj.content_type or '').lower().split(';')[0].strip()
    ext = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    allowed = _get_allowed_mimes()

    # Cross-check: if extension is known, verify MIME matches
    if ext in _EXT_TO_MIME:
        expected_mime = _EXT_TO_MIME[ext]
        # If browser sent a MIME type, it should match the extension
        if claimed_mime and claimed_mime != expected_mime:
            logger.warning(
                f'MIME mismatch for "{filename}": claimed={claimed_mime}, expected={expected_mime}'
            )
        # Use the extension-derived MIME as the authoritative type
        claimed_mime = expected_mime

    if not claimed_mime:
        # No MIME from browser and unknown extension — reject
        raise ValueError(f'Unknown MIME type for file "{filename}" (extension: {ext or "none"})')

    if claimed_mime not in allowed:
        raise ValueError(
            f'MIME type "{claimed_mime}" not allowed for file "{filename}". '
            f'Allowed types: {", ".join(sorted(allowed))[:200]}…'
        )

    return claimed_mime


def _validate_file_size(file_obj, max_size=None):
    """Validate file size against configured limit.

    Args:
        file_obj: Flask file object from request.files
        max_size: Optional override for max size in bytes

    Raises:
        ValueError: If file exceeds the size limit
    """
    if max_size is None:
        max_size = current_app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)

    # Seek to end to get size, then seek back to start
    file_obj.seek(0, 2)
    size = file_obj.tell()
    file_obj.seek(0)

    if size > max_size:
        max_mb = max_size / (1024 * 1024)
        raise ValueError(f'File size ({size} bytes) exceeds limit of {max_mb:.1f} MB')


def upload_file(file_obj, original_name=None):
    """
    Handle file upload and create Upload record.

    Args:
        file_obj: Flask file object from request.files
        original_name: Optional override for the original filename

    Returns:
        Upload: The created Upload record

    Raises:
        ValueError: If no file is provided, filename is empty, MIME type is
                    not allowed, or file exceeds size limit
    """
    if not file_obj:
        raise ValueError('No file provided')

    filename = original_name or file_obj.filename
    if not filename:
        raise ValueError('No filename provided')

    # Validate file size before saving
    _validate_file_size(file_obj)

    # Validate MIME type (allowlist + extension cross-check)
    mime_type = _validate_mime_type(file_obj, filename)

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
        mime_type=mime_type,
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

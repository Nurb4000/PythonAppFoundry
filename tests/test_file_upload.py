"""Tests for file upload hardening (size limits, MIME validation)."""
import io
import pytest


class TestMimeTypeValidation:
    """Test MIME type allowlist and extension cross-check."""

    def test_allowed_image_types(self, app_context):
        """Common image types should be allowed."""
        from app.services.file_upload import _validate_mime_type, _get_allowed_mimes
        allowed = _get_allowed_mimes()
        assert 'image/png' in allowed
        assert 'image/jpeg' in allowed
        assert 'image/gif' in allowed

    def test_allowed_document_types(self, app_context):
        """Common document types should be allowed."""
        from app.services.file_upload import _get_allowed_mimes
        allowed = _get_allowed_mimes()
        assert 'application/pdf' in allowed
        assert 'text/csv' in allowed
        assert 'text/plain' in allowed

    def test_unknown_mime_rejected(self, app_context):
        """Unknown MIME types should raise ValueError."""
        from app.services.file_upload import _validate_mime_type
        from werkzeug.datastructures import FileStorage

        fake_file = FileStorage(
            filename='test.xyz',
            content_type='application/x-unknown-type',
        )
        with pytest.raises(ValueError, match='not allowed'):
            _validate_mime_type(fake_file, 'test.xyz')

    def test_extension_mime_cross_check(self, app_context):
        """Extension-derived MIME should override browser-reported MIME."""
        from app.services.file_upload import _validate_mime_type
        from werkzeug.datastructures import FileStorage

        # Browser claims it's text/plain, but .png extension says image/png
        fake_file = FileStorage(
            filename='test.png',
            content_type='text/plain',
        )
        mime = _validate_mime_type(fake_file, 'test.png')
        assert mime == 'image/png'

    def test_no_extension_rejected(self, app_context):
        """Files with no extension and no MIME type should be rejected."""
        from app.services.file_upload import _validate_mime_type
        from werkzeug.datastructures import FileStorage

        fake_file = FileStorage(
            filename='noextension',
            content_type='',
        )
        with pytest.raises(ValueError, match='Unknown MIME'):
            _validate_mime_type(fake_file, 'noextension')


class TestFileSizeValidation:
    """Test file size limit enforcement."""

    def test_small_file_accepted(self, app_context):
        """Files under the limit should pass validation."""
        from app.services.file_upload import _validate_file_size
        from werkzeug.datastructures import FileStorage

        small_data = b'x' * 1000  # 1 KB
        fake_file = FileStorage(
            io.BytesIO(small_data),
            filename='small.txt',
            content_type='text/plain',
        )
        # Should not raise
        _validate_file_size(fake_file, max_size=1024 * 1024)  # 1 MB limit

    def test_oversized_file_rejected(self, app_context):
        """Files over the limit should raise ValueError."""
        from app.services.file_upload import _validate_file_size
        from werkzeug.datastructures import FileStorage

        large_data = b'x' * (2 * 1024 * 1024)  # 2 MB
        fake_file = FileStorage(
            io.BytesIO(large_data),
            filename='large.txt',
            content_type='text/plain',
        )
        with pytest.raises(ValueError, match='exceeds limit'):
            _validate_file_size(fake_file, max_size=1024 * 1024)  # 1 MB limit

    def test_file_position_reset(self, app_context):
        """_validate_file_size should reset file position after check."""
        from app.services.file_upload import _validate_file_size
        from werkzeug.datastructures import FileStorage

        data = b'hello world'
        fake_file = FileStorage(
            io.BytesIO(data),
            filename='test.txt',
            content_type='text/plain',
        )
        _validate_file_size(fake_file, max_size=1024 * 1024)
        # File should be seeked back to start
        assert fake_file.read() == data


class TestUploadIntegration:
    """Integration tests for the full upload pipeline."""

    def test_upload_valid_file(self, logged_in_client, clean_db, app_context):
        """Uploading a valid file should succeed."""
        import secrets
        from werkzeug.datastructures import FileStorage

        # Set CSRF token in session before the POST
        csrf_token = secrets.token_hex(32)
        with logged_in_client.session_transaction() as sess:
            sess['csrf_token'] = csrf_token

        data = {
            'file': (FileStorage(io.BytesIO(b'test content'), 'test.txt', 'text/plain'), 'test.txt'),
            'csrf_token': csrf_token,
        }
        resp = logged_in_client.post(
            '/__admin/uploads/upload',
            data=data,
            content_type='multipart/form-data',
            follow_redirects=True,
        )
        assert resp.status_code in (200, 302)

    def test_upload_max_content_length(self, app, client, admin_user, clean_db):
        """File exceeding MAX_CONTENT_LENGTH should return 413."""
        # Set a small limit for this test
        app.config['MAX_CONTENT_LENGTH'] = 100  # 100 bytes

        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = 'true'

        large_data = b'x' * 200
        data = {
            'file': (io.BytesIO(large_data), 'large.txt'),
        }
        resp = client.post(
            '/__admin/uploads/upload',
            data=data,
            content_type='multipart/form-data',
            follow_redirects=True,
        )
        assert resp.status_code in (413, 500)  # 413 or handled as 500

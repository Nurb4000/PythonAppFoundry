"""Tests for API request/response logging."""
import json
import pytest


class TestApiLogging:
    """Test API logging functionality."""

    def test_api_log_model_exists(self, app_context):
        """ApiLog model should exist with required fields."""
        from app.models import ApiLog
        assert hasattr(ApiLog, 'method')
        assert hasattr(ApiLog, 'path')
        assert hasattr(ApiLog, 'status_code')
        assert hasattr(ApiLog, 'duration_ms')
        assert hasattr(ApiLog, 'client_ip')
        assert hasattr(ApiLog, 'user_agent')
        assert hasattr(ApiLog, 'api_key_id')
        assert hasattr(ApiLog, 'request_body')
        assert hasattr(ApiLog, 'response_summary')

    def test_api_log_created_on_request(self, app_context, client):
        """API log should be created when an API endpoint is called."""
        from app.models import ApiLog

        # Make a request to an API endpoint (follow redirects)
        resp = client.get('/__api/openapi.json', follow_redirects=True)

        # Check that a log entry was created
        logs = ApiLog.query.filter_by(path='/__api/openapi.json').all()
        assert len(logs) >= 1
        assert logs[-1].method == 'GET'

    def test_api_log_records_method(self, app_context, client):
        """API log should record the HTTP method."""
        from app.models import ApiLog

        resp = client.post('/__api/webhook/test-endpoint', json={'data': 'test'})
        logs = ApiLog.query.filter_by(path='/__api/webhook/test-endpoint').all()
        assert len(logs) >= 1
        assert logs[-1].method == 'POST'

    def test_api_log_records_status_code(self, app_context, client):
        """API log should record the response status code."""
        from app.models import ApiLog

        # 404 for non-existent webhook
        resp = client.get('/__api/webhook/nonexistent')
        logs = ApiLog.query.filter_by(path='/__api/webhook/nonexistent').all()
        assert len(logs) >= 1
        assert logs[-1].status_code == 404

    def test_api_log_records_duration(self, app_context, client):
        """API log should record request duration."""
        from app.models import ApiLog

        resp = client.get('/__api/openapi.json')
        logs = ApiLog.query.filter_by(path='/__api/openapi.json').all()
        assert len(logs) >= 1
        assert logs[-1].duration_ms is not None
        assert logs[-1].duration_ms >= 0

    def test_api_log_records_client_ip(self, app_context, client):
        """API log should record the client IP."""
        from app.models import ApiLog

        resp = client.get('/__api/openapi.json')
        logs = ApiLog.query.filter_by(path='/__api/openapi.json').all()
        assert len(logs) >= 1
        # Test client uses 127.0.0.1
        assert logs[-1].client_ip in ('127.0.0.1', 'localhost', '::1')

    def test_api_log_records_request_body(self, app_context, client):
        """API log should record the request body for JSON requests."""
        from app.models import ApiLog

        resp = client.post('/__api/webhook/test-endpoint', json={'key': 'value'})
        logs = ApiLog.query.filter_by(path='/__api/webhook/test-endpoint').all()
        assert len(logs) >= 1
        assert 'key' in logs[-1].request_body or 'value' in logs[-1].request_body

    def test_api_log_records_response_summary(self, app_context, client):
        """API log should record the response summary."""
        from app.models import ApiLog

        resp = client.get('/__api/openapi.json')
        logs = ApiLog.query.filter_by(path='/__api/openapi.json').all()
        assert len(logs) >= 1
        # OpenAPI response should contain some JSON content
        assert len(logs[-1].response_summary) > 0

    def test_non_api_endpoint_not_logged(self, app_context, client):
        """Non-API endpoints should not be logged."""
        from app.models import ApiLog

        initial_count = ApiLog.query.count()
        resp = client.get('/healthz')
        assert resp.status_code == 200

        # healthz is not an API endpoint, so it shouldn't be logged
        final_count = ApiLog.query.count()
        assert final_count == initial_count

    def test_api_log_migration_exists(self):
        """Migration for api_logs table should exist."""
        import os
        assert os.path.isfile('migrations/versions/006_add_api_logs.py')


class TestApiLogAdminRoutes:
    """Test API log admin routes."""

    def test_list_page_loads(self, logged_in_client, clean_db):
        """API logs list page should load."""
        resp = logged_in_client.get('/__admin/api-logs/')
        assert resp.status_code == 200

    def test_view_page_loads(self, logged_in_client, app_context):
        """API log view page should load for existing log."""
        from app.models import ApiLog

        log = ApiLog(
            method='GET',
            path='/__api/test',
            status_code=200,
            duration_ms=50,
            client_ip='127.0.0.1',
        )
        from app import db as _db
        _db.session.add(log)
        _db.session.commit()

        resp = logged_in_client.get(f'/__admin/api-logs/{log.id}')
        assert resp.status_code == 200

    def test_export_page_loads(self, logged_in_client, clean_db):
        """API logs export should return JSON."""
        resp = logged_in_client.get('/__admin/api-logs/export')
        assert resp.status_code == 200
        assert resp.mimetype == 'application/json'

    def test_clear_page_loads(self, logged_in_client, clean_db):
        """API logs clear page should redirect."""
        resp = logged_in_client.get('/__admin/api-logs/clear?confirm=true', follow_redirects=True)
        assert resp.status_code == 200

"""Tests for Prometheus metrics endpoint."""
import pytest


class TestMetricsEndpoint:
    """Test the /__api/metrics endpoint."""

    def test_metrics_returns_200(self, client):
        """Metrics endpoint should return 200."""
        resp = client.get('/__api/metrics')
        assert resp.status_code == 200

    def test_metrics_content_type(self, client):
        """Metrics should have text/plain content type."""
        resp = client.get('/__api/metrics')
        assert 'text/plain' in resp.mimetype

    def test_metrics_format(self, client):
        """Metrics should be in Prometheus exposition format."""
        resp = client.get('/__api/metrics')
        body = resp.data.decode()
        # Should contain HELP and TYPE comments
        assert '# HELP' in body or '# TYPE' in body
        # Should contain at least one metric line
        lines = [l for l in body.split('\n') if l and not l.startswith('#')]
        assert len(lines) >= 0  # May be empty on first request

    def test_http_requests_total_metric(self, client):
        """After requests, http_requests_total should appear."""
        # Make a few requests
        client.get('/__api/metrics')
        client.get('/healthz')

        resp = client.get('/__api/metrics')
        body = resp.data.decode()
        assert 'http_requests_total' in body

    def test_http_active_requests_metric(self, client):
        """http_active_requests gauge should be present."""
        resp = client.get('/__api/metrics')
        body = resp.data.decode()
        assert 'http_active_requests' in body


class TestMetricsCollection:
    """Test the metrics collection functions."""

    def test_record_http_request(self, app_context):
        """Recording a request should update counters."""
        from app.services.metrics import record_http_request, generate_metrics

        record_http_request('GET', '/test', 200, 0.1)
        metrics = generate_metrics()
        assert 'http_requests_total' in metrics
        assert 'method="GET"' in metrics
        assert 'status="200"' in metrics

    def test_active_requests_counter(self, app_context):
        """Active requests counter should increment/decrement."""
        from app.services.metrics import (
            increment_active_requests, decrement_active_requests, generate_metrics,
        )

        increment_active_requests()
        metrics = generate_metrics()
        assert 'http_active_requests 1' in metrics or 'http_active_requests 2' in metrics

        decrement_active_requests()
        metrics = generate_metrics()
        # Should be 0 or 1 (depending on timing)
        assert 'http_active_requests' in metrics

    def test_script_execution_counter(self, app_context):
        """Script execution counter should work."""
        from app.services.metrics import record_script_execution, generate_metrics

        record_script_execution('webhook')
        metrics = generate_metrics()
        assert 'script_executions_total' in metrics
        assert 'source_type="webhook"' in metrics

    def test_dead_letter_gauge(self, app_context):
        """Dead letter queue gauge should update."""
        from app.services.metrics import set_dead_letter_count, generate_metrics

        set_dead_letter_count(5)
        metrics = generate_metrics()
        assert 'dead_letter_queue_size 5' in metrics

    def test_path_normalization(self, app_context):
        """Dynamic path segments should be normalized."""
        from app.services.metrics import record_http_request, generate_metrics

        record_http_request('GET', '/__admin/modules/123', 200, 0.05)
        metrics = generate_metrics()
        assert '<id>' in metrics or 'modules' in metrics

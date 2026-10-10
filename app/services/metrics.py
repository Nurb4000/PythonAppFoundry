"""Prometheus-compatible metrics endpoint for PythonAppFoundry.

Exposes metrics at ``/__api/metrics`` in the Prometheus text exposition format.
Metrics are collected via Flask ``before_request`` / ``after_request`` hooks and
periodic DB queries.  No external dependencies required.
"""
import logging
import time
from collections import defaultdict
from threading import Lock

logger = logging.getLogger(__name__)

# ── In-memory metric storage (thread-safe) ────────────────────────────────────
_lock = Lock()

# HTTP request counters: {method: {status_code: count}}
_http_requests_total = defaultdict(lambda: defaultdict(int))
# HTTP request durations (seconds): list of recent values per endpoint
_http_request_duration = defaultdict(list)
# Gauge: current active requests
_active_requests = {'count': 0}
# Counter: total script executions by source_type
_script_executions_total = defaultdict(int)
# Counter: dead letter queue entries
_dead_letter_total = {'count': 0}


def _sanitize_label(value: str) -> str:
    """Escape double quotes and backslashes in label values."""
    return value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def record_http_request(method: str, path: str, status_code: int, duration: float):
    """Record an HTTP request for metrics collection."""
    with _lock:
        _http_requests_total[method][str(status_code)] += 1
        # Keep last 1000 durations per endpoint to bound memory
        durations = _http_request_duration[path]
        durations.append(duration)
        if len(durations) > 1000:
            durations.pop(0)


def increment_active_requests():
    """Increment the active request counter (called in before_request)."""
    with _lock:
        _active_requests['count'] += 1


def decrement_active_requests():
    """Decrement the active request counter (called in after_request)."""
    with _lock:
        _active_requests['count'] = max(0, _active_requests['count'] - 1)


def record_script_execution(source_type: str):
    """Record a script execution for metrics."""
    with _lock:
        _script_executions_total[source_type] += 1


def set_dead_letter_count(count: int):
    """Set the current dead letter queue count."""
    with _lock:
        _dead_letter_total['count'] = count


def generate_metrics() -> str:
    """Generate metrics in Prometheus text exposition format.

    Returns a string suitable for the ``/metrics`` endpoint response body.
    """
    lines = []
    timestamp = int(time.time())

    # ── HTTP request total (counter) ────────────────────────────────────────
    with _lock:
        for method, statuses in _http_requests_total.items():
            for status, count in statuses.items():
                lines.append(
                    f'# HELP http_requests_total Total HTTP requests by method and status.'
                    f'\\n# TYPE http_requests_total counter'
                )
                lines.append(
                    f'http_requests_total{{method="{_sanitize_label(method)}",'
                    f'status="{status}"}} {count} {timestamp}'
                )

    # ── HTTP request duration (histogram approximation) ─────────────────────
    with _lock:
        for path, durations in _http_request_duration.items():
            if not durations:
                continue
            avg = sum(durations) / len(durations)
            p50 = sorted(durations)[len(durations) // 2]
            p99 = sorted(durations)[int(len(durations) * 0.99)]
            lines.append(
                f'# HELP http_request_duration_seconds HTTP request duration.'
                f'\\n# TYPE http_request_duration_seconds gauge'
            )
            safe_path = _sanitize_label(path)
            lines.append(
                f'http_request_duration_seconds{{endpoint="{safe_path}",quantile="0.50"}} '
                f'{p50:.6f} {timestamp}'
            )
            lines.append(
                f'http_request_duration_seconds{{endpoint="{safe_path}",quantile="0.99"}} '
                f'{p99:.6f} {timestamp}'
            )
            lines.append(
                f'http_request_duration_seconds{{endpoint="{safe_path}",quantile="avg"}} '
                f'{avg:.6f} {timestamp}'
            )

    # ── Active requests (gauge) ─────────────────────────────────────────────
    with _lock:
        count = _active_requests['count']
    lines.append(
        f'# HELP http_active_requests Currently active HTTP requests.'
        f'\\n# TYPE http_active_requests gauge'
    )
    lines.append(f'http_active_requests {count} {timestamp}')

    # ── Script executions (counter) ─────────────────────────────────────────
    with _lock:
        for source_type, count in _script_executions_total.items():
            lines.append(
                f'# HELP script_executions_total Total script executions by type.'
                f'\\n# TYPE script_executions_total counter'
            )
            lines.append(
                f'script_executions_total{{source_type="{_sanitize_label(source_type)}"}} '
                f'{count} {timestamp}'
            )

    # ── Dead letter queue (gauge) ───────────────────────────────────────────
    with _lock:
        dlq_count = _dead_letter_total['count']
    lines.append(
        f'# HELP dead_letter_queue_size Current dead letter queue size.'
        f'\\n# TYPE dead_letter_queue_size gauge'
    )
    lines.append(f'dead_letter_queue_size {dlq_count} {timestamp}')

    return '\n'.join(lines) + '\n'


def init_metrics(app):
    """Register metrics collection hooks on the Flask app."""
    from flask import request, g

    @app.before_request
    def _metrics_before():
        increment_active_requests()
        g._metrics_start = time.time()

    @app.after_request
    def _metrics_after(response):
        start = getattr(g, '_metrics_start', time.time())
        duration = time.time() - start
        path = request.path
        # Normalize dynamic segments (e.g., /__admin/modules/123 → /__admin/modules/<id>)
        parts = path.split('/')
        normalized = []
        for part in parts:
            if part.isdigit():
                normalized.append('<id>')
            else:
                normalized.append(part)
        normalized_path = '/'.join(normalized) or '/'

        record_http_request(request.method, normalized_path, response.status_code, duration)
        decrement_active_requests()
        return response

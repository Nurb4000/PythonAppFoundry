"""API request/response logging service.

Logs every API call with method, path, status code, duration, client IP,
user agent, and associated API key (if used).  Used for monitoring,
debugging, and compliance auditing.
"""
import logging
import time

from flask import request, g
from app import db
from app.models import ApiLog

logger = logging.getLogger(__name__)


def log_api_request(response):
    """Flask after_request handler that logs API calls.

    Records method, path, status code, duration, client IP, user agent,
    and associated API key (if used) to the ApiLog table.

    Args:
        response: The Flask response object.

    Returns:
        The unchanged response object.
    """
    # Only log requests to __api endpoints
    if not request.path.startswith('/__api'):
        return response

    # Calculate duration
    start_time = getattr(g, '_api_start_time', time.time())
    duration_ms = int((time.time() - start_time) * 1000)

    # Get API key ID from the request context (set by validate_api_key)
    api_key_id = getattr(g, '_api_key_id', None)

    # Extract request body (truncate to 4KB)
    request_body = ''
    if request.is_json:
        try:
            data = request.get_json(silent=True)
            request_body = str(data)[:4000] if data else ''
        except Exception:
            pass
    elif request.data:
        request_body = request.data.decode('utf-8', errors='replace')[:4000]

    # Extract response summary (truncate to 4KB)
    response_summary = ''
    try:
        if response.is_json:
            data = response.get_json(silent=True)
            response_summary = str(data)[:4000] if data else ''
        elif response.data:
            response_summary = response.data.decode('utf-8', errors='replace')[:4000]
    except Exception:
        pass

    # Create log entry
    log_entry = ApiLog(
        method=request.method,
        path=request.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
        client_ip=request.remote_addr or '',
        user_agent=(request.headers.get('User-Agent', '')[:500]),
        api_key_id=api_key_id,
        request_body=request_body,
        response_summary=response_summary,
    )

    try:
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        logger.debug(f'API log entry failed: {e}')
        try:
            db.session.rollback()
        except Exception:
            pass

    return response


def init_api_logging(app):
    """Register API logging hooks on the Flask app.

    Args:
        app: The Flask application instance.
    """
    @app.before_request
    def _api_log_before():
        if request.path.startswith('/__api'):
            g._api_start_time = time.time()

    @app.after_request
    def _api_log_after(response):
        return log_api_request(response)

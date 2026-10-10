"""Gunicorn configuration for PythonAppFoundry.

Usage::

    gunicorn run:app -c gunicorn.conf.py

Or with the number of workers auto-detected from CPU count::

    gunicorn run:app -c gunicorn.conf.py --workers 0
"""
import math
import multiprocessing
import os
import signal
import sys

# ── Server socket ────────────────────────────────────────────────────────────
bind = f'0.0.0.0:{os.environ.get("APP_PORT", "5000")}'
backlog = 2048

# ── Worker processes ─────────────────────────────────────────────────────────
# Auto-scale: (2 × CPUs) + 1, capped at 16.  Override with --workers N.
_cpu_count = multiprocessing.cpu_count()
workers = min(max(2, (2 * _cpu_count) + 1), 16)
worker_class = 'sync'  # Flask is synchronous; switch to 'gevent' for async
worker_connections = 1000
threads = max(2, _cpu_count)  # Threaded workers for better concurrency
timeout = 120  # Script execution timeout (must exceed script_timeout setting)
graceful_timeout = 30
keepalive = 2

# ── Process naming & logging ─────────────────────────────────────────────────
proc_name = 'PythonAppFoundry'
accesslog = '-'  # Stdout
errorlog = '-'   # Stderr
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')
access_log_format = (
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sm'
)

# ── Worker tmp dir (for preload) ─────────────────────────────────────────────
tmp_upload_dir = '/tmp/paf-gunicorn'

# ── Preload app (shared memory, faster startup) ──────────────────────────────
preload_app = True

# ── Max requests per worker (memory leak mitigation) ─────────────────────────
max_requests = 1000
max_requests_jitter = 50  # Stagger restarts


# ── Graceful shutdown hook ───────────────────────────────────────────────────
def on_exit(server):
    """Called when the master process exits. Shut down AppState resources."""
    from app import create_app
    app = create_app()
    try:
        from app.services.app_state import shutdown_state
        shutdown_state(app)
    except Exception as e:
        logger = server.log.error_log
        logger.warning(f'AppState shutdown hook: {e}')


def post_fork(server, worker):
    """Called after a worker forks. Initialize per-worker AppState."""
    from app import create_app
    app = create_app()
    server.log.info(f'Worker {worker.pid} initialized AppState')


def pre_exec(server):
    """Called before the master process is replaced (e.g., --reload)."""
    global tmp_upload_dir
    os.makedirs(tmp_upload_dir, exist_ok=True)

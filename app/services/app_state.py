"""Centralized application state for multi-process deployments.

Stores global state (scheduler, thread pool, credential key, tenants) in
Flask's app context so each Gunicorn worker maintains its own isolated copy.
Provides a backwards-compatible API for the existing service modules.
"""
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class AppState:
    """Holds per-process global state for the application.

    In a single-process deployment this is a singleton.  Under Gunicorn each
    worker gets its own instance stored in ``app.config['_app_state']``.
    """

    def __init__(self):
        self._lock = threading.Lock()
        # Scheduler
        self.scheduler = None
        self.scheduler_app = None
        self.last_run_guard = {}
        # Async executor
        self.pool = None
        self.max_workers = 4
        # Credential store
        self.credential_key = None
        # Tenants
        self.tenants = {}
        self.default_tenant = None

    def get_or_create_pool(self, desired_workers=None):
        """Get or create the thread pool, recreating if worker count changes."""
        if desired_workers is None:
            from app.models import Setting
            try:
                desired_workers = int(Setting.get('async_workers', '4'))
            except (ValueError, TypeError):
                desired_workers = 4

        with self._lock:
            if desired_workers != self.max_workers or self.pool is None:
                self.max_workers = desired_workers
                if self.pool is not None:
                    self.pool.shutdown(wait=False, cancel_futures=True)
                self.pool = ThreadPoolExecutor(
                    max_workers=self.max_workers,
                    thread_name_prefix='paf-async',
                )
                logger.info(f'Thread pool (re)created with {self.max_workers} workers')
        return self.pool

    def shutdown(self):
        """Gracefully shut down all managed resources."""
        if self.pool is not None:
            logger.info('Shutting down async executor pool')
            self.pool.shutdown(wait=True, cancel_futures=True)
            self.pool = None
        if self.scheduler is not None:
            logger.info('Shutting down scheduler')
            try:
                self.scheduler.shutdown(wait=True)
            except Exception as e:
                logger.warning(f'Scheduler shutdown error: {e}')
            self.scheduler = None


def get_state(app=None):
    """Retrieve the AppState for the current app context.

    Parameters
    ----------
    app : Flask, optional
        Explicit app object.  If *None*, uses ``flask.current_app``.

    Returns
    -------
    AppState
    """
    if app is None:
        from flask import current_app as _current_app
        app = _current_app._get_current_object()

    state = app.config.get('_app_state')
    if state is None:
        state = AppState()
        app.config['_app_state'] = state
    return state


def init_state(app):
    """Ensure the AppState exists on the given Flask app.

    Called during app factory initialisation.
    """
    if '_app_state' not in app.config:
        app.config['_app_state'] = AppState()
    return app.config['_app_state']


def shutdown_state(app):
    """Shut down managed resources (called on SIGTERM / worker exit)."""
    state = app.config.get('_app_state')
    if state:
        state.shutdown()

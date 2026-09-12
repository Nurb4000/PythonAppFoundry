"""Async script execution via ThreadPoolExecutor.

Provides background script execution for webhooks and scheduled tasks,
with status tracking via the ScriptExecution model.
"""
import faulthandler
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from flask import current_app
from app import db
from app.models import Script, ScriptExecution, Setting
from app.services.script_runner import execute_script

logger = logging.getLogger(__name__)

_pool = None
_max_workers = 4


def _get_script_timeout_seconds():
    """Return the configured script timeout in seconds (>= 0; 0 = unlimited)."""
    try:
        val = int(Setting.get('script_timeout', '30'))
    except (ValueError, TypeError):
        val = 30
    return val if val > 0 else 0


def _get_pool():
    """Get or create the thread pool. Recreated if worker count changes."""
    global _pool, _max_workers
    desired = int(Setting.get('async_workers', '4'))
    if desired != _max_workers or _pool is None:
        _max_workers = desired
        if _pool is not None:
            _pool.shutdown(wait=False, cancel_futures=True)
        _pool = ThreadPoolExecutor(max_workers=_max_workers, thread_name_prefix='paf-async')
    return _pool


def submit_script(script, source_type='webhook', source_name=None,
                  extra_globals=None, correlation_id=None):
    """Submit a script for background execution.

    Returns the ScriptExecution.id for status polling.
    """
    execution = ScriptExecution(
        source_type=source_type,
        source_name=source_name or script.name,
        script_name=script.name,
        module_id=script.module_id,
        correlation_id=correlation_id,
        status='queued',
    )
    db.session.add(execution)
    db.session.commit()

    exec_id = execution.id
    # Capture the app object at submit time so background threads can use it
    app = current_app._get_current_object()
    pool = _get_pool()
    pool.submit(_run_script, app, exec_id, script, extra_globals or {})

    logger.info(f'Queued async execution {exec_id}: {source_type}:{source_name or script.name}')
    return exec_id


def _run_script(app, execution_id, script, extra_globals):
    """Background thread: execute script and update status."""
    with app.app_context():
        execution = db.session.get(ScriptExecution, execution_id)
        if not execution:
            return

        # Async scripts run on a worker thread, where SIGALRM timeouts do not
        # fire. Start a watchdog that logs the running script's traceback once
        # it exceeds the configured deadline. CPython cannot forcibly kill a
        # thread, so this provides timeout *visibility* (ops can see the hang in
        # logs / restart) rather than reclaiming the worker — combined with the
        # bounded, configurable pool this prevents a single hung script from
        # silently starving the executor forever.
        timeout = _get_script_timeout_seconds()
        watchdog_done = threading.Event()
        watchdog_thread = None
        if timeout:
            def _watchdog():
                time.sleep(timeout)
                if not watchdog_done.is_set():
                    logger.warning(
                        'Async execution %s exceeded %ds timeout; dumping traceback '
                        '(restart or scale async_workers to recover the worker pool)',
                        execution_id, timeout,
                    )
                    faulthandler.dump_traceback()
            watchdog_thread = threading.Thread(target=_watchdog, name=f'paf-watchdog-{execution_id}', daemon=True)
            watchdog_thread.start()

        execution.status = 'running'
        execution.started_at = datetime.utcnow()
        db.session.commit()

        try:
            result = execute_script(script, extra_globals=extra_globals)
            execution.status = 'success'
            if isinstance(result, tuple):
                execution.result_summary = str(result[0])[:4000]
            else:
                execution.result_summary = str(result)[:4000] if result else ''
        except Exception as e:
            execution.status = 'error'
            execution.error_message = str(e)[:4000]
        finally:
            watchdog_done.set()
            if watchdog_thread is not None:
                watchdog_thread.join(timeout=1)
            execution.completed_at = datetime.utcnow()
            if execution.started_at:
                execution.duration_ms = int(
                    (execution.completed_at - execution.started_at).total_seconds() * 1000
                )
            db.session.commit()

        logger.info(f'Async execution {execution_id} completed: {execution.status}')


def submit_import(xml_str, update_existing=False, module_id=None, version_comment='',
                  source='upload', created_by_user_id=None):
    """Queue a module import to run on the background thread pool.

    Large XML imports can take long enough to risk timing out the HTTP request
    that triggered them. This offloads the work so the caller can redirect to a
    status page and poll for completion instead of blocking. Returns the
    ImportJob.id.
    """
    from app.models import ImportJob
    job = ImportJob(
        source=source,
        status='queued',
        # update_existing only makes sense when we have a concrete module to
        # update; normalise so a bare new-import stays a new-import.
        update_existing=bool(update_existing and module_id is not None),
        version_comment=(version_comment or ''),
        created_by_user_id=created_by_user_id,
        result_summary='Queued for import.',
    )
    if module_id is not None:
        job.module_id = module_id
    db.session.add(job)
    db.session.commit()

    job_id = job.id
    # Capture the app object so the background thread can push its own context.
    app = current_app._get_current_object()
    _get_pool().submit(_run_import, app, job_id, xml_str, update_existing,
                       module_id, version_comment, source)
    logger.info(f'Queued async import {job_id} (source={source})')
    return job_id


def _run_import(app, job_id, xml_str, update_existing, module_id, version_comment, source):
    """Background worker: run a queued module import and record the result."""
    from app.models import ImportJob
    from app.services.bundle import import_module
    with app.app_context():
        job = db.session.get(ImportJob, job_id)
        if job is None:
            return
        try:
            m = import_module(xml_str, update_existing=update_existing, module_id=module_id)
            job.status = 'completed'
            job.module_id = m.id
            summary = f'Imported "{m.name}" (module #{m.id})'
            # Replicate the admin "create a version snapshot on update" behaviour,
            # but call create_version directly (current_user is unavailable in a
            # worker thread).
            if update_existing and module_id and version_comment:
                try:
                    from app.services.versioning import create_version
                    create_version(module_id, comment=version_comment, user_id=job.created_by_user_id)
                    summary += '; version snapshot created'
                except Exception as ve:
                    summary += f'; version skip: {ve}'
            job.result_summary = summary
        except Exception as e:
            job.status = 'failed'
            job.result_summary = str(e)[:4000]
            logger.error(f'Async import {job_id} failed: {e}')
        finally:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()


def get_import_job(job_id):
    """Return an ImportJob ORM object (or None)."""
    from app.models import ImportJob
    return db.session.get(ImportJob, job_id)


def get_status(execution_id):
    """Get execution status as a dict."""
    db.session.expire_all()
    execution = db.session.get(ScriptExecution, execution_id)
    if not execution:
        return None
    return {
        'id': execution.id,
        'status': execution.status,
        'source_type': execution.source_type,
        'source_name': execution.source_name,
        'script_name': execution.script_name,
        'module_id': execution.module_id,
        'correlation_id': execution.correlation_id,
        'queued_at': execution.created_at.isoformat() if execution.created_at else None,
        'started_at': execution.started_at.isoformat() if execution.started_at else None,
        'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
        'duration_ms': execution.duration_ms,
        'result_summary': execution.result_summary or None,
        'error_message': execution.error_message or None,
    }

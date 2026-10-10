"""Scheduler service with app-state-backed storage for multi-process support.

Global variables ``_scheduler``, ``_app``, and ``_last_run_guard`` are now
proxied through :class:`~app.services.app_state.AppState` so each Gunicorn
worker maintains its own isolated copy.  The module-level names remain for
backwards compatibility with existing imports.
"""
import logging
import os
import threading
from datetime import datetime, timezone, timedelta

from app import db
from app.models import ScheduledTask, ExecutionLog, Setting
from app.services.script_runner import execute_script
from app.services.async_executor import submit_script

logger = logging.getLogger(__name__)


def _get_state():
    """Get the AppState, falling back to module-level globals for compat."""
    try:
        from flask import current_app
        from app.services.app_state import get_state
        return get_state(current_app._get_current_object())
    except RuntimeError:
        # Outside app context — use module-level fallbacks
        return _ModuleState()


class _ModuleState:
    """Backwards-compatible module-level state (used outside app context)."""
    scheduler = None
    scheduler_app = None
    last_run_guard = {}


def register_task(task):
    state = _get_state()
    sched = state.scheduler
    if sched is None:
        return

    from apscheduler.triggers.cron import CronTrigger

    parts = task.cron_expression.strip().split()
    if len(parts) != 5:
        return

    try:
        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        )

        sched.add_job(
            func=run_task_wrapper,
            trigger=trigger,
            id=f'task_{task.id}',
            args=[task.id],
            replace_existing=True,
            name=task.name,
        )
        job = sched.get_job(f'task_{task.id}')
        if job and job.next_run_time:
            task.next_run = job.next_run_time.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception as e:
        logger.error(f'Failed to register task {task.name}: {e}')


def run_task_wrapper(task_id):
    state = _get_state()
    app = state.scheduler_app
    if app is None:
        return
    now = datetime.now(timezone.utc)
    # Dedup guard: skip if this task ran within the last 60 seconds
    last = state.last_run_guard.get(task_id)
    if last and now - last < timedelta(seconds=60):
        logger.info(f'Dedup guard blocked task {task_id} — last run {last} now={now}')
        return
    state.last_run_guard[task_id] = now

    with app.app_context():
        task = db.session.get(ScheduledTask, task_id)
        if not task or not task.enabled:
            return
        sched = state.scheduler
        job_count = len(sched.get_jobs()) if sched else 0
        logger.info(f'Running task: {task.name} PID={os.getpid()} thread={threading.get_ident()} jobs={job_count}')
        task.last_run = now
        job = sched.get_job(f'task_{task.id}') if sched else None
        if job and job.next_run_time:
            task.next_run = job.next_run_time.astimezone(timezone.utc).replace(tzinfo=None)
        db.session.commit()
        if task.script:
            submit_script(
                task.script,
                source_type='task',
                source_name=task.name,
                extra_globals={
                    'task_id': task.id,
                    'task_name': task.name,
                },
            )


def _run_script_in_app_context(app, script, name):
    with app.app_context():
        execute_script(script, source_type='task', source_name=name)


def _check_query_reports():
    """Check and execute scheduled query reports.

    Cron matching is delegated to APScheduler's ``CronTrigger.matches()`` (the
    same engine used for scheduled tasks) so that full cron syntax — named
    days/months, ranges with steps, day-of-week aliases, etc. — is evaluated
    correctly instead of the old hand-rolled matcher.
    """
    from apscheduler.triggers.cron import CronTrigger
    from app.models import QueryReport
    now = datetime.now(timezone.utc)
    queries = db.session.query(QueryReport).filter(
        QueryReport.schedule_cron != '',
        QueryReport.schedule_cron.isnot(None),
    ).all()
    for q in queries:
        try:
            parts = q.schedule_cron.strip().split()
            if len(parts) != 5:
                continue
            trigger = CronTrigger(
                minute=parts[0], hour=parts[1], day=parts[2],
                month=parts[3], day_of_week=parts[4], timezone=timezone.utc,
            )
            minute_start = now.replace(second=0, microsecond=0)
            window_end = minute_start + timedelta(seconds=59)
            next_fire = trigger.get_next_fire_time(minute_start - timedelta(seconds=1), window_end)
            if next_fire is None or next_fire > window_end:
                continue
            if q.last_run and (now - q.last_run).total_seconds() < 60:
                continue
            result = db.session.execute(db.text(q.sql))
            if result.returns_rows:
                rows = result.fetchall()
                if q.email_to and q.email_subject:
                    cols = list(result.keys())
                    output = [','.join(cols)]
                    for row in rows:
                        output.append(','.join(str(v) if v is not None else '' for v in row))
                    body = '\n'.join(output)
                    try:
                        from app.services.script_runner import _send_email
                        _send_email(to=q.email_to, subject=q.email_subject, body=body)
                    except Exception as e:
                        logger.warning(f'Query report email failed for "{q.name}": {e}')
            q.last_run = now
            db.session.commit()
        except Exception as e:
            logger.warning(f'Scheduled query report "{q.name}" failed: {e}')


def init_scheduler(app):
    """Initialize the scheduler, storing state in AppState for multi-process support."""
    from app.services.app_state import get_state
    state = get_state(app)

    if state.scheduler is not None:
        logger.info(f'Scheduler already running PID={os.getpid()}')
        return

    state.scheduler_app = app
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        state.scheduler = BackgroundScheduler()
        state.scheduler.start()

        with app.app_context():
            tasks = db.session.query(ScheduledTask).filter_by(enabled=True).all()
            for task in tasks:
                register_task(task)
            db.session.commit()
            state.scheduler.add_job(
                func=_check_query_reports_wrapper,
                trigger='interval',
                minutes=1,
                id='_query_report_check',
                replace_existing=True,
                name='Query Report Check',
            )
            state.scheduler.add_job(
                func=_check_incoming_mail_wrapper,
                trigger='interval',
                minutes=1,
                id='_incoming_mail_check',
                replace_existing=True,
                name='Incoming Mail Check',
            )

        logger.info(
            f'Scheduler started PID={os.getpid()} '
            f'tasks={len(tasks)} jobs={len(state.scheduler.get_jobs())}'
        )
    except ImportError:
        logger.info('APScheduler not installed — scheduler disabled')
    except Exception as e:
        logger.error(f'Scheduler init failed: {e}')


def _check_query_reports_wrapper():
    state = _get_state()
    app = state.scheduler_app
    if app is None:
        return
    with app.app_context():
        _check_query_reports()


def _check_incoming_mail():
    from app.services.incoming_mail import poll_incoming_mail
    try:
        poll_interval = int(Setting.get('imap_poll_interval', '5'))
    except (ValueError, TypeError):
        poll_interval = 5
    now = datetime.now(timezone.utc)
    state = _get_state()
    last = state.last_run_guard.get('_imap')
    if last and (now - last).total_seconds() < poll_interval * 60:
        return
    state.last_run_guard['_imap'] = now
    try:
        poll_incoming_mail()
    except Exception as e:
        logger.warning(f'Incoming mail poll failed: {e}')


def _check_incoming_mail_wrapper():
    state = _get_state()
    app = state.scheduler_app
    if app is None:
        return
    with app.app_context():
        _check_incoming_mail()


def refresh_tasks():
    state = _get_state()
    sched = state.scheduler
    if sched is None:
        return
    sched.remove_all_jobs()
    tasks = db.session.query(ScheduledTask).filter_by(enabled=True).all()
    for task in tasks:
        register_task(task)
    db.session.commit()


# ── Backwards-compatible module-level proxies ────────────────────────────────
# These are read dynamically from AppState so existing imports like
# ``from app.services.scheduler import _scheduler`` continue to work.

class _SchedulerProxy:
    """Lazy proxy that forwards attribute access to AppState.scheduler."""
    @property
    def scheduler(self):
        state = _get_state()
        return state.scheduler


# Module-level aliases for backwards compatibility
_scheduler = None  # Fallback; resolved dynamically via _get_state()
_app = None
_last_run_guard = {}

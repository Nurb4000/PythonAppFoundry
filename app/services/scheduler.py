import os
import threading
from datetime import datetime, timezone, timedelta

from app import db
from app.models import ScheduledTask, ExecutionLog, Setting
from app.services.script_runner import execute_script

_scheduler = None
_app = None
_last_run_guard = {}


def init_scheduler(app):
    global _scheduler, _app
    if _scheduler is not None:
        print(f'[SCHEDULER] init_scheduler called but already running PID={os.getpid()}')
        return
    _app = app
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        _scheduler = BackgroundScheduler()
        _scheduler.start()

        with app.app_context():
            tasks = db.session.query(ScheduledTask).filter_by(enabled=True).all()
            for task in tasks:
                register_task(task)
            db.session.commit()

        print(f'[SCHEDULER] Started PID={os.getpid()} WERKZEUG_RUN_MAIN={os.environ.get("WERKZEUG_RUN_MAIN")} APP_DEBUG={os.environ.get("APP_DEBUG")} tasks={len(tasks)} jobs={len(_scheduler.get_jobs())}')
    except ImportError:
        print('[SCHEDULER] APScheduler not installed — scheduler disabled')
    except Exception as e:
        print(f'[SCHEDULER] Init failed: {e}')


def register_task(task):
    if _scheduler is None:
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

        _scheduler.add_job(
            func=run_task_wrapper,
            trigger=trigger,
            id=f'task_{task.id}',
            args=[task.id],
            replace_existing=True,
            name=task.name,
        )
        job = _scheduler.get_job(f'task_{task.id}')
        if job and job.next_run_time:
            from datetime import timezone
            task.next_run = job.next_run_time.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'Failed to register task {task.name}: {e}')


def run_task_wrapper(task_id):
    app = _app
    if app is None:
        return
    now = datetime.now(timezone.utc)
    # Dedup guard: skip if this task ran within the last 60 seconds
    last = _last_run_guard.get(task_id)
    if last and now - last < timedelta(seconds=60):
        print(f'[SCHEDULER] Dedup guard blocked task {task_id} — last run {last} now={now}')
        return
    _last_run_guard[task_id] = now

    with app.app_context():
        task = db.session.get(ScheduledTask, task_id)
        if not task or not task.enabled:
            return
        job_count = len(_scheduler.get_jobs()) if _scheduler else 0
        print(f'[SCHEDULER] Running task: {task.name} PID={os.getpid()} thread={threading.get_ident()} jobs={job_count}')
        task.last_run = now
        job = _scheduler.get_job(f'task_{task.id}') if _scheduler else None
        if job and job.next_run_time:
            task.next_run = job.next_run_time.astimezone(timezone.utc).replace(tzinfo=None)
        db.session.commit()
        if task.script:
            timeout = int(Setting.get('script_timeout', '30'))
            t = threading.Thread(
                target=_run_script_in_app_context,
                args=(app, task.script, task.name),
                daemon=True,
            )
            t.start()
            t.join(timeout=timeout)
            if t.is_alive():
                log = ExecutionLog(
                    source_type='task',
                    source_name=task.name,
                    duration_ms=timeout * 1000,
                    status='error',
                    error_message=f'Task timed out after {timeout}s',
                )
                db.session.add(log)
                db.session.commit()
                logging.getLogger(__name__).error(f'Task {task.name} timed out')


def _run_script_in_app_context(app, script, name):
    with app.app_context():
        execute_script(script, source_type='task', source_name=name)


def _cron_matches(expression, dt):
    """Simple cron matcher for 5-field expressions. Checks at minute granularity."""
    try:
        parts = expression.strip().split()
        if len(parts) != 5:
            return False
        minute, hour, day, month, dow = parts
        def _match(field, value):
            if field == '*':
                return True
            for part in field.split(','):
                if '-' in part:
                    a, b = part.split('-', 1)
                    if a.isdigit() and b.isdigit() and int(a) <= value <= int(b):
                        return True
                elif part.isdigit() and int(part) == value:
                    return True
                elif part == '*/1' or part == '*':
                    return True
                elif part.startswith('*/') and part[2:].isdigit():
                    step = int(part[2:])
                    if step > 0 and value % step == 0:
                        return True
            return False
        return (_match(minute, dt.minute) and _match(hour, dt.hour)
                and _match(day, dt.day) and _match(month, dt.month)
                and _match(dow, dt.weekday()))
    except Exception:
        return False


def _check_query_reports():
    """Check and execute scheduled query reports."""
    from app.models import QueryReport
    now = datetime.now(timezone.utc)
    queries = db.session.query(QueryReport).filter(
        QueryReport.schedule_cron != '',
        QueryReport.schedule_cron.isnot(None),
    ).all()
    for q in queries:
        try:
            if not _cron_matches(q.schedule_cron, now):
                continue
            # Guard: skip if this query ran within the last 60 seconds
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
                    except Exception:
                        pass
            q.last_run = now
            db.session.commit()
        except Exception:
            pass


def init_scheduler(app):
    global _scheduler, _app
    if _scheduler is not None:
        print(f'[SCHEDULER] init_scheduler called but already running PID={os.getpid()}')
        return
    _app = app
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        _scheduler = BackgroundScheduler()
        _scheduler.start()

        with app.app_context():
            tasks = db.session.query(ScheduledTask).filter_by(enabled=True).all()
            for task in tasks:
                register_task(task)
            db.session.commit()
            _scheduler.add_job(
                func=_check_query_reports_wrapper,
                trigger='interval',
                minutes=1,
                id='_query_report_check',
                replace_existing=True,
                name='Query Report Check',
            )

        print(f'[SCHEDULER] Started PID={os.getpid()} WERKZEUG_RUN_MAIN={os.environ.get("WERKZEUG_RUN_MAIN")} APP_DEBUG={os.environ.get("APP_DEBUG")} tasks={len(tasks)} jobs={len(_scheduler.get_jobs())}')
    except ImportError:
        print('[SCHEDULER] APScheduler not installed — scheduler disabled')
    except Exception as e:
        print(f'[SCHEDULER] Init failed: {e}')


def _check_query_reports_wrapper():
    app = _app
    if app is None:
        return
    with app.app_context():
        _check_query_reports()


def refresh_tasks():
    if _scheduler is None:
        return
    _scheduler.remove_all_jobs()
    tasks = db.session.query(ScheduledTask).filter_by(enabled=True).all()
    for task in tasks:
        register_task(task)
    db.session.commit()

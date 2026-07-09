import threading

from app import db
from app.models import ScheduledTask, ExecutionLog, Setting
from app.services.script_runner import execute_script

_scheduler = None
_app = None


def init_scheduler(app):
    global _scheduler, _app
    if _scheduler is not None:
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

        app.logger.info(f'Scheduler started with {len(tasks)} tasks')
    except ImportError:
        app.logger.warning('APScheduler not installed — scheduler disabled')
    except Exception as e:
        app.logger.error(f'Scheduler init failed: {e}')


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
    with app.app_context():
        task = db.session.get(ScheduledTask, task_id)
        if not task or not task.enabled:
            return
        import logging
        logging.getLogger(__name__).info(f'Running task: {task.name}')
        from datetime import datetime, timezone
        task.last_run = datetime.now(timezone.utc)
        job = _scheduler.get_job(f'task_{task.id}')
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


def refresh_tasks():
    if _scheduler is None:
        return
    _scheduler.remove_all_jobs()
    tasks = db.session.query(ScheduledTask).filter_by(enabled=True).all()
    for task in tasks:
        register_task(task)
    db.session.commit()

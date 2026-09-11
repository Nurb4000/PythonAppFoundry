import logging
import time
from datetime import datetime, timezone

from app import db
from app.models import Trigger, ExecutionLog, DeadLetterEntry
from app.services.script_runner import execute_script

logger = logging.getLogger(__name__)


def fire_triggers(event_type, target_table, context=None):
    if context is None:
        context = {}

    triggers = db.session.query(Trigger).filter_by(
        event_type=event_type,
        target_table=target_table,
        enabled=True,
    ).all()

    for trigger in triggers:
        if not trigger.script:
            continue
        try:
            logger.info(f'Firing trigger: {trigger.name} ({event_type} on {target_table})')
            execute_script(trigger.script, source_type='trigger', source_name=trigger.name, extra_globals={
                'event_type': event_type,
                'target_table': target_table,
                'trigger_context': context,
            })
        except Exception as e:
            logger.error(f'Trigger {trigger.name} failed: {e}')
            _add_to_dead_letter(trigger.name, event_type, target_table, str(e),
                                  module_id=trigger.module_id, script_id=trigger.script_id)


def fire_webhook(webhook_slug, payload=None, provided_token=None):
    """Fire triggers for a webhook event synchronously.
    
    Args:
        webhook_slug: The webhook identifier (used as event_type)
        payload: Optional dictionary with request data to pass to the script
        provided_token: Optional auth token from the request to validate against trigger
    """
    if payload is None:
        payload = {}

    triggers = db.session.query(Trigger).filter_by(
        event_type='webhook',
        target_table=webhook_slug,
        enabled=True,
    ).all()

    for trigger in triggers:
        if not trigger.script:
            continue
        if trigger.auth_token:
            if not provided_token or not __import__('secrets').compare_digest(trigger.auth_token, provided_token):
                logger.warning(f'Webhook trigger {trigger.name}: invalid auth token')
                continue
        
        try:
            t0 = time.time()
            logger.info(f'Firing webhook trigger: {trigger.name} ({webhook_slug})')
            execute_script(trigger.script, source_type='webhook', source_name=trigger.name, extra_globals={
                'webhook_slug': webhook_slug,
                'webhook_payload': payload,
                'webhook_request': None,
            })
            duration_ms = int((time.time() - t0) * 1000)
            
            log = ExecutionLog(
                source_type='webhook',
                source_name=trigger.name,
                duration_ms=duration_ms,
                status='success',
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            logger.error(f'Webhook trigger {trigger.name} failed: {e}')
            _add_to_dead_letter(trigger.name, 'webhook', webhook_slug, str(e),
                                  module_id=trigger.module_id, script_id=trigger.script_id)


def fire_webhook_async(webhook_slug, payload=None, provided_token=None):
    """Fire triggers for a webhook event asynchronously via the thread pool.
    
    Returns a list of execution IDs for status polling.
    """
    from app.services.async_executor import submit_script
    
    if payload is None:
        payload = {}

    triggers = db.session.query(Trigger).filter_by(
        event_type='webhook',
        target_table=webhook_slug,
        enabled=True,
    ).all()

    execution_ids = []
    for trigger in triggers:
        if not trigger.script:
            continue
        if trigger.auth_token:
            if not provided_token or not __import__('secrets').compare_digest(trigger.auth_token, provided_token):
                logger.warning(f'Webhook trigger {trigger.name}: invalid auth token')
                continue
        
        exec_id = submit_script(
            trigger.script,
            source_type='webhook',
            source_name=trigger.name,
            extra_globals={
                'webhook_slug': webhook_slug,
                'webhook_payload': payload,
                'webhook_request': None,
            },
            correlation_id=f'webhook:{webhook_slug}',
        )
        execution_ids.append(exec_id)

    return execution_ids


def _add_to_dead_letter(trigger_name, event_type, target, error_msg, module_id=None, script_id=None):
    """Persist a failed execution to the durable dead-letter store.

    Entries are stored in the database (DeadLetterEntry) so they survive a
    restart and are shared across worker processes, unlike the previous
    in-memory list.
    """
    entry = DeadLetterEntry(
        trigger_name=trigger_name,
        event_type=event_type,
        target=target,
        error_message=error_msg[:4000],
        module_id=module_id,
        script_id=script_id,
        status='failed',
        retry_count=0,
    )
    db.session.add(entry)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception('Failed to persist dead-letter entry for %s', trigger_name)

    dl_logger = logging.getLogger('platform.dead_letter')
    dl_logger.warning(f'Dead letter: {trigger_name} - {error_msg[:200]}')
    return getattr(entry, 'id', None)


def get_dead_letter_queue():
    """Return dead-letter entries as a list of dicts.

    Kept dict-shaped for backwards compatibility with callers (health check)
    that only inspect the queue length; the admin UI uses get_dead_letter_entries().
    """
    rows = DeadLetterEntry.query.order_by(DeadLetterEntry.created_at.desc()).all()
    return [
        {
            'id': r.id,
            'trigger_name': r.trigger_name,
            'event_type': r.event_type,
            'target': r.target,
            'error': r.error_message,
            'timestamp': r.created_at.isoformat() if r.created_at else '',
            'retry_count': r.retry_count or 0,
        }
        for r in rows
    ]


def get_dead_letter_entries():
    """Return raw DeadLetterEntry ORM objects (ordered newest first) for the admin UI."""
    return DeadLetterEntry.query.order_by(DeadLetterEntry.created_at.desc()).all()


def dead_letter_count(status=None):
    """Return the number of dead-letter entries, optionally filtered by status."""
    q = DeadLetterEntry.query
    if status is not None:
        q = q.filter(DeadLetterEntry.status == status)
    return q.count()


def clear_dead_letter_queue(status=None):
    """Delete dead-letter entries. Returns the number removed.

    Defaults to clearing only successfully-retried/processed entries; pass
    status='failed' (or a specific status) to remove those.
    """
    q = DeadLetterEntry.query
    if status is not None:
        q = q.filter(DeadLetterEntry.status == status)
    count = q.count()
    q.delete()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception('Failed to clear dead-letter entries')
    return count


def delete_dead_letter_entry(entry_id):
    """Delete a single dead-letter entry by id. Returns True if one was removed."""
    entry = DeadLetterEntry.query.get(entry_id)
    if entry is None:
        return False
    db.session.delete(entry)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception('Failed to delete dead-letter entry %s', entry_id)
    return True


def _refire_trigger(entry):
    """Re-execute the script behind a dead-letter entry (best effort)."""
    from app.models import Trigger
    trigger = Trigger.query.filter_by(
        name=entry.trigger_name, event_type=entry.event_type,
    ).first()
    if not trigger or not trigger.script:
        raise RuntimeError('trigger no longer exists')
    if entry.event_type == 'webhook':
        extra_globals = {
            'webhook_slug': entry.target,
            'webhook_payload': {},
            'webhook_request': None,
        }
    else:
        extra_globals = {'trigger_context': {}}
    execute_script(trigger.script, source_type=entry.event_type,
                   source_name=trigger.name, extra_globals=extra_globals)


def retry_dead_letter(entry_id):
    """Re-attempt a failed dead-letter execution.

    Increments retry_count and flips the entry status based on the re-run.
    Returns True if the entry existed and was retried.
    """
    entry = DeadLetterEntry.query.get(entry_id)
    if entry is None:
        return False

    entry.retry_count = (entry.retry_count or 0) + 1
    entry.status = 'retrying'
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    try:
        _refire_trigger(entry)
        entry.status = 'succeeded'
    except Exception as e:
        entry.status = 'failed'
        logger.error(f'Retry of dead-letter entry {entry_id} failed: {e}')
    finally:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    logger.info(f'Retried dead-letter entry {entry_id} (attempt {entry.retry_count}): status={entry.status}')
    return True

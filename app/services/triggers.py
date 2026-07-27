import logging
import time
from datetime import datetime, timezone

from app import db
from app.models import Trigger, ExecutionLog
from app.services.script_runner import execute_script

logger = logging.getLogger(__name__)

# Dead letter queue for failed webhook executions
_dead_letter_queue = []
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5


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
            _add_to_dead_letter(trigger.name, event_type, target_table, str(e))


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
            _add_to_dead_letter(trigger.name, 'webhook', webhook_slug, str(e))


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


def _add_to_dead_letter(trigger_name, event_type, target, error_msg):
    """Add a failed execution to the dead letter queue."""
    entry = {
        'trigger_name': trigger_name,
        'event_type': event_type,
        'target': target,
        'error': error_msg,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }
    _dead_letter_queue.append(entry)
    
    dl_logger = logging.getLogger('platform.dead_letter')
    dl_logger.warning(f'Dead letter: {trigger_name} - {error_msg[:200]}')


def get_dead_letter_queue():
    """Get the current dead letter queue."""
    return list(_dead_letter_queue)


def clear_dead_letter_queue():
    """Clear the dead letter queue."""
    _dead_letter_queue.clear()


def retry_dead_letter(index=0):
    """Retry a specific dead letter entry (by index)."""
    if 0 <= index < len(_dead_letter_queue):
        entry = _dead_letter_queue.pop(index)
        logger.info(f'Retrying dead letter: {entry["trigger_name"]} - {entry["target"]}')
        return True
    return False

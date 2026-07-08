import logging

from app import db
from app.models import Trigger
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


def fire_webhook(webhook_slug, payload=None):
    """Fire triggers for a webhook event.
    
    Args:
        webhook_slug: The webhook identifier (used as event_type)
        payload: Optional dictionary with request data to pass to the script
    """
    if payload is None:
        payload = {}

    # Webhook triggers use 'webhook' as event_type and the slug as target_table
    triggers = db.session.query(Trigger).filter_by(
        event_type='webhook',
        target_table=webhook_slug,
        enabled=True,
    ).all()

    for trigger in triggers:
        if not trigger.script:
            continue
        try:
            logger.info(f'Firing webhook trigger: {trigger.name} ({webhook_slug})')
            execute_script(trigger.script, source_type='webhook', source_name=trigger.name, extra_globals={
                'webhook_slug': webhook_slug,
                'webhook_payload': payload,
                'webhook_request': None,  # Will be set by route if needed
            })
        except Exception as e:
            logger.error(f'Webhook trigger {trigger.name} failed: {e}')

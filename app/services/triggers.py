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

"""Structured logging for the platform.

Provides JSON-formatted logs with context (module_id, script_id, user_id, etc.)
for better debugging and monitoring.
"""
import json
import logging
import sys
from datetime import datetime, timezone


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': getattr(record, 'module', ''),
            'function': getattr(record, 'funcName', ''),
            'line': record.lineno,
        }
        
        # Add extra context if present
        if hasattr(record, 'extra_data'):
            log_data.update(record.extra_data)
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, default=str)


def setup_structured_logging(app=None, level=logging.INFO):
    """Configure structured logging for the application."""
    logger = logging.getLogger()
    logger.setLevel(level)
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Add console handler with structured formatting
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    logger.addHandler(handler)
    
    # Add file handler if app is provided
    if app:
        log_dir = app.instance_path / 'logs' if hasattr(app.instance_path, '__truediv__') else None
        if log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / 'platform.log'
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(StructuredFormatter())
            logger.addHandler(file_handler)
    
    return logger


def log_execution(script_name, module_id, duration_ms, status, error=None, user_id=None):
    """Log a script execution with structured data."""
    logger = logging.getLogger('platform.execution')
    extra = {
        'module': 'execution',
        'extra_data': {
            'script': script_name,
            'module_id': module_id,
            'duration_ms': duration_ms,
            'status': status,
            'user_id': user_id,
        }
    }
    
    if status == 'error' and error:
        logger.error(f'Script execution failed: {script_name}', extra=extra)
    else:
        logger.info(f'Script executed: {script_name} ({duration_ms}ms)', extra=extra)


def log_webhook(webhook_slug, payload_size, status, duration_ms):
    """Log a webhook invocation with structured data."""
    logger = logging.getLogger('platform.webhook')
    extra = {
        'module': 'webhook',
        'extra_data': {
            'webhook': webhook_slug,
            'payload_size': payload_size,
            'status': status,
            'duration_ms': duration_ms,
        }
    }
    
    if status == 'error':
        logger.error(f'Webhook failed: {webhook_slug}', extra=extra)
    else:
        logger.info(f'Webhook processed: {webhook_slug} ({duration_ms}ms)', extra=extra)

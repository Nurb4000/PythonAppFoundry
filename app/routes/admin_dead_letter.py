"""Admin UI for the durable dead-letter queue of failed trigger/webhook executions."""
from flask import Blueprint, request, redirect, url_for, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required, render_admin
from app.services.triggers import (
    get_dead_letter_entries,
    retry_dead_letter,
    delete_dead_letter_entry,
    clear_dead_letter_queue,
    dead_letter_count,
)
from app.services.audit import log_audit

dead_letter_bp = Blueprint('dead_letter', __name__)


@dead_letter_bp.route('/')
@admin_required
def list_dead_letter():
    status_filter = request.args.get('status', '')
    search = request.args.get('q', '').strip()

    entries = get_dead_letter_entries()
    if status_filter:
        entries = [e for e in entries if e.status == status_filter]
    if search:
        needle = search.lower()
        entries = [
            e for e in entries
            if needle in (e.trigger_name or '').lower()
            or needle in (e.event_type or '').lower()
            or needle in (e.target or '').lower()
        ]

    content = render_admin(
        'Dead Letter Queue',
        'admin/dead_letter/list.html',
        entries=entries,
        status_filter=status_filter,
        search=search,
        counts={
            'all': dead_letter_count(),
            'failed': dead_letter_count(status='failed'),
            'succeeded': dead_letter_count(status='succeeded'),
            'retrying': dead_letter_count(status='retrying'),
        },
    )
    return content


@dead_letter_bp.route('/retry/<int:entry_id>', methods=['POST'])
@admin_required
@csrf_protect
def retry_dead_letter_action(entry_id):
    if retry_dead_letter(entry_id):
        log_audit('retry', 'dead_letter', entry_id)
        flash(f'Retry submitted for entry #{entry_id}.')
    else:
        flash(f'Dead-letter entry #{entry_id} not found.')
    return redirect(url_for('admin.dead_letter.list_dead_letter'))


@dead_letter_bp.route('/delete/<int:entry_id>', methods=['POST'])
@admin_required
@csrf_protect
def delete_dead_letter_action(entry_id):
    if delete_dead_letter_entry(entry_id):
        log_audit('delete', 'dead_letter', entry_id)
        flash(f'Dead-letter entry #{entry_id} deleted.')
    else:
        flash(f'Dead-letter entry #{entry_id} not found.')
    return redirect(url_for('admin.dead_letter.list_dead_letter'))


@dead_letter_bp.route('/clear', methods=['POST'])
@admin_required
@csrf_protect
def clear_dead_letter():
    """Clear successfully-retried / processed entries (status != failed)."""
    removed = clear_dead_letter_queue(status='succeeded')
    log_audit('clear', 'dead_letter', 0, details=f'removed={removed}')
    noun = 'entry' if removed == 1 else 'entries'
    flash(f'Cleared {removed} processed dead-letter {noun}.')
    return redirect(url_for('admin.dead_letter.list_dead_letter'))


@dead_letter_bp.route('/clear-all', methods=['POST'])
@admin_required
@csrf_protect
def clear_all_dead_letter():
    removed = clear_dead_letter_queue()
    log_audit('clear_all', 'dead_letter', 0, details=f'removed={removed}')
    flash(f'Cleared all {removed} dead-letter entries.')
    return redirect(url_for('admin.dead_letter.list_dead_letter'))

"""Admin routes for extended notification management."""
from flask import Blueprint, request, redirect, url_for, render_template_string

notification_extended_bp = Blueprint('notification_extended', __name__)


@notification_extended_bp.route('/notifications/test-email', methods=['POST'])
@admin_required
@csrf_protect
def test_email_notification():
    """Send a test email notification."""
    from app.services.script_runner import _send_email
    
    to = request.form.get('test_to', '')
    if not to:
        flash('Recipient email required', 'error')
        return redirect(url_for('admin.notification_settings'))
    
    try:
        _send_email(to=to, subject='Test Notification', body='<h1>Test Email</h1><p>This is a test notification email.</p>', html=True)
        flash(f'Test email sent to {to}')
    except Exception as e:
        flash(f'Failed to send test email: {e}', 'error')
    
    return redirect(url_for('admin.notification_settings'))


@notification_extended_bp.route('/notifications/test-slack', methods=['POST'])
@admin_required
@csrf_protect
def test_slack_notification():
    """Send a test Slack notification."""
    import requests
    
    webhook_url = Setting.get('slack_webhook_url', '')
    if not webhook_url:
        flash('Slack webhook URL not configured', 'error')
        return redirect(url_for('admin.notification_settings'))
    
    try:
        response = requests.post(webhook_url, json={'text': 'Test Slack notification from PythonAppFoundry'})
        if response.status_code == 200:
            flash('Test Slack notification sent successfully')
        else:
            flash(f'Slack notification failed: {response.status_code}', 'error')
    except Exception as e:
        flash(f'Failed to send Slack notification: {e}', 'error')
    
    return redirect(url_for('admin.notification_settings'))


@notification_extended_bp.route('/notifications/test-discord', methods=['POST'])
@admin_required
@csrf_protect
def test_discord_notification():
    """Send a test Discord notification."""
    import requests
    
    webhook_url = Setting.get('discord_webhook_url', '')
    if not webhook_url:
        flash('Discord webhook URL not configured', 'error')
        return redirect(url_for('admin.notification_settings'))
    
    try:
        response = requests.post(webhook_url, json={'content': 'Test Discord notification from PythonAppFoundry'})
        if response.status_code == 204:
            flash('Test Discord notification sent successfully')
        else:
            flash(f'Discord notification failed: {response.status_code}', 'error')
    except Exception as e:
        flash(f'Failed to send Discord notification: {e}', 'error')
    
    return redirect(url_for('admin.notification_settings'))

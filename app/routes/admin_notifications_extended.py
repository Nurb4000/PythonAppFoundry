"""Admin routes for extended notification settings."""
from flask import Blueprint, request, redirect, url_for, flash

notifications_extended_bp = Blueprint('notifications_extended', __name__)


@notifications_extended_bp.route('/notifications/settings', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def notification_settings():
    """Configure notification preferences."""
    from app.models import Setting
    
    if request.method == 'POST':
        Setting.set('email_notifications', 'true' if 'email_notifications' in request.form else 'false')
        Setting.set('slack_webhook_url', request.form.get('slack_webhook_url', ''))
        Setting.set('discord_webhook_url', request.form.get('discord_webhook_url', ''))
        flash('Notification settings saved')
        return redirect(url_for('admin.notification_settings'))
    
    email_notifications = Setting.get('email_notifications', 'false') == 'true'
    slack_webhook_url = Setting.get('slack_webhook_url', '')
    discord_webhook_url = Setting.get('discord_webhook_url', '')
    
    return render_admin('Notification Settings', '''
<form method="POST">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<h3>Email Notifications</h3>
<label><input name="email_notifications" type="checkbox" {% if email_notifications %}checked{% endif %}> Enable Email Notifications</label>

<h3>Slack Integration</h3>
<label>Slack Webhook URL <input name="slack_webhook_url" value="{{ slack_webhook_url }}" placeholder="https://hooks.slack.com/..."></label>

<h3>Discord Integration</h3>
<label>Discord Webhook URL <input name="discord_webhook_url" value="{{ discord_webhook_url }}" placeholder="https://discord.com/api/webhooks/..."></label>

<button type="submit" style="margin-top:1rem;padding:8px 20px;background:#2563eb;color:#fff;border:none;border-radius:4px;cursor:pointer;">Save Notification Settings</button>
</form>
''', email_notifications=email_notifications, slack_webhook_url=slack_webhook_url, discord_webhook_url=discord_webhook_url)
